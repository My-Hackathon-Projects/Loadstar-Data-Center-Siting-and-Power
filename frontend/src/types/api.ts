import type { components } from "./openapi";

type Schema<Name extends keyof components["schemas"]> =
  components["schemas"][Name];

export type ApiErrorDetail = Schema<"ApiErrorDetail">;
export type ApiErrorResponse = Schema<"ApiErrorResponse">;
export type AssumptionsResponse = Schema<"AssumptionsResponse">;
export type CompareRequest = Schema<"CompareRequest">;
export type CompareResponse = Schema<"CompareResponse">;
export type ExplainRequest = Schema<"ExplainRequest">;
export type ExplainResponse = Schema<"ExplainResponse">;
export type HealthDependencies = Schema<"HealthDependencies">;
export type HealthDependency = Schema<"HealthDependency">;
export type HealthResponse = Schema<"HealthResponse">;
export type LayerFeature = Schema<"LayerFeature">;
export type LayerFeatureProperties = Schema<"LayerFeatureProperties">;
export type LayerResponse = Schema<"LayerResponse">;
export type OptimizationJobAccepted = Schema<"OptimizationJobAccepted">;
export type OptimizationJobStatus = Schema<"OptimizationJobStatus">;
export type OptimizeRequest = Schema<"OptimizeRequest">;
export type ParetoPoint = Schema<"ParetoPoint">;
export type PointGeometry = Schema<"PointGeometry">;
export type RankedSite = Schema<"RankedSite">;
export type ScaleWarning = Schema<"ScaleWarning">;
export type ScoreExplanation = Schema<"ScoreExplanation">;
export type SearchRequest = Schema<"SearchRequest">;
export type SearchResponse = Schema<"SearchResponse">;
export type SiteDetailResponse = Schema<"SiteDetailResponse">;
export type SiteFeature = Schema<"SiteFeature">;
export type SourceArtifact = Schema<"SourceArtifact">;
export type SourceArtifactsResponse = Schema<"SourceArtifactsResponse">;
export type SupplyMixResponse = Schema<"SupplyMixResponse">;
export type Weights = Schema<"Weights">;

export type DispatchSummary = SupplyMixResponse["dispatch_summary"];
export type DispatchPreviewRow = SupplyMixResponse["dispatch_preview"][number];
