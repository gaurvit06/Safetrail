import { lazy, Suspense } from "react";
import { Navigate, Route, Routes, useParams } from "react-router-dom";
import { Spinner } from "./components/ui";
import FamilyView from "./pages/FamilyView";
import JudgeJoin from "./pages/JudgeJoin";
import Prepare from "./pages/Prepare";
import TripHome from "./pages/TripHome";
import TripSetup from "./pages/TripSetup";
import Welcome from "./pages/Welcome";

const Responder = lazy(() => import("./pages/Responder"));
const Stage = lazy(() => import("./pages/Stage"));
const StageControl = lazy(() => import("./pages/StageControl"));
const BreakIt = lazy(() => import("./pages/BreakIt"));
const Benchmark = lazy(() => import("./pages/Benchmark"));

function CheckpointRedirect() {
  const { id } = useParams();
  return <Navigate to={`/t?cp=${encodeURIComponent(id ?? "")}`} replace />;
}

export default function App() {
  return (
    <Suspense fallback={<div className="grid h-full place-items-center"><Spinner size={28} /></div>}>
      <Routes>
        <Route path="/" element={<Welcome />} />
        <Route path="/t/new" element={<TripSetup />} />
        <Route path="/t/prepare" element={<Prepare />} />
        <Route path="/t" element={<TripHome />} />
        <Route path="/j" element={<JudgeJoin />} />
        <Route path="/c/:id" element={<CheckpointRedirect />} />
        <Route path="/f/:token" element={<FamilyView />} />
        <Route path="/r" element={<Responder />} />
        <Route path="/jr" element={<Responder simple />} />
        <Route path="/stage" element={<Stage />} />
        <Route path="/stage/control" element={<StageControl />} />
        <Route path="/stage/break" element={<BreakIt />} />
        <Route path="/break" element={<BreakIt />} />
        <Route path="/benchmark" element={<Benchmark />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </Suspense>
  );
}
