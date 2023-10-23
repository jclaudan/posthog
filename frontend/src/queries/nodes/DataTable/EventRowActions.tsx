import { EventType, NotebookNodeType, NotebookTarget } from '~/types'
import { More } from 'lib/lemon-ui/LemonButton/More'
import { LemonButton } from 'lib/lemon-ui/LemonButton'
import { createActionFromEvent } from 'scenes/events/createActionFromEvent'
import { urls } from 'scenes/urls'
import { getCurrentTeamId } from 'lib/utils/logics'
import { teamLogic } from 'scenes/teamLogic'
import { IconLink, IconPlayCircle } from 'lib/lemon-ui/icons'
import { useActions } from 'kea'
import { sessionPlayerModalLogic } from 'scenes/session-recordings/player/modal/sessionPlayerModalLogic'
import { copyToClipboard, insightUrlForEvent } from 'lib/utils'
import { dayjs } from 'lib/dayjs'
import { IconNotebook } from '@posthog/icons'
import { notebooksModel } from '~/models/notebooksModel'

interface EventActionProps {
    event: EventType
}

export function EventRowActions({ event }: EventActionProps): JSX.Element {
    const { openSessionPlayer } = useActions(sessionPlayerModalLogic)
    const insightUrl = insightUrlForEvent(event)
    const { createNotebook } = useActions(notebooksModel)

    return (
        <More
            overlay={
                <>
                    {getCurrentTeamId() && (
                        <LemonButton
                            status="stealth"
                            onClick={() =>
                                createActionFromEvent(
                                    getCurrentTeamId(),
                                    event,
                                    0,
                                    teamLogic.findMounted()?.values.currentTeam?.data_attributes || []
                                )
                            }
                            fullWidth
                            data-attr="events-table-create-action"
                        >
                            Create action from event
                        </LemonButton>
                    )}
                    {event.uuid && event.timestamp && (
                        <LemonButton
                            status="stealth"
                            fullWidth
                            sideIcon={<IconLink />}
                            data-attr="events-table-event-link"
                            onClick={async () =>
                                await copyToClipboard(
                                    `${window.location.origin}${urls.event(String(event.uuid), event.timestamp)}`,
                                    'link to event'
                                )
                            }
                        >
                            Copy link to event
                        </LemonButton>
                    )}
                    {!!event.properties?.$session_id && (
                        <LemonButton
                            status="stealth"
                            to={urls.replaySingle(event.properties.$session_id)}
                            disableClientSideRouting
                            onClick={(e) => {
                                e.preventDefault()
                                if (event.properties.$session_id) {
                                    openSessionPlayer(
                                        { id: event.properties.$session_id },
                                        dayjs(event.timestamp).valueOf()
                                    )
                                }
                            }}
                            fullWidth
                            sideIcon={<IconPlayCircle />}
                            data-attr="events-table-usage"
                        >
                            View recording
                        </LemonButton>
                    )}
                    {insightUrl && (
                        <LemonButton to={insightUrl} status="stealth" fullWidth data-attr="events-table-usage">
                            Try out in Insights
                        </LemonButton>
                    )}
                    {event.event === '$feedback' && (
                        <LemonButton
                            sideIcon={<IconNotebook />}
                            status="stealth"
                            fullWidth
                            data-attr="events-table-usage"
                            onClick={() => {
                                const content = []

                                const personId = event.distinct_id ?? event.person?.distinct_ids[0]
                                if (personId) {
                                    content.push(
                                        {
                                            type: 'paragraph',
                                            content: [
                                                { type: 'text', marks: [{ type: 'bold' }], text: 'Reported by:' },
                                            ],
                                        },
                                        { type: NotebookNodeType.Person, attrs: { id: personId } }
                                    )
                                }

                                if (event.properties?.$session_id) {
                                    content.push(
                                        { type: 'paragraph', content: [] },
                                        { type: 'text', marks: [{ type: 'bold' }], text: 'Session replay:' },
                                        {
                                            type: NotebookNodeType.Recording,
                                            attrs: { id: event.properties?.$session_id },
                                        }
                                    )
                                }

                                if (event.properties.$attachments && event.properties.$attachments.length > 0) {
                                    content.push({ type: 'paragraph', content: [] })
                                    event.properties.$attachments.forEach((mediaLocation: string) => {
                                        content.push({
                                            type: NotebookNodeType.Attachment,
                                            attrs: { mediaLocation: mediaLocation },
                                        })
                                    })
                                }
                                createNotebook(`Feedback: ${event.properties.$title}`, NotebookTarget.Popover, content)
                            }}
                        >
                            Open in Notebook
                        </LemonButton>
                    )}
                </>
            }
        />
    )
}
