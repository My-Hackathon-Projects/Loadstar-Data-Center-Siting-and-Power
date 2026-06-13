import { useCallback, useMemo, useRef } from "react";
import Map, { type MapRef } from "react-map-gl/maplibre";

import { darkBasemapStyle } from "../../map/darkBasemap";
import { EUROPE_VIEW, FLY_CHAIN, GLOBE_VIEW } from "../constants";

interface GlobeStageProps {
  /** Run the scripted flyTo descent. When false (reduced motion) the globe opens
   *  already settled on Europe with no camera animation. */
  animate: boolean;
}

/**
 * MapLibre globe (v5 globe projection) on the dark basemap. Mounts for the
 * arrival phase and stays mounted through the greeting so there is no remount
 * stutter at the handoff.
 */
export default function GlobeStage({ animate }: GlobeStageProps) {
  const mapRef = useRef<MapRef | null>(null);
  const style = useMemo(() => darkBasemapStyle({ globe: true }), []);

  const handleLoad = useCallback(() => {
    if (!animate) {
      return;
    }
    const map = mapRef.current?.getMap();
    if (!map) {
      return;
    }
    // Chain the descent: clouds-level, then Europe, then settle. Each leg fires
    // the next on moveend so the motion is continuous.
    let step = 0;
    const advance = () => {
      if (step >= FLY_CHAIN.length) {
        return;
      }
      const leg = FLY_CHAIN[step];
      step += 1;
      map.once("moveend", advance);
      map.flyTo({ ...leg, essential: true });
    };
    advance();
  }, [animate]);

  return (
    <Map
      attributionControl={false}
      initialViewState={animate ? GLOBE_VIEW : EUROPE_VIEW}
      interactive={false}
      mapStyle={style}
      onLoad={handleLoad}
      ref={mapRef}
      reuseMaps
      style={{ width: "100%", height: "100%" }}
    />
  );
}
