/**
 * useMapMarker — mount a React component as a MapLibre marker.
 *
 * Encapsulates the createRoot/setLngLat/unmount lifecycle that previously
 * lived inline in MapView.jsx. The hook owns:
 *   - DOM element + ReactDOM root creation on first availability
 *   - marker.setLngLat updates when coords change (no remount)
 *   - root.render updates when component props change (no remount)
 *   - clean teardown when lngLat goes null, map unmounts, or component unmounts
 *
 * Pass `lngLat = null` to suppress the marker (e.g. trip not active, no
 * destination yet). When it becomes a valid [lng, lat] tuple the marker is
 * (re)created. Going from valid → null tears it down.
 *
 * `onMount(marker)` fires once per mount cycle — use it to attach DOM event
 * listeners (e.g. click handlers). The callback closes over the latest
 * caller scope via an internal ref, so it sees current state/props even
 * though the effect deps don't include it.
 */
import { useEffect, useRef } from "react";
import ReactDOM from "react-dom/client";
import maplibregl from "maplibre-gl";

// Imperative escape hatch — used by the live-position marker, whose heading
// prop must update in lock-step with a ref-stored smoothed value. The ref
// can't trigger React re-renders, so the hook's auto-render-on-props-change
// would always lag by one frame. Callers using mountMarker manage the
// {marker, root} pair themselves and call root.render() to update props.
export function mountMarker(map, Component, props, lngLat, { className } = {}) {
  const el = document.createElement("div");
  if (className) el.className = className;
  const root = ReactDOM.createRoot(el);
  root.render(<Component {...props} />);
  const marker = new maplibregl.Marker({ element: el, anchor: "center" })
    .setLngLat(lngLat)
    .addTo(map);
  return { marker, root };
}

export function removeMarker(ref) {
  ref.current?.marker.remove();
  ref.current?.root.unmount();
  ref.current = null;
}

export function useMapMarker(map, Component, props, lngLat, options = {}) {
  const { className, onMount } = options;
  const ref = useRef(null);

  // Keep latest props/onMount in refs so the lifecycle effect can use them
  // without re-running when they change.
  const propsRef = useRef(props);
  propsRef.current = props;
  const onMountRef = useRef(onMount);
  onMountRef.current = onMount;

  const hasCoords = Array.isArray(lngLat) && lngLat.length === 2;

  // Lifecycle: create the marker when map + coords first become available,
  // destroy it when either is removed. Does NOT depend on lngLat values
  // themselves — position changes go through the position-update effect.
  useEffect(() => {
    if (!map || !hasCoords) return;

    const el = document.createElement("div");
    if (className) el.className = className;
    const root = ReactDOM.createRoot(el);
    root.render(<Component {...propsRef.current} />);
    const marker = new maplibregl.Marker({ element: el, anchor: "center" })
      .setLngLat(lngLat)
      .addTo(map);
    ref.current = { marker, root };
    onMountRef.current?.(marker);

    return () => {
      marker.remove();
      root.unmount();
      ref.current = null;
    };
    // Component/className are construction-time; props/onMount tracked via refs;
    // lngLat handled by the position effect below.
  }, [map, hasCoords]); // eslint-disable-line react-hooks/exhaustive-deps

  // Position updates — cheap setLngLat, no remount.
  const lng = hasCoords ? lngLat[0] : null;
  const lat = hasCoords ? lngLat[1] : null;
  useEffect(() => {
    if (ref.current && lng != null && lat != null) {
      ref.current.marker.setLngLat([lng, lat]);
    }
  }, [lng, lat]);

  // Props updates — re-render the React subtree. Runs every parent render;
  // React's reconciler no-ops when the rendered output hasn't changed.
  useEffect(() => {
    if (ref.current) {
      ref.current.root.render(<Component {...props} />);
    }
  });

  return ref;
}
