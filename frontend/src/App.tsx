import { Routes, Route } from 'react-router-dom';
import HomePage from './pages/HomePage';
import Diagnostics from './pages/Diagnostics';
import AskAIPage from './pages/AskAIPage';
import HospitaOperationsPage from './pages/HospitalOperationsPage';
import LoginPage from './pages/LoginPage';
import RegisterPage from './pages/RegisterPage';
import { AuthProvider } from './context/AuthContext';
import ProtectedRoute from './components/ProtectedRoute';

function App() {
  return (
    <AuthProvider>
      <Routes>
        {/* Public Routes */}
        <Route path="/" element={<HomePage />} />
        <Route path="/login" element={<LoginPage />} />
        <Route path="/register" element={<RegisterPage />} />

        {/* Protected Routes (Authenticated Users) */}
        <Route element={<ProtectedRoute />}>
          <Route path="/diagnostics" element={<Diagnostics />} />
          <Route path="/ask" element={<AskAIPage />} />
        </Route>

        {/* Admin Routes */}
        <Route element={<ProtectedRoute allowedRoles={['admin']} />}>
          <Route path="/operations" element={<HospitaOperationsPage />} />
        </Route>
      </Routes>
    </AuthProvider>
  );
}

export default App;
