import { Routes, Route } from 'react-router-dom';
import HomePage from './pages/HomePage';
import Diagnostics from './pages/Diagnostics';
import AskAIPage from './pages/AskAIPage';
import HospitaOperationsPage from './pages/HospitalOperationsPage';

function App() {
  return (
    <Routes>
      <Route path="/" element={<HomePage />} />
      <Route path="/diagnostics" element={<Diagnostics />} />
      <Route path="/ask" element={<AskAIPage />} />
      <Route path="/operations" element={<HospitaOperationsPage />} />
    </Routes>
    
  );
}

export default App;
