# `backend/schedule_data/`

Build artifacts emitted by [`scripts/build_schedule_index.py`](../../scripts/build_schedule_index.py)
to power FEAT-018 (Published CTA schedule viewer).

## Contents

- **One JSON file per CTA route** (`<route_id>.json`) — full published timetable
  for the route, split by direction and stop, with departure times bucketed
  into `weekday` / `saturday` / `sunday` service days.
- **`_manifest.json`** — picker manifest consumed by `GET /schedule/routes`.
  Contains all route metadata plus a `stop_routes` reverse index that lets the
  frontend pre-highlight a saved stop's serving routes when entering the
  Schedules picker from a saved-stop card (FEAT-018 Decision 10).

## Regenerating

These files are **build artifacts**, not authored sources. Regenerate them
whenever `backend/gtfs_data/` changes (i.e. after every
`python backend/fetch_gtfs.py` refresh):

```
python scripts/build_schedule_index.py
```

The script reads `backend/gtfs_data/` only — it does not hit the network.
Runs in ~1 minute on the maintainer's machine.

If a route ID is missing here, `GET /schedule/{route_id}` 404s; this is the
intended failure mode if the build script wasn't re-run after a GTFS refresh
that introduced new routes.

## JSON shape

See the header docstring of
[`scripts/build_schedule_index.py`](../../scripts/build_schedule_index.py) for
the authoritative description of:

- the per-route JSON shape (directions → stops → times by service-day bucket),
- the service-day bucket rules (including the `calendar_dates.txt` holiday
  override that folds federal holidays into the Sunday bucket),
- the route-category classification rule (`train` / `bus_express` /
  `bus_frequent` / `bus_regular`, derived from GTFS `route_color`).
