import { Navigate, Route, Routes } from 'react-router-dom';
import Home from './pages/Home';
import Scan from './pages/Scan';
import Results from './pages/Results';
import OrganizerDashboard from './pages/OrganizerDashboard';
import { useStore } from './store/useStore';

function RequireUser({ children }: { children: JSX.Element }) {
  const user = useStore((state) => state.user);
  return user ? children : <Navigate to="/" replace />;
}

function RequireProbe({ children }: { children: JSX.Element }) {
  const probeId = useStore((state) => state.probeId);
  return probeId ? children : <Navigate to="/scan" replace />;
}

function RequireOrganizer({ children }: { children: JSX.Element }) {
  const user = useStore((state) => state.user);
  return user?.scope === 'organizer' ? children : <Navigate to="/" replace />;
}

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Home />} />
      <Route
        path="/scan"
        element={
          <RequireUser>
            <Scan />
          </RequireUser>
        }
      />
      <Route
        path="/results"
        element={
          <RequireProbe>
            <Results />
          </RequireProbe>
        }
      />
      <Route
        path="/dashboard"
        element={
          <RequireOrganizer>
            <OrganizerDashboard />
          </RequireOrganizer>
        }
      />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
