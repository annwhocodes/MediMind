
import { FC } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import Logo, { HomeLogo, DiagnosticsLogo, OperationsLogo, AskAILogo } from '../common/Logo';
import { useAuth } from '../../context/AuthContext';
import { LogOut, LogIn, User } from 'lucide-react';

// Navigation component
const Header: FC = () => {
  const location = useLocation();
  const navigate = useNavigate();
  const { user, logout } = useAuth();

  const isActive = (path: string) => location.pathname === path;

  // LIGHT THEME CLASSES
  const baseLinkClass = 'flex items-center space-x-2 text-gray-500 hover:text-blue-600 transition-colors duration-200';
  const activeLinkClass = 'text-blue-600 font-semibold border-b-2 border-blue-600 pb-0.5';

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  return (
    <header className="sticky top-0 z-50 w-full">
      {/* Light theme container: bg-white/90, border-gray-100 */}
      <div className="bg-white/90 backdrop-blur-md px-7 py-4 flex justify-between items-center shadow-md border-b border-gray-100">
        <Logo />

        <nav className="hidden md:flex items-center space-x-8 font-medium">
          <Link to="/" className={`${baseLinkClass} ${isActive('/') ? activeLinkClass : ''}`}>
            <HomeLogo className="w-5 h-5" />
            <span>Home</span>
          </Link>

          {user && (
            <Link to="/diagnostics" className={`${baseLinkClass} ${isActive('/diagnostics') ? activeLinkClass : ''}`}>
              <DiagnosticsLogo className="w-5 h-5" />
              <span>Diagnostics</span>
            </Link>
          )}

          {user && (
            <Link to="/ask" className={`${baseLinkClass} ${isActive('/ask') ? activeLinkClass : ''}`}>
              <AskAILogo className="w-5 h-5" />
              <span>Ask AI</span>
            </Link>
          )}

          {user && user.role === 'admin' && (
            <Link to="/operations" className={`${baseLinkClass} ${isActive('/operations') ? activeLinkClass : ''}`}>
              <OperationsLogo className="w-5 h-5" />
              <span>Operations</span>
            </Link>
          )}
        </nav>

        <div className="flex items-center gap-4">
          {user ? (
            // Light theme separators and text
            <div className="flex items-center gap-4 pl-6 border-l border-gray-200">
              <div className="flex items-center gap-2 text-gray-700">
                <User size={18} />
                <span className="text-sm font-medium">{user.username}</span>
                {user.role === 'admin' && (
                  <span className="text-[10px] bg-blue-50 text-blue-600 px-2 py-0.5 rounded-full border border-blue-100 uppercase tracking-wider font-bold">
                    Admin
                  </span>
                )}
              </div>
              <button
                onClick={handleLogout}
                className="p-2 text-gray-400 hover:text-red-500 transition-colors rounded-lg hover:bg-gray-100"
                title="Sign out"
              >
                <LogOut size={20} />
              </button>
            </div>
          ) : (
            <Link
              to="/login"
              className="flex items-center gap-2 px-5 py-2.5 bg-blue-600 hover:bg-blue-500 text-white rounded-xl font-medium transition-all shadow-lg shadow-blue-500/20 active:scale-95"
            >
              <LogIn size={18} />
              <span>Sign In</span>
            </Link>
          )}
        </div>
      </div>
    </header>
  );
};

export default Header;