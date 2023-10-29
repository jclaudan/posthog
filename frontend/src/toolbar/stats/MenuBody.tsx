import { DateFilter } from 'lib/components/DateFilter/DateFilter'
import { getShadowRootPopoverContainer } from '~/toolbar/utils'
import { Spinner } from 'lib/lemon-ui/Spinner'
import { LemonButton } from 'lib/lemon-ui/LemonButton'
import { IconSync } from 'lib/lemon-ui/icons'
import { Tooltip } from 'lib/lemon-ui/Tooltip'
import { LemonSwitch } from 'lib/lemon-ui/LemonSwitch'
import { useActions, useValues } from 'kea'
import { heatmapLogic } from '~/toolbar/elements/heatmapLogic'
import { elementsLogic } from '~/toolbar/elements/elementsLogic'

export const MenuBody = (): JSX.Element => {
    const { matchLinksByHref, countedElements, clickCount, heatmapLoading, heatmapFilter, canLoadMoreElementStats } =
        useValues(heatmapLogic)
    const { setHeatmapFilter, loadMoreElementStats, setMatchLinksByHref } = useActions(heatmapLogic)
    const { setHighlightElement, setSelectedElement } = useActions(elementsLogic)

    return (
        <>
            <div className="flex items-center gap-2">
                <DateFilter
                    dateFrom={heatmapFilter.date_from ?? '-7d'}
                    dateTo={heatmapFilter.date_to}
                    onChange={(date_from, date_to) => setHeatmapFilter({ date_from, date_to })}
                    getPopupContainer={getShadowRootPopoverContainer}
                />

                {heatmapLoading ? <Spinner /> : null}
            </div>
            <div>
                Found: {countedElements.length} elements / {clickCount} clicks!
            </div>
            <div>
                <LemonButton
                    icon={<IconSync />}
                    type={'secondary'}
                    status={'primary-alt'}
                    size={'small'}
                    onClick={loadMoreElementStats}
                    disabledReason={canLoadMoreElementStats ? undefined : 'Loaded all elements in this data range.'}
                    getTooltipPopupContainer={getShadowRootPopoverContainer}
                >
                    Load more
                </LemonButton>
            </div>

            <Tooltip
                title={
                    'Matching links by their target URL can exclude clicks from the heatmap if the URL is too unique.'
                }
                getPopupContainer={getShadowRootPopoverContainer}
            >
                <div>
                    <LemonSwitch
                        checked={matchLinksByHref}
                        label={'Match links by their target URL'}
                        onChange={(checked) => setMatchLinksByHref(checked)}
                        fullWidth={true}
                        bordered={true}
                    />
                </div>
            </Tooltip>
            <div className="FlagList flex flex-col w-full overflow-y-scroll h-full">
                {countedElements.map(({ element, count, actionStep }, index) => {
                    return (
                        <div
                            className="p-2 flex flex-row justify-between cursor-pointer hover:bg-primary-highlight"
                            key={index}
                            onClick={() => setSelectedElement(element)}
                            onMouseEnter={() => setHighlightElement(element)}
                            onMouseLeave={() => setHighlightElement(null)}
                        >
                            <div>
                                {index + 1}.&nbsp;
                                {actionStep?.text ||
                                    (actionStep?.tag_name ? (
                                        <code>&lt;{actionStep.tag_name}&gt;</code>
                                    ) : (
                                        <em>Element</em>
                                    ))}
                            </div>
                            <div>{count} clicks</div>
                        </div>
                    )
                })}
            </div>
        </>
    )
}
