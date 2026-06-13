import type { LayerResponse } from "../types/api";
import { requestJson } from "./client";

/** GET `/layers/{layerName}` and return a GeoJSON map layer. */
export function getLayer(layerName: string): Promise<LayerResponse> {
  return requestJson<LayerResponse>(`/layers/${layerName}`);
}
