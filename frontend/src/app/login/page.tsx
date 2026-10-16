'use client';

import React, { useState, useEffect, Suspense } from 'react';
import Link from 'next/link';
import LogoMark from '@/components/LogoMark';
import { useRouter, useSearchParams } from 'next/navigation';
import { useAuth } from '@/context/AuthContext';
import {
  Mail,
  Lock,
  User,
  Eye,
  EyeOff,
  RefreshCw,
  AlertCircle,
  CheckCircle2,
  ArrowRight,
  FileCheck,
  Scale,
  LockKeyhole,
  Phone,
  Globe,
  Briefcase,
  Building2,
  GraduationCap,
} from 'lucide-react';

function LoginContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const initialTab = searchParams.get('tab') === 'signup' ? 'signup' : 'login';

  const { isAuthenticated, login, signup } = useAuth();

  const [tab, setTab] = useState<'login' | 'signup'>(initialTab);
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

  // Signed-in users enter the scenario overview.
  useEffect(() => {
    if (isAuthenticated) {
      router.replace('/dashboard');
    }
  }, [isAuthenticated, router, searchParams]);

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
          router.replace('/dashboard');
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
          router.replace('/dashboard');
        }
      }
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Authentication failed');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="auth-page relative isolate flex min-h-screen flex-col justify-center bg-slate-50 px-4 py-12 sm:px-6 lg:px-8">
      {/* Brand Header */}
      <div className="sm:mx-auto sm:w-full sm:max-w-md text-center mb-6">
        <Link href="/" className="inline-flex items-center gap-2.5 group">
          <LogoMark />
          <span className="text-xl font-bold tracking-tight text-slate-900">
            ClaimWise
          </span>
        </Link>
        <p className="text-xs text-slate-500 mt-2">
          Evidence first. If no proof, no answer.
        </p>
      </div>

      <div className="relative z-10 mx-auto grid w-full max-w-5xl grid-cols-1 items-center gap-8 lg:grid-cols-12 lg:gap-10">
        {/* Left Value Column (Visible on Desktop) */}
        <div className="lg:col-span-6 space-y-6 hidden lg:block pr-4">
          <div className="space-y-2">
            <span className="inline-flex items-center rounded-full bg-teal-50 border border-teal-200/80 px-2.5 py-0.5 text-[11px] font-semibold text-teal-800">
              High-Assurance AI Infrastructure
            </span>
            <h1 className="text-2xl font-bold text-slate-900 tracking-tight leading-tight">
              Contract-Grounded Insurance Intelligence
            </h1>
            <p className="text-xs text-slate-500 leading-relaxed">
              Verify policy provisions, evaluate coverage gaps, and adjudicate medical bills with verifiable page citations and deterministic rules.
            </p>
          </div>

          <div className="space-y-3">
            <div className="auth-feature flex items-start gap-3 rounded-lg border border-slate-200 bg-white p-3.5 shadow-2xs">
              <FileCheck className="h-4 w-4 text-teal-700 shrink-0 mt-0.5" />
              <div>
                <h2 className="text-xs font-semibold text-slate-800">Verbatim Clause Citations</h2>
                <p className="text-[11px] text-slate-500 mt-0.5">Every finding references the exact 1-based page number and SHA-256 document hash.</p>
              </div>
            </div>

            <div className="auth-feature flex items-start gap-3 rounded-lg border border-slate-200 bg-white p-3.5 shadow-2xs">
              <Scale className="h-4 w-4 text-teal-700 shrink-0 mt-0.5" />
              <div>
                <h2 className="text-xs font-semibold text-slate-800">Deterministic Claims Adjudication</h2>
                <p className="text-[11px] text-slate-500 mt-0.5">Zero LLM math hallucination. Deductibles, copays, and coinsurance calculated deterministically.</p>
              </div>
            </div>

            <div className="auth-feature flex items-start gap-3 rounded-lg border border-slate-200 bg-white p-3.5 shadow-2xs">
              <LockKeyhole className="h-4 w-4 text-teal-700 shrink-0 mt-0.5" />
              <div>
                <h2 className="text-xs font-semibold text-slate-800">Tamper-Evident Audit Trail</h2>
                <p className="text-[11px] text-slate-500 mt-0.5">Every inquiry, adjudication, and appeal is recorded in a cryptographically verified SHA-256 hash-chain.</p>
              </div>
            </div>
          </div>

          <div className="pt-2 text-[11px] text-slate-400 flex items-center gap-4">
            <span>HIPAA Compliant</span>
            <span>•</span>
            <span>SOC 2 Type II Controls</span>
            <span>•</span>
            <span>Tier 1 Suggest Mode</span>
          </div>
        </div>

        {/* Right Form Card */}
        <div className="lg:col-span-6 w-full">
          <div className="auth-panel space-y-5 rounded-2xl border border-slate-200 bg-white p-6 shadow-xl sm:p-8 cw-glass">
            {/* Tab Switcher */}
            <div className="auth-tabs grid grid-cols-2 rounded-lg bg-slate-100 p-1 text-xs font-semibold">
              <button
                type="button"
                onClick={() => {
                  setTab('login');
                  setError(null);
                }}
                className={`rounded-md py-2 transition-colors cursor-pointer ${
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
                className={`rounded-md py-2 transition-colors cursor-pointer ${
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

            {/* Form */}
            <form onSubmit={handleSubmit} className="space-y-4">
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
                      placeholder="Alex Morgan"
                      className="auth-input w-full rounded-lg border border-slate-300 bg-white py-2 pl-9 pr-3 text-xs text-slate-900 focus:border-teal-600 focus:outline-none focus:ring-1 focus:ring-teal-600"
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
                    className="auth-input w-full rounded-lg border border-slate-300 bg-white py-2 pl-9 pr-3 text-xs text-slate-900 focus:border-teal-600 focus:outline-none focus:ring-1 focus:ring-teal-600"
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
                          className="auth-input w-full rounded-lg border border-slate-300 bg-white py-2 pl-9 pr-3 text-xs text-slate-900 focus:border-teal-600 focus:outline-none focus:ring-1 focus:ring-teal-600"
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
                          className="auth-input w-full rounded-lg border border-slate-300 bg-white py-2 pl-9 pr-3 text-xs text-slate-900 focus:border-teal-600 focus:outline-none focus:ring-1 focus:ring-teal-600 cursor-pointer"
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
                          className="auth-input w-full rounded-lg border border-slate-300 bg-white py-2 pl-9 pr-3 text-xs text-slate-900 focus:border-teal-600 focus:outline-none focus:ring-1 focus:ring-teal-600 cursor-pointer"
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
                          className="auth-input w-full rounded-lg border border-slate-300 bg-white py-2 pl-9 pr-3 text-xs text-slate-900 focus:border-teal-600 focus:outline-none focus:ring-1 focus:ring-teal-600"
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
                    className="auth-input w-full rounded-lg border border-slate-300 bg-white py-2 pl-9 pr-9 text-xs text-slate-900 focus:border-teal-600 focus:outline-none focus:ring-1 focus:ring-teal-600"
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
                className="auth-submit w-full inline-flex cursor-pointer items-center justify-center gap-2 rounded-lg bg-teal-700 py-2.5 text-xs font-semibold text-white shadow-xs transition-colors hover:bg-teal-800 disabled:cursor-wait disabled:opacity-50"
              >
                {isLoading ? (
                  <>
                    <RefreshCw className="h-3.5 w-3.5 animate-spin" />
                    <span>Authenticating...</span>
                  </>
                ) : (
                  <>
                    <span>{tab === 'login' ? 'Sign In' : 'Create Account'}</span>
                    <ArrowRight className="h-3.5 w-3.5" />
                  </>
                )}
              </button>
            </form>

            <p className="auth-legal text-center text-[10px] text-slate-400">
              By signing in, you agree to ClaimWise evidence-first verification terms.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}

export default function LoginPage() {
  return (
    <Suspense fallback={<div className="min-h-screen bg-slate-50 flex items-center justify-center text-xs text-slate-400">Loading authentication portal...</div>}>
      <LoginContent />
    </Suspense>
  );
}
