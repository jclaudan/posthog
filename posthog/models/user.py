from functools import cached_property
from typing import (
    Any,
    Callable,
    Dict,
    List,
    Optional,
    Tuple,
    Type,
    TypedDict,
)

from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models, transaction
from django.db.models import Q
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from rest_framework.exceptions import ValidationError

from posthog.cloud_utils import get_cached_instance_license, is_cloud
from posthog.constants import AvailableFeature
from posthog.settings import INSTANCE_TAG, SITE_URL
from posthog.utils import get_instance_realm

from .organization import Organization, OrganizationMembership
from .personal_api_key import PersonalAPIKey, hash_key_value
from .team import Team
from .utils import UUIDClassicModel, generate_random_token, sane_repr


class Notifications(TypedDict, total=False):
    plugin_disabled: bool


NOTIFICATION_DEFAULTS: Notifications = {"plugin_disabled": True}

# We don't ned the following attributes in most cases, so we defer them by default
DEFERED_ATTRS = ["requested_password_reset_at"]


class UserManager(BaseUserManager):
    """Define a model manager for User model with no username field."""

    def get_queryset(self):
        return super().get_queryset().defer(*DEFERED_ATTRS)

    model: Type["User"]

    use_in_migrations = True

    def create_user(self, email: str, password: Optional[str], first_name: str, **extra_fields) -> "User":
        """Create and save a User with the given email and password."""
        if email is None:
            raise ValueError("Email must be provided!")
        email = self.normalize_email(email)
        extra_fields.setdefault("distinct_id", generate_random_token())
        user = self.model(email=email, first_name=first_name, **extra_fields)
        if password is not None:
            user.set_password(password)
        user.save()
        return user

    def bootstrap(
        self,
        organization_name: str,
        email: str,
        password: Optional[str],
        first_name: str = "",
        organization_fields: Optional[Dict[str, Any]] = None,
        team_fields: Optional[Dict[str, Any]] = None,
        create_team: Optional[Callable[["Organization", "User"], "Team"]] = None,
        is_staff: bool = False,
        **user_fields,
    ) -> Tuple["Organization", "Team", "User"]:
        """Instead of doing the legwork of creating a user from scratch, delegate the details with bootstrap."""
        with transaction.atomic():
            organization_fields = organization_fields or {}
            organization_fields.setdefault("name", organization_name)
            organization = Organization.objects.create(**organization_fields)
            user = self.create_user(
                email=email,
                password=password,
                first_name=first_name,
                is_staff=is_staff,
                **user_fields,
            )
            if create_team:
                team = create_team(organization, user)
            else:
                team = Team.objects.create_with_data(user=user, organization=organization, **(team_fields or {}))
            user.join(organization=organization, level=OrganizationMembership.Level.OWNER)
            return organization, team, user

    def create_and_join(
        self,
        organization: Organization,
        email: str,
        password: Optional[str],
        first_name: str = "",
        level: OrganizationMembership.Level = OrganizationMembership.Level.MEMBER,
        **extra_fields,
    ) -> "User":
        with transaction.atomic():
            user = self.create_user(email=email, password=password, first_name=first_name, **extra_fields)
            user.join(organization=organization, level=level)
            return user

    def get_from_personal_api_key(self, key_value: str) -> Optional["User"]:
        try:
            personal_api_key: PersonalAPIKey = (
                PersonalAPIKey.objects.select_related("user")
                .filter(user__is_active=True)
                .get(secure_value=hash_key_value(key_value))
            )
        except PersonalAPIKey.DoesNotExist:
            return None
        else:
            personal_api_key.last_used_at = timezone.now()
            personal_api_key.save()
            return personal_api_key.user


def events_column_config_default() -> Dict[str, Any]:
    return {"active": "DEFAULT"}


class User(AbstractUser, UUIDClassicModel):
    USERNAME_FIELD = "email"
    REQUIRED_FIELDS: List[str] = []

    DISABLED = "disabled"
    TOOLBAR = "toolbar"
    TOOLBAR_CHOICES = [(DISABLED, DISABLED), (TOOLBAR, TOOLBAR)]

    current_organization = models.ForeignKey(
        "posthog.Organization",
        models.SET_NULL,
        null=True,
        related_name="users_currently+",
    )
    current_team = models.ForeignKey("posthog.Team", models.SET_NULL, null=True, related_name="teams_currently+")
    email = models.EmailField(_("email address"), unique=True)
    pending_email = models.EmailField(_("pending email address awaiting verification"), null=True, blank=True)
    temporary_token: models.CharField = models.CharField(max_length=200, null=True, blank=True, unique=True)
    distinct_id: models.CharField = models.CharField(max_length=200, null=True, blank=True, unique=True)
    is_email_verified: models.BooleanField = models.BooleanField(null=True, blank=True)
    requested_password_reset_at: models.DateTimeField = models.DateTimeField(null=True, blank=True)
    has_seen_product_intro_for: models.JSONField = models.JSONField(null=True, blank=True)

    # Preferences / configuration options
    email_opt_in: models.BooleanField = models.BooleanField(default=False, null=True, blank=True)
    # These override the notification settings
    partial_notification_settings: models.JSONField = models.JSONField(null=True, blank=True)
    anonymize_data: models.BooleanField = models.BooleanField(default=False, null=True, blank=True)
    toolbar_mode: models.CharField = models.CharField(
        max_length=200, null=True, blank=True, choices=TOOLBAR_CHOICES, default=TOOLBAR
    )

    # DEPRECATED
    events_column_config: models.JSONField = models.JSONField(default=events_column_config_default)

    # Remove unused attributes from `AbstractUser`
    username = None  # type: ignore

    objects: UserManager = UserManager()  # type: ignore

    @property
    def is_superuser(self) -> bool:  # type: ignore
        return self.is_staff

    @cached_property
    def teams(self):
        """
        All teams the user has access to on any organization, taking into account project based permissioning
        """
        teams = Team.objects.filter(organization__members=self)
        if Organization.objects.filter(
            members=self,
            available_features__contains=[AvailableFeature.PROJECT_BASED_PERMISSIONING],
        ).exists():
            try:
                from ee.models import ExplicitTeamMembership
            except ImportError:
                pass
            else:
                available_private_project_ids = ExplicitTeamMembership.objects.filter(
                    Q(parent_membership__user=self)
                ).values_list("team_id", flat=True)
                organizations_where_user_is_admin = OrganizationMembership.objects.filter(
                    user=self, level__gte=OrganizationMembership.Level.ADMIN
                ).values_list("organization_id", flat=True)
                # If project access control IS applicable, make sure
                # - project doesn't have access control OR
                # - the user has explicit access OR
                # - the user is Admin or owner
                teams = teams.filter(
                    Q(access_control=False)
                    | Q(pk__in=available_private_project_ids)
                    | Q(organization__pk__in=organizations_where_user_is_admin)
                )

        return teams.order_by("access_control", "id")

    @cached_property
    def organization(self) -> Optional[Organization]:
        if self.current_organization is None:
            if self.current_team is not None:
                self.current_organization_id = self.current_team.organization_id
            self.current_organization = self.organizations.first()
            self.save()
        return self.current_organization

    @cached_property
    def team(self) -> Optional[Team]:
        if self.current_team is None and self.organization is not None:
            self.current_team = self.teams.filter(organization=self.current_organization).first()
            self.save()
        return self.current_team

    def join(
        self,
        *,
        organization: Organization,
        level: OrganizationMembership.Level = OrganizationMembership.Level.MEMBER,
    ) -> OrganizationMembership:
        with transaction.atomic():
            membership = OrganizationMembership.objects.create(user=self, organization=organization, level=level)
            self.current_organization = organization
            if (
                AvailableFeature.PROJECT_BASED_PERMISSIONING not in organization.available_features
                or level >= OrganizationMembership.Level.ADMIN
            ):
                # If project access control is NOT applicable, simply prefer open projects just in case
                self.current_team = organization.teams.order_by("access_control", "id").first()
            else:
                # If project access control IS applicable, make sure the user is assigned a project they have access to
                # We don't need to check for ExplicitTeamMembership as none can exist for a completely new member
                self.current_team = organization.teams.order_by("id").filter(access_control=False).first()
            self.save()
        self.update_billing_distinct_ids(organization)
        return membership

    @property
    def notification_settings(self) -> Notifications:
        return {
            **NOTIFICATION_DEFAULTS,  # type: ignore
            **(self.partial_notification_settings if self.partial_notification_settings else {}),
        }

    def leave(self, *, organization: Organization) -> None:
        membership: OrganizationMembership = OrganizationMembership.objects.get(user=self, organization=organization)
        if membership.level == OrganizationMembership.Level.OWNER:
            raise ValidationError("Cannot leave the organization as its owner!")
        with transaction.atomic():
            membership.delete()
            if self.current_organization == organization:
                self.current_organization = self.organizations.first()
                self.current_team = (
                    None if self.current_organization is None else self.current_organization.teams.first()
                )
                self.team = self.current_team  # Update cached property
                self.save()
        self.update_billing_distinct_ids(organization)

    def update_billing_distinct_ids(self, organization: Organization) -> None:
        from ee.billing.billing_manager import BillingManager  # avoid circular import

        if is_cloud() and get_cached_instance_license() is not None:
            BillingManager(get_cached_instance_license()).update_billing_distinct_ids(organization)

    def get_analytics_metadata(self):
        team_member_count_all: int = (
            OrganizationMembership.objects.filter(organization__in=self.organizations.all())
            .values("user_id")
            .distinct()
            .count()
        )

        current_organization_membership = None
        if self.organization:
            current_organization_membership = self.organization.memberships.filter(user=self).first()

        project_setup_complete = False
        if self.team and self.team.completed_snippet_onboarding and self.team.ingested_event:
            project_setup_complete = True

        return {
            "realm": get_instance_realm(),
            "email_opt_in": self.email_opt_in,
            "anonymize_data": self.anonymize_data,
            "email": self.email if not self.anonymize_data else None,
            "is_signed_up": True,
            "organization_count": self.organization_memberships.count(),
            "project_count": self.teams.count(),
            "team_member_count_all": team_member_count_all,
            "completed_onboarding_once": self.teams.filter(
                completed_snippet_onboarding=True, ingested_event=True
            ).exists(),  # has completed the onboarding at least for one project
            # properties dependent on current project / org below
            "organization_id": str(self.organization.id) if self.organization else None,
            "current_organization_membership_level": current_organization_membership.level
            if current_organization_membership
            else None,
            "project_id": str(self.team.uuid) if self.team else None,
            "project_setup_complete": project_setup_complete,
            "joined_at": self.date_joined,
            "has_password_set": self.has_usable_password(),
            "has_social_auth": self.social_auth.exists(),  # type: ignore
            "social_providers": list(self.social_auth.values_list("provider", flat=True)),  # type: ignore
            "instance_url": SITE_URL,
            "instance_tag": INSTANCE_TAG,
            "is_email_verified": self.is_email_verified,
            "has_seen_product_intro_for": self.has_seen_product_intro_for,
        }

    __repr__ = sane_repr("email", "first_name", "distinct_id")
