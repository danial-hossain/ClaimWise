'use client';

import React, { useState, useEffect } from 'react';
import { usePathname, useRouter } from 'next/navigation';
import { useAuth } from '@/context/AuthContext';
import LogoMark from '@/components/LogoMark';
import {
  X,
  Mail,
  Lock,
  User,
  Eye,
  EyeOff,
  RefreshCw,
  AlertCircle,
  CheckCircle2,
  Phone,
  Globe,
  Briefcase,
  Building2,
  GraduationCap,
} from 'lucide-react';

interface AuthModalProps {
  isOpen?: boolean;
  onClose?: () => void;
  defaultTab?: 'login' | 'signup';
}

function AuthModalContent({
  isOpen: propIsOpen,
  onClose: propOnClose,
  defaultTab: propDefaultTab,
}: AuthModalProps) {
  const router = useRouter();
  const pathname = usePathname();
  const {
    isAuthModalOpen,
    authModalTab,
    closeAuthModal,
    login,
    signup,
  } = useAuth();

  // Support controlled or context-driven state
  const isOpen = propIsOpen !== undefined ? propIsOpen : isAuthModalOpen;
  const handleClose = propOnClose || closeAuthModal;

  const [tab, setTab] = useState<'login' | 'signup'>(propDefaultTab || authModalTab || 'login');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [fullName, setFullName] = useState('');
  const [phoneNumber, setPhoneNumber] = useState('');
  const [country, setCountry] = useState('United States');
  const [occupationStatus, setOccupationStatus] = useState<'student' | 'employee' | 'self_employed' | 'other'>('student');
  const [organization, setOrganization] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  // Handle ESC key press
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && isOpen) {
        handleClose();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, handleClose]);

  if (!isOpen) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setSuccessMsg(null);
    setIsLoading(true);

    try {
      if (tab === 'login') {
        const res = await login({ email, password });
        if (!res.success) {
          setError(res.error || 'Invalid credentials');
        } else {
          setSuccessMsg('Signed in successfully. Your workspace is ready.');
          setTimeout(() => {
            handleClose();
            if (['/', '/login', '/signup'].includes(pathname)) router.replace('/dashboard');
            else router.refresh();
          }, 500);
        }
      } else {
        const res = await signup({
          email,
          password,
          full_name: fullName,
          role: 'policyholder',
          phone_number: phoneNumber || undefined,
          country: country || undefined,
          occupation_status: occupationStatus,
          organization: organization || undefined,
        });
        if (!res.success) {
          setError(res.error || 'Failed to create account');
        } else {
          setSuccessMsg('Account created successfully. Your workspace is ready.');
          setTimeout(() => {
            handleClose();
            if (['/', '/login', '/signup'].includes(pathname)) router.replace('/dashboard');
            else router.refresh();
          }, 500);
        }
      }
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Authentication failed');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 backdrop-blur-xs p-4 animate-in fade-in duration-200"
      onClick={(e) => {
        if (e.target === e.currentTarget) handleClose();
      }}
      role="dialog"
      aria-modal="true"
      aria-labelledby="auth-modal-title"
    >
      <div className="w-full max-w-lg rounded-2xl border border-slate-200 bg-white p-6 sm:p-7 shadow-2xl relative space-y-5 animate-in zoom-in-95 duration-150 cw-glass">
        {/* Close Button */}
        <button
          type="button"
          onClick={handleClose}
          className="absolute top-4 right-4 rounded-lg p-1.5 text-slate-400 hover:bg-slate-100 hover:text-slate-700 transition-colors cursor-pointer"
          aria-label="Close modal"
        >
          <X className="h-4 w-4" />
        </button>

        {/* Modal Header */}
        <div className="text-center space-y-1.5 pt-1">
          <LogoMark className="mx-auto mb-2 h-10 w-10" />
          <h2 id="auth-modal-title" className="text-lg font-bold tracking-tight text-slate-900">
            {tab === 'login' ? 'Sign in to ClaimWise' : 'Create your account'}
          </h2>
          <p className="text-xs text-slate-500 max-w-xs mx-auto">
            {tab === 'login'
              ? 'Access evidence-grounded policy verification and claims management'
              : 'Join ClaimWise for tamper-evident policy intelligence'}
          </p>
        </div>

        {/* Segmented Tab Switcher */}
        <div className="grid grid-cols-2 rounded-lg bg-slate-100 p-1 text-xs font-semibold">
          <button
            type="button"
            onClick={() => {
              setTab('login');
              setError(null);
            }}
            className={`rounded-md py-1.5 transition-colors cursor-pointer ${
              tab === 'login'
                ? 'bg-white text-slate-900 shadow-xs font-semibold'
                : 'text-slate-500 hover:text-slate-800'
            }`}
          >
            Sign In
          </button>
          <button
            type="button"
            onClick={() => {
              setTab('signup');
              setError(null);
            }}
            className={`rounded-md py-1.5 transition-colors cursor-pointer ${
              tab === 'signup'
                ? 'bg-white text-slate-900 shadow-xs font-semibold'
                : 'text-slate-500 hover:text-slate-800'
            }`}
          >
            Create Account
          </button>
        </div>

        {/* Error or Success Notice */}
        {error && (
          <div className="rounded-lg bg-rose-50 border border-rose-200 p-3 text-xs text-rose-700 flex items-start gap-2">
            <AlertCircle className="h-4 w-4 shrink-0 mt-0.5 text-rose-600" />
            <p className="leading-relaxed">{error}</p>
          </div>
        )}

        {successMsg && (
          <div className="rounded-lg bg-emerald-50 border border-emerald-200 p-3 text-xs text-emerald-700 flex items-center gap-2">
            <CheckCircle2 className="h-4 w-4 shrink-0 text-emerald-600" />
            <span>{successMsg}</span>
          </div>
        )}

        {/* Credentials Form */}
        <form onSubmit={handleSubmit} className="space-y-3.5">
          {tab === 'signup' && (
            <div>
              <label className="block text-[11px] font-medium text-slate-700 uppercase tracking-wider mb-1">
                Full Name
              </label>
              <div className="relative">
                <User className="absolute left-3 top-2.5 h-4 w-4 text-slate-400" />
                <input
                  type="text"
                  required
                  value={fullName}
                  onChange={(e) => setFullName(e.target.value)}
                  placeholder="e.g. Alex Morgan"
                  className="w-full rounded-lg border border-slate-300 bg-white pl-9 pr-3 py-2 text-xs text-slate-900 focus:border-teal-600 focus:outline-none focus:ring-1 focus:ring-teal-600"
                />
              </div>
            </div>
          )}

          <div>
            <label className="block text-[11px] font-medium text-slate-700 uppercase tracking-wider mb-1">
              Email Address
            </label>
            <div className="relative">
              <Mail className="absolute left-3 top-2.5 h-4 w-4 text-slate-400" />
              <input
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="name@example.com"
                className="w-full rounded-lg border border-slate-300 bg-white pl-9 pr-3 py-2 text-xs text-slate-900 focus:border-teal-600 focus:outline-none focus:ring-1 focus:ring-teal-600"
              />
            </div>
          </div>

          {tab === 'signup' && (
            <>
              {/* Phone & Country Grid */}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div>
                  <label className="block text-[11px] font-medium text-slate-700 uppercase tracking-wider mb-1">
                    Phone Number
                  </label>
                  <div className="relative">
                    <Phone className="absolute left-3 top-2.5 h-4 w-4 text-slate-400" />
                    <input
                      type="tel"
                      value={phoneNumber}
                      onChange={(e) => setPhoneNumber(e.target.value)}
                      placeholder="+1 (555) 000-0000"
                      className="w-full rounded-lg border border-slate-300 bg-white pl-9 pr-3 py-2 text-xs text-slate-900 focus:border-teal-600 focus:outline-none focus:ring-1 focus:ring-teal-600"
                    />
                  </div>
                </div>

                <div>
                  <label className="block text-[11px] font-medium text-slate-700 uppercase tracking-wider mb-1">
                    Country
                  </label>
                  <div className="relative">
                    <Globe className="absolute left-3 top-2.5 h-4 w-4 text-slate-400 pointer-events-none" />
                    <select
                      value={country}
                      onChange={(e) => setCountry(e.target.value)}
                      className="w-full rounded-lg border border-slate-300 bg-white pl-9 pr-3 py-2 text-xs text-slate-900 focus:border-teal-600 focus:outline-none focus:ring-1 focus:ring-teal-600 cursor-pointer"
                    >
                      <option value="United States">United States</option>
                      <option value="Canada">Canada</option>
                      <option value="United Kingdom">United Kingdom</option>
                      <option value="Australia">Australia</option>
                      <option value="Germany">Germany</option>
                      <option value="France">France</option>
                      <option value="Bangladesh">Bangladesh</option>
                      <option value="India">India</option>
                      <option value="Singapore">Singapore</option>
                      <option value="Japan">Japan</option>
                      <option value="Other">Other</option>
                    </select>
                  </div>
                </div>
              </div>

              {/* Status & Organization Grid */}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div>
                  <label className="block text-[11px] font-medium text-slate-700 uppercase tracking-wider mb-1">
                    Status / Occupation
                  </label>
                  <div className="relative">
                    {occupationStatus === 'student' ? (
                      <GraduationCap className="absolute left-3 top-2.5 h-4 w-4 text-slate-400 pointer-events-none" />
                    ) : (
                      <Briefcase className="absolute left-3 top-2.5 h-4 w-4 text-slate-400 pointer-events-none" />
                    )}
                    <select
                      value={occupationStatus}
                      onChange={(e) => setOccupationStatus(e.target.value as 'student' | 'employee' | 'self_employed' | 'other')}
                      className="w-full rounded-lg border border-slate-300 bg-white pl-9 pr-3 py-2 text-xs text-slate-900 focus:border-teal-600 focus:outline-none focus:ring-1 focus:ring-teal-600 cursor-pointer"
                    >
                      <option value="student">Student</option>
                      <option value="employee">Employee / Employed</option>
                      <option value="self_employed">Self-Employed</option>
                      <option value="other">Other</option>
                    </select>
                  </div>
                </div>

                <div>
                  <label className="block text-[11px] font-medium text-slate-700 uppercase tracking-wider mb-1">
                    {occupationStatus === 'student'
                      ? 'School / University'
                      : occupationStatus === 'employee'
                      ? 'Employer / Company'
                      : 'Organization'}
                  </label>
                  <div className="relative">
                    <Building2 className="absolute left-3 top-2.5 h-4 w-4 text-slate-400" />
                    <input
                      type="text"
                      value={organization}
                      onChange={(e) => setOrganization(e.target.value)}
                      placeholder={
                        occupationStatus === 'student'
                          ? 'e.g. Stanford University'
                          : occupationStatus === 'employee'
                          ? 'e.g. Acme Health'
                          : 'e.g. Organization Name'
                      }
                      className="w-full rounded-lg border border-slate-300 bg-white pl-9 pr-3 py-2 text-xs text-slate-900 focus:border-teal-600 focus:outline-none focus:ring-1 focus:ring-teal-600"
                    />
                  </div>
                </div>
              </div>
            </>
          )}

          <div>
            <label className="block text-[11px] font-medium text-slate-700 uppercase tracking-wider mb-1">
              Password
            </label>
            <div className="relative">
              <Lock className="absolute left-3 top-2.5 h-4 w-4 text-slate-400" />
              <input
                type={showPassword ? 'text' : 'password'}
                required
                minLength={6}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="Minimum 6 characters"
                className="w-full rounded-lg border border-slate-300 bg-white pl-9 pr-9 py-2 text-xs text-slate-900 focus:border-teal-600 focus:outline-none focus:ring-1 focus:ring-teal-600"
              />
              <button
                type="button"
                onClick={() => setShowPassword(!showPassword)}
                className="absolute right-2.5 top-2.5 text-slate-400 hover:text-slate-600 cursor-pointer"
                aria-label="Toggle password visibility"
              >
                {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
              </button>
            </div>
          </div>


          <button
            type="submit"
            disabled={isLoading}
            className="w-full mt-2 inline-flex items-center justify-center gap-2 rounded-lg bg-teal-700 hover:bg-teal-800 disabled:opacity-50 text-white text-xs font-semibold py-2.5 transition-colors cursor-pointer shadow-xs"
          >
            {isLoading ? (
              <>
                <RefreshCw className="h-3.5 w-3.5 animate-spin" />
                <span>Authenticating...</span>
              </>
            ) : (
              <span>{tab === 'login' ? 'Sign In' : 'Create Account'}</span>
            )}
          </button>
        </form>

        {/* Compliance Footer */}
        <div className="pt-1 text-center text-[10px] text-slate-400">
          Keep your policies and claim drafts together in one account.
        </div>
      </div>
    </div>
  );
}


export default function AuthModal(props: AuthModalProps) {
  const { authModalTab } = useAuth();
  return <AuthModalContent key={props.defaultTab || authModalTab} {...props} />;
}
