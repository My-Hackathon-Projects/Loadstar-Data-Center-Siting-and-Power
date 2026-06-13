import { Suspense, lazy } from "react";
import { Navigate, Route, Routes } from "react-router-dom";

// The journey route is the only place that imports three / @react-three/fiber.
// Lazy-loading it keeps those packages in a /-only chunk so the /app bundle
// never pays for the intro.
const CinematicEntry = lazy(() => import("./features/journey/CinematicEntry"));
const Dashboard = lazy(() => import("./features/dashboard/Dashboard"));
const BehindTheTech = lazy(() => import("./features/tech/BehindTheTech"));
const Outro = lazy(() => import("./features/thanks/Outro"));

function RouteFallback() {
  return <div className="min-h-screen bg-void" aria-hidden />;
}

export function App() {
  return (
    <Suspense fallback={<RouteFallback />}>
      <Routes>
        <Route path="/" element={<CinematicEntry />} />
        <Route path="/app" element={<Dashboard />} />
        <Route path="/tech" element={<BehindTheTech />} />
        <Route path="/thanks" element={<Outro />} />
        {/* Unknown paths fall back to the working dashboard, never a blank screen. */}
        <Route path="*" element={<Navigate replace to="/app" />} />
      </Routes>
    </Suspense>
  );
}
