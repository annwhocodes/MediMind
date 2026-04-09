import React, { createContext, useContext, useState, ReactNode } from 'react';

type Role = 'patient' | 'admin' | null;

interface AuthContextType {
  role: Role;
  login: (role: Role) => void;
  logout: () => void;
}

const AuthContext = createContext<AuthContextType>({} as AuthContextType);

export const AuthProvider: React.FC<{children: ReactNode}> = ({ children }) => {
  // Check local storage for initial state to persist login across reloads
  const [role, setRoleState] = useState<Role>(() => {
    const saved = localStorage.getItem('medimind_role');
    return (saved === 'patient' || saved === 'admin') ? saved : null;
  });

  const setRole = (newRole: Role) => {
    setRoleState(newRole);
    if (newRole) {
      localStorage.setItem('medimind_role', newRole);
    } else {
      localStorage.removeItem('medimind_role');
    }
  };

  return (
    <AuthContext.Provider value={{ role, login: setRole, logout: () => setRole(null) }}>
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => useContext(AuthContext);
