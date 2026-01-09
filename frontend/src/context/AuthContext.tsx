
import React, { createContext, useContext, useState, useEffect } from 'react';
import axios from 'axios';

interface AuthContextType {
    user: { username: string; role: string } | null;
    token: string | null;
    login: (token: string, role: string, username: string) => void;
    logout: () => void;
    isLoading: boolean;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
    const [user, setUser] = useState<{ username: string; role: string } | null>(null);
    const [token, setToken] = useState<string | null>(localStorage.getItem('token'));
    const [isLoading, setIsLoading] = useState(true);

    useEffect(() => {
        const storedToken = localStorage.getItem('token');
        const storedRole = localStorage.getItem('role');
        const storedUsername = localStorage.getItem('username');

        if (storedToken && storedRole && storedUsername) {
            setUser({ username: storedUsername, role: storedRole });
            setToken(storedToken);
            // Set default header
            axios.defaults.headers.common['Authorization'] = `Bearer ${storedToken}`;
        }
        setIsLoading(false);
    }, []);

    const login = (newToken: string, newRole: string, newUsername: string) => {
        localStorage.setItem('token', newToken);
        localStorage.setItem('role', newRole);
        localStorage.setItem('username', newUsername);

        setToken(newToken);
        setUser({ username: newUsername, role: newRole });

        // Set axios header
        axios.defaults.headers.common['Authorization'] = `Bearer ${newToken}`;
    };

    const logout = () => {
        localStorage.removeItem('token');
        localStorage.removeItem('role');
        localStorage.removeItem('username');

        setToken(null);
        setUser(null);

        delete axios.defaults.headers.common['Authorization'];
    };

    return (
        <AuthContext.Provider value={{ user, token, login, logout, isLoading }}>
            {children}
        </AuthContext.Provider>
    );
};

export const useAuth = () => {
    const context = useContext(AuthContext);
    if (!context) {
        throw new Error('useAuth must be used within an AuthProvider');
    }
    return context;
};
