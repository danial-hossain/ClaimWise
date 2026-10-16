'use client';

import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';
import {
  AuthUser,
  LoginPayload,
  SignUpPayload,
} from '@/types/api';
import {
  loginUser,
  signupUser,
  demoLoginUser,
  fetchCurrentUser,
  logoutUser,
  getStoredAuthToken,
} from '@/lib/api';

interface AuthContextType {
  user: AuthUser | null;
  token: string | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  isAuthModalOpen: boolean;
  authModalTab: 'login' | 'signup';
  openAuthModal: (tab?: 'login' | 'signup') => void;
  closeAuthModal: () => void;
  login: (payload: LoginPayload) => Promise<{ success: boolean; error?: string }>;
  signup: (payload: SignUpPayload) => Promise<{ success: boolean; error?: string }>;
  demoLogin: (role: 'policyholder' | 'broker' | 'advocate') => Promise<{ success: boolean; error?: string }>;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isAuthModalOpen, setIsAuthModalOpen] = useState(false);
  const [authModalTab, setAuthModalTab] = useState<'login' | 'signup'>('login');

  useEffect(() => {
    let isMounted = true;

    const restoreSession = async () => {
      // Actively purge any legacy token in localStorage
      getStoredAuthToken();
      try {
        const res = await fetchCurrentUser();
        if (isMounted) {
          setUser(res.data);
        }
      } catch {
        if (isMounted) {
          setUser(null);
        }
      } finally {
        if (isMounted) {
          setIsLoading(false);
        }
      }
    };

    // eslint-disable-next-line react-hooks/set-state-in-effect
    restoreSession();

    const handleProfileUpdated = () => {
      restoreSession();
    };

    window.addEventListener('claimwise_profile_updated', handleProfileUpdated);
    return () => {
      isMounted = false;
      window.removeEventListener('claimwise_profile_updated', handleProfileUpdated);
    };
  }, []);

  const openAuthModal = useCallback((tab: 'login' | 'signup' = 'login') => {
    setAuthModalTab(tab);
    setIsAuthModalOpen(true);
  }, []);

  const closeAuthModal = useCallback(() => {
    setIsAuthModalOpen(false);
  }, []);

  const handleLogin = async (payload: LoginPayload) => {
    const res = await loginUser(payload);
    if (res.data) {
      setUser(res.data.user);
      setIsAuthModalOpen(false);
      return { success: true };
    }
    return { success: false, error: res.error || 'Login failed' };
  };

  const handleSignup = async (payload: SignUpPayload) => {
    const res = await signupUser(payload);
    if (res.data) {
      setUser(res.data.user);
      setIsAuthModalOpen(false);
      return { success: true };
    }
    return { success: false, error: res.error || 'Signup failed' };
  };

  const handleDemoLogin = async (role: 'policyholder' | 'broker' | 'advocate') => {
    const res = await demoLoginUser({ role });
    if (res.data) {
      setUser(res.data.user);
      setIsAuthModalOpen(false);
      return { success: true };
    }
    return { success: false, error: res.error || 'Demo sign in failed' };
  };

  const handleLogout = async () => {
    await logoutUser();
    setUser(null);
    setToken(null);
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        token,
        isAuthenticated: !!user,
        isLoading,
        isAuthModalOpen,
        authModalTab,
        openAuthModal,
        closeAuthModal,
        login: handleLogin,
        signup: handleSignup,
        demoLogin: handleDemoLogin,
        logout: handleLogout,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}
