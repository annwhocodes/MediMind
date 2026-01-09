
import React, { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import axios from 'axios';
import { Lock, User, AlertCircle, ArrowRight } from 'lucide-react';
import Header from '../components/layout/Header';
import Footer from '../components/layout/Footer';

const LoginPage = () => {
    const [username, setUsername] = useState('');
    const [password, setPassword] = useState('');
    const [error, setError] = useState('');
    const [loading, setLoading] = useState(false);

    const { login } = useAuth();
    const navigate = useNavigate();

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        setLoading(true);
        setError('');

        try {
            // Use form data as requested by OAuth2PasswordRequestForm
            const formData = new FormData();
            formData.append('username', username);
            formData.append('password', password);

            const response = await axios.post('http://localhost:8001/auth/login', formData, {
                headers: { 'Content-Type': 'multipart/form-data' }
            });

            const { access_token, role } = response.data;
            login(access_token, role, username);

            // Redirect based on role
            if (role === 'admin') {
                navigate('/operations');
            } else {
                navigate('/diagnostics'); // or /analyze
            }
        } catch (err: any) {
            console.error(err);
            setError(err.response?.data?.detail || 'Login failed. Please check your credentials.');
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="min-h-screen bg-blue-50 flex flex-col">
            <Header />

            <div className="flex-grow flex items-center justify-center p-4">
                <div className="w-full max-w-md bg-white p-8 rounded-2xl shadow-xl border border-blue-100">
                    <div className="text-center mb-8">
                        <h1 className="text-3xl font-bold text-gray-800">
                            Welcome Back
                        </h1>
                        <p className="text-gray-500 mt-2">Sign in to access MediMind AI</p>
                    </div>

                    {error && (
                        <div className="mb-6 p-4 bg-red-50 border border-red-200 rounded-xl flex items-center gap-3 text-red-600 text-sm">
                            <AlertCircle size={18} />
                            {error}
                        </div>
                    )}

                    <form onSubmit={handleSubmit} className="space-y-6">
                        <div className="space-y-2">
                            <label className="text-sm font-medium text-gray-700 ml-1">Username</label>
                            <div className="relative group">
                                <User className="absolute left-4 top-3.5 text-gray-400 group-focus-within:text-blue-600 transition-colors" size={20} />
                                <input
                                    type="text"
                                    value={username}
                                    onChange={(e) => setUsername(e.target.value)}
                                    className="w-full bg-gray-50 border border-gray-200 rounded-xl py-3 pl-12 pr-4 text-gray-800 focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500 transition-all placeholder:text-gray-400"
                                    placeholder="Enter your username"
                                    required
                                />
                            </div>
                        </div>

                        <div className="space-y-2">
                            <label className="text-sm font-medium text-gray-700 ml-1">Password</label>
                            <div className="relative group">
                                <Lock className="absolute left-4 top-3.5 text-gray-400 group-focus-within:text-blue-600 transition-colors" size={20} />
                                <input
                                    type="password"
                                    value={password}
                                    onChange={(e) => setPassword(e.target.value)}
                                    className="w-full bg-gray-50 border border-gray-200 rounded-xl py-3 pl-12 pr-4 text-gray-800 focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500 transition-all placeholder:text-gray-400"
                                    placeholder="••••••••"
                                    required
                                />
                            </div>
                        </div>

                        <button
                            type="submit"
                            disabled={loading}
                            className="w-full bg-gradient-to-r from-blue-600 to-violet-600 hover:from-blue-700 hover:to-violet-700 text-white font-semibold py-3.5 rounded-xl transition-all shadow-lg shadow-blue-500/30 active:scale-[0.98] flex items-center justify-center gap-2 group"
                        >
                            {loading ? (
                                <div className="w-5 h-5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                            ) : (
                                <>
                                    Sign In
                                    <ArrowRight size={18} className="group-hover:translate-x-1 transition-transform" />
                                </>
                            )}
                        </button>
                    </form>

                    <div className="mt-6 text-center">
                        <p className="text-gray-500 text-sm">
                            Don't have an account?{' '}
                            <Link to="/register" className="text-blue-600 hover:text-blue-700 font-medium transition-colors">
                                Sign up
                            </Link>
                        </p>
                    </div>
                </div>
            </div>

            <div className="px-8">
                <Footer />
            </div>
        </div>
    );
};

export default LoginPage;
