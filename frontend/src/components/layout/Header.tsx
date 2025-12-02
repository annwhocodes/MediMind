import { FC } from 'react';
import { Link, useLocation } from 'react-router-dom';
import Logo, { HomeLogo, DiagnosticsLogo, OperationsLogo, AskAILogo } from '../common/Logo';

// Navigation component
const Header: FC = () => {
  const location = useLocation();
  const isActive = (path: string) => location.pathname === path;

  const baseLinkClass = 'flex items-center space-x-2 text-gray-700 hover:text-blue-600 transition-colors duration-200';
  const activeLinkClass = 'text-blue-600 font-semibold border-b-2 border-blue-600';
  
  return (
    <header>
      <div className="bg-white p-4 px-7 flex justify-between items-center shadow-md rounded-lg mb-5">
        <Logo />
        
        <nav className="flex space-x-6 font-medium">
          <Link to="/" className={`${baseLinkClass} ${isActive('/') ? activeLinkClass : ''}`}>
            <HomeLogo className="w-5 h-5" />
            <span>Home</span>
          </Link>
          <Link to="/diagnostics" className={`${baseLinkClass} ${isActive('/diagnostics') ? activeLinkClass : ''}`}>
            <DiagnosticsLogo className="w-5 h-5" />
            <span>Diagnostics</span>
          </Link>
          <Link to="/operations" className={`${baseLinkClass} ${isActive('/operations') ? activeLinkClass : ''}`}>
            <OperationsLogo className="w-5 h-5" />
            <span>Hospital Operations</span>
          </Link>
          <Link to="/ask" className={`${baseLinkClass} ${isActive('/ask') ? activeLinkClass : ''}`}>
            <AskAILogo className="w-5 h-5" />
            <span>AskAI</span>
          </Link>
        </nav>
      </div>
    </header>
  );
};

export default Header;