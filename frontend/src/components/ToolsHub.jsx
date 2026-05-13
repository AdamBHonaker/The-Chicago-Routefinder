/* FEAT-018 — Tools hub.
 *
 * Container that lives inside the (renamed) "Tools" tab body. Renders a
 * vertical stack of "tool cards"; each card launches a sub-view that
 * replaces the hub in the tab body. A back affordance inside the sub-view
 * returns the user to the hub.
 *
 * The pattern is intentionally simple — no router, no shared sub-view
 * shell — so each tool can render whatever JSX it wants. To register a new
 * tool, add an entry to TOOLS below and write the corresponding sub-view
 * component under components/tools/. Card metadata (headline + description)
 * comes from i18n keys ``tools_<id>_headline`` / ``tools_<id>_desc``.
 *
 * State management note: the active sub-view is intentionally NOT persisted
 * across tab switches. Per FEAT-018 Decision (sub-views are short): pressing
 * back returns to the hub; switching tabs and returning shows the hub.
 */

import { useState, lazy, Suspense } from "react";
import { useTranslation } from "react-i18next";

const SavedLocationsTool = lazy(() => import("./tools/SavedLocationsTool.jsx"));
const SchedulesTool      = lazy(() => import("./tools/SchedulesTool.jsx"));
const LastTrainTool      = lazy(() => import("./tools/LastTrainTool.jsx"));

const TOOLS = [
  { id: "saved",      Component: SavedLocationsTool },
  { id: "schedules",  Component: SchedulesTool      },
  { id: "last_train", Component: LastTrainTool      },
];

export default function ToolsHub({
  savedRoutes,
  pinnedStops,
  onDeleteRoute,
  onRouteSelect,
  onUnpin,
}) {
  const { t } = useTranslation();
  const [activeTool, setActiveTool] = useState(null);
  // Optional pre-seed for the Schedules picker, set by SavedLocationsTool
  // when the user taps "Schedule →" on a saved-stop card (Decision 10).
  const [scheduleSeed, setScheduleSeed] = useState(null);

  function launchSchedulesFromStop(stopId) {
    setScheduleSeed({ stopId });
    setActiveTool("schedules");
  }

  if (activeTool) {
    const entry = TOOLS.find((t) => t.id === activeTool);
    if (!entry) return null;
    const { Component } = entry;
    return (
      <Suspense fallback={null}>
        <Component
          onBack={() => {
            setActiveTool(null);
            setScheduleSeed(null);
          }}
          savedRoutes={savedRoutes}
          pinnedStops={pinnedStops}
          onDeleteRoute={onDeleteRoute}
          onRouteSelect={onRouteSelect}
          onUnpin={onUnpin}
          onViewSchedule={launchSchedulesFromStop}
          seed={scheduleSeed}
        />
      </Suspense>
    );
  }

  return (
    <section className="tools-hub main">
      <h2 className="tool-card__headline tools-hub__heading">
        {t("tools_hub_heading")}
      </h2>
      {TOOLS.map(({ id }) => (
        <button
          key={id}
          type="button"
          className="tool-card"
          onClick={() => setActiveTool(id)}
        >
          <span className="tool-card__headline">{t(`tools_${id}_headline`)}</span>
          <span className="tool-card__desc">{t(`tools_${id}_desc`)}</span>
          <span className="tool-card__cta">{t("tools_open")} →</span>
        </button>
      ))}
    </section>
  );
}
