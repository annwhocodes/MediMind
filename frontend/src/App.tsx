import { Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider, useAuth } from './contexts/AuthContext';
import LoginPage from './pages/LoginPage';
import HomePage from './pages/HomePage';
import Diagnostics from './pages/Diagnostics';
import AskAIPage from './pages/AskAIPage';
import HospitaOperationsPage from './pages/HospitalOperationsPage';

const ProtectedRoute = ({ children, allowedRoles }: { children: JSX.Element, allowedRoles: ('patient' | 'admin')[] }) => {
  const { role } = useAuth();
  
  if (!role) {
    return <Navigate to="/login" replace />;
  }
  
  if (!allowedRoles.includes(role)) {
    return <Navigate to="/" replace />;
  }
  
  return children;
};

function AppRoutes() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/" element={<ProtectedRoute allowedRoles={['patient', 'admin']}><HomePage /></ProtectedRoute>} />
      <Route path="/diagnostics" element={<ProtectedRoute allowedRoles={['patient', 'admin']}><Diagnostics /></ProtectedRoute>} />
      <Route path="/ask" element={<ProtectedRoute allowedRoles={['patient', 'admin']}><AskAIPage /></ProtectedRoute>} />
      <Route path="/operations" element={<ProtectedRoute allowedRoles={['admin']}><HospitaOperationsPage /></ProtectedRoute>} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}

function App() {
  return (
    <AuthProvider>
      <AppRoutes />
    </AuthProvider>
  );
}

export default App;
