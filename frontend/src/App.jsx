import { Navigate, Route, Routes } from 'react-router-dom';
import Layout from './components/Layout.jsx';
import ProtectedRoute from './components/ProtectedRoute.jsx';
import Login from './pages/Login.jsx';
import Dashboard from './pages/Dashboard.jsx';
import Vehicles from './pages/Vehicles.jsx';
import People from './pages/People.jsx';
import AccessLogs from './pages/AccessLogs.jsx';
import Devices from './pages/Devices.jsx';
import Users from './pages/Users.jsx';
import OcrTester from './pages/OcrTester.jsx';

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route
        element={
          <ProtectedRoute>
            <Layout />
          </ProtectedRoute>
        }
      >
        <Route index element={<Dashboard />} />
        <Route path="vehicles" element={<Vehicles />} />
        <Route path="people" element={<People />} />
        <Route path="logs" element={<AccessLogs />} />
        <Route
          path="devices"
          element={
            <ProtectedRoute adminOnly>
              <Devices />
            </ProtectedRoute>
          }
        />
        <Route
          path="users"
          element={
            <ProtectedRoute adminOnly>
              <Users />
            </ProtectedRoute>
          }
        />
        <Route path="ocr" element={<OcrTester />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
