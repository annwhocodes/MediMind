import { FC, useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { Heart, Activity, Mail, Lock, User, UserPlus, LogIn } from 'lucide-react';
import Logo from '../components/common/Logo';

const LoginPage: FC = () => {
  const { login } = useAuth();
  const navigate = useNavigate();
  
  const [isLoginView, setIsLoginView] = useState(true);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [name, setName] = useState('');
  const [role, setRole] = useState<'patient' | 'admin'>('patient');
  const [errorMsg, setErrorMsg] = useState('');

  // Initialize dummy databases if they don't exist
  useEffect(() => {
    if (!localStorage.getItem('medimind_users')) {
      localStorage.setItem('medimind_users', JSON.stringify([
        { email: 'admin@medimind.com', password: 'password', role: 'admin', name: 'System Admin' },
        { email: 'patient@example.com', password: 'password', role: 'patient', name: 'John Doe' }
      ]));
    }
  }, []);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMsg('');
    
    if (!email || !password || (!isLoginView && !name)) {
      setErrorMsg('Please fill in all required fields.');
      return;
    }

    const usersStr = localStorage.getItem('medimind_users') || '[]';
    const users = JSON.parse(usersStr);

    if (isLoginView) {
      // Handle Login
      const user = users.find((u: any) => u.email.toLowerCase() === email.toLowerCase() && u.password === password);
      if (user) {
        login(user.role);
        navigate('/');
      } else {
        setErrorMsg('Invalid email or password.');
      }
    } else {
      // Handle Sign Up
      const userExists = users.some((u: any) => u.email.toLowerCase() === email.toLowerCase());
      if (userExists) {
        setErrorMsg('User with this email already exists.');
        return;
      }
      
      const newUser = { email, password, name, role };
      users.push(newUser);
      localStorage.setItem('medimind_users', JSON.stringify(users));
      
      login(role);
      navigate('/');
    }
  };

  return (
    <div className="min-h-screen bg-blue-50 flex flex-col items-center justify-center p-4">
      <div className="max-w-md w-full bg-white rounded-2xl shadow-xl p-10 relative overflow-hidden">
        {/* Top header accent */}
        <div className="absolute top-0 left-0 w-full h-2 bg-gradient-to-r from-blue-500 to-indigo-600"></div>
        
        <div className="flex flex-col items-center text-center mb-8">
           <div className="mb-6">
             <Logo />
           </div>
           <h1 className="text-2xl font-bold text-gray-800 tracking-tight">
             {isLoginView ? 'Welcome back' : 'Create your account'}
           </h1>
           <p className="text-sm text-gray-500 mt-2">
             {isLoginView ? 'Sign in to access your portal' : 'Enroll in the medical system'}
           </p>
        </div>

        {errorMsg && (
          <div className="mb-6 p-3 bg-red-50 text-red-700 text-sm rounded border border-red-200">
            {errorMsg}
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          {!isLoginView && (
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Full Name</label>
              <div className="relative">
                <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                  <User className="h-5 w-5 text-gray-400" />
                </div>
                <input
                  type="text"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  className="pl-10 w-full max-w-full block border-gray-300 rounded-lg border focus:ring-blue-500 focus:border-blue-500 p-2.5 outline-none"
                  placeholder="John Doe"
                />
              </div>
            </div>
          )}

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Email Address</label>
            <div className="relative">
              <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                <Mail className="h-5 w-5 text-gray-400" />
              </div>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="pl-10 w-full max-w-full block border-gray-300 rounded-lg border focus:ring-blue-500 focus:border-blue-500 p-2.5 outline-none"
                placeholder="you@example.com"
              />
            </div>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Password</label>
            <div className="relative">
              <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                <Lock className="h-5 w-5 text-gray-400" />
              </div>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="pl-10 w-full max-w-full block border-gray-300 rounded-lg border focus:ring-blue-500 focus:border-blue-500 p-2.5 outline-none"
                placeholder="••••••••"
              />
            </div>
          </div>

          {!isLoginView && (
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Account Type</label>
              <div className="grid grid-cols-2 gap-4 mt-2">
                <div 
                  onClick={() => setRole('patient')}
                  className={`cursor-pointer border rounded-lg p-3 flex flex-col items-center justify-center space-y-2 transition-all ${role === 'patient' ? 'bg-blue-50 border-blue-500 shadow-sm' : 'hover:bg-gray-50'}`}
                >
                  <Heart className={`w-6 h-6 ${role === 'patient' ? 'text-blue-600' : 'text-gray-400'}`} />
                  <span className={`text-sm font-medium ${role === 'patient' ? 'text-blue-700' : 'text-gray-600'}`}>Patient</span>
                </div>
                <div 
                  onClick={() => setRole('admin')}
                  className={`cursor-pointer border rounded-lg p-3 flex flex-col items-center justify-center space-y-2 transition-all ${role === 'admin' ? 'bg-indigo-50 border-indigo-500 shadow-sm' : 'hover:bg-gray-50'}`}
                >
                  <Activity className={`w-6 h-6 ${role === 'admin' ? 'text-indigo-600' : 'text-gray-400'}`} />
                  <span className={`text-sm font-medium ${role === 'admin' ? 'text-indigo-700' : 'text-gray-600'}`}>Hospital Staff</span>
                </div>
              </div>
            </div>
          )}

          <button
            type="submit"
            className="mt-6 w-full flex items-center justify-center space-x-2 bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-700 hover:to-indigo-700 text-white p-3 rounded-xl font-medium transition-all duration-200 shadow-md"
          >
            {isLoginView ? <LogIn className="w-5 h-5" /> : <UserPlus className="w-5 h-5" />}
            <span>{isLoginView ? 'Sign In' : 'Create Account'}</span>
          </button>
        </form>

        <div className="mt-6 text-center text-sm text-gray-600">
          {isLoginView ? (
            <p>
              Don't have an account?{' '}
              <button 
                onClick={() => { setIsLoginView(false); setErrorMsg(''); }}
                className="text-blue-600 font-semibold hover:underline"
              >
                Sign up
              </button>
            </p>
          ) : (
            <p>
              Already have an account?{' '}
              <button 
                onClick={() => { setIsLoginView(true); setErrorMsg(''); }}
                className="text-blue-600 font-semibold hover:underline"
              >
                Log in
              </button>
            </p>
          )}
        </div>
        
        <div className="mt-8 pt-6 border-t border-gray-100 text-center">
            <p className="text-xs text-gray-400">Secure AES-256 Encrypted Portal</p>
        </div>
      </div>
    </div>
  );
};

export default LoginPage;
