'use client';

import React, { useEffect, useState } from 'react';
import Link from 'next/link';
import { ArrowLeft, CheckCircle2, LockKeyhole, Mail, MapPin, Save, UserRound } from 'lucide-react';
import { useAuth } from '@/context/AuthContext';
import { changeAccountPassword, updateAccountProfile } from '@/lib/api';

export default function SettingsPage() {
  const { user } = useAuth();
  const [fullName, setFullName] = useState(user?.full_name || '');
  const [address, setAddress] = useState('');
  const [profileMessage, setProfileMessage] = useState('');
  const [profileError, setProfileError] = useState('');
  const [savingProfile, setSavingProfile] = useState(false);
  const [currentPassword, setCurrentPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [passwordMessage, setPasswordMessage] = useState('');
  const [passwordError, setPasswordError] = useState('');
  const [savingPassword, setSavingPassword] = useState(false);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setFullName(user?.full_name || '');
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setAddress(user?.address || '');
  }, [user]);

  const saveProfile = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setSavingProfile(true);
    setProfileError('');
    setProfileMessage('');
    const result = await updateAccountProfile({ full_name: fullName.trim(), address: address.trim() });
    if (result.error) setProfileError(result.error);
    else setProfileMessage('Your account details have been updated.');
    setSavingProfile(false);
  };

  const savePassword = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setPasswordError('');
    setPasswordMessage('');
    if (newPassword !== confirmPassword) {
      setPasswordError('The new passwords do not match.');
      return;
    }
    setSavingPassword(true);
    const result = await changeAccountPassword({ current_password: currentPassword, new_password: newPassword });
    if (result.error) setPasswordError(result.error);
    else {
      setPasswordMessage('Your password has been changed.');
      setCurrentPassword('');
      setNewPassword('');
      setConfirmPassword('');
    }
    setSavingPassword(false);
  };

  return (
    <main className="app-page settings-page mx-auto max-w-4xl space-y-7 px-4 py-8 sm:px-7 sm:py-10">
      <header className="page-editorial-header border-b pb-5">
        <Link href="/dashboard" className="inline-flex items-center gap-1.5 text-xs text-slate-500 transition-colors hover:text-slate-800">
          <ArrowLeft className="h-3.5 w-3.5" /> Dashboard
        </Link>
        <h1 className="page-editorial-title">Account settings</h1>
        <p className="mt-2 text-sm text-slate-500">Update your personal details and sign-in password.</p>
      </header>

      <section className="max-w-2xl rounded-2xl border bg-white p-5 shadow-sm sm:p-7 cw-glass">
        <div className="mb-6">
          <h2 className="text-lg font-semibold text-slate-900">Personal details</h2>
          <p className="mt-1 text-sm text-slate-500">Your email address is used to sign in and cannot be changed here.</p>
        </div>
        <form onSubmit={saveProfile} className="space-y-5">
          <div>
            <label htmlFor="account-email" className="mb-1.5 block text-sm font-medium text-slate-700">Email address</label>
            <div className="relative">
              <Mail className="pointer-events-none absolute left-3 top-3.5 h-4 w-4 text-slate-400" />
              <input id="account-email" value={user?.email || ''} readOnly className="w-full rounded-xl border border-slate-200 bg-slate-100 py-3 pl-10 pr-3 text-sm text-slate-500" />
            </div>
          </div>
          <div>
            <label htmlFor="account-name" className="mb-1.5 block text-sm font-medium text-slate-700">Full name</label>
            <div className="relative">
              <UserRound className="pointer-events-none absolute left-3 top-3.5 h-4 w-4 text-slate-400" />
              <input id="account-name" required minLength={2} maxLength={100} value={fullName} onChange={(event) => setFullName(event.target.value)} className="w-full rounded-xl border border-slate-300 bg-white py-3 pl-10 pr-3 text-sm text-slate-900 outline-none transition focus:border-teal-600 focus:ring-3 focus:ring-teal-600/10" />
            </div>
          </div>
          <div>
            <label htmlFor="account-address" className="mb-1.5 block text-sm font-medium text-slate-700">Address</label>
            <div className="relative">
              <MapPin className="pointer-events-none absolute left-3 top-3.5 h-4 w-4 text-slate-400" />
              <input id="account-address" maxLength={300} value={address} onChange={(event) => setAddress(event.target.value)} placeholder="Street, city, postal code" className="w-full rounded-xl border border-slate-300 bg-white py-3 pl-10 pr-3 text-sm text-slate-900 outline-none transition placeholder:text-slate-400 focus:border-teal-600 focus:ring-3 focus:ring-teal-600/10" />
            </div>
          </div>
          {(profileError || profileMessage) && <p role="status" className={`text-sm ${profileError ? 'text-rose-700' : 'text-emerald-700'}`}>{profileError || profileMessage}</p>}
          <button type="submit" disabled={savingProfile} className="inline-flex min-h-11 items-center justify-center gap-2 rounded-xl bg-teal-800 px-5 text-sm font-semibold text-white shadow-sm transition hover:bg-teal-900 disabled:cursor-wait disabled:opacity-60">
            {profileMessage && !profileError ? <CheckCircle2 className="h-4 w-4" /> : <Save className="h-4 w-4" />}
            {savingProfile ? 'Saving…' : 'Save details'}
          </button>
        </form>
      </section>

      <section className="max-w-2xl rounded-2xl border bg-white p-5 shadow-sm sm:p-7 cw-glass">
        <div className="mb-6 flex items-start gap-3">
          <div className="rounded-xl bg-teal-50 p-2.5 text-teal-800"><LockKeyhole className="h-5 w-5" /></div>
          <div>
            <h2 className="text-lg font-semibold text-slate-900">Change password</h2>
            <p className="mt-1 text-sm text-slate-500">Use at least 6 characters for your new password.</p>
          </div>
        </div>
        <form onSubmit={savePassword} className="space-y-5">
          <div>
            <label htmlFor="current-password" className="mb-1.5 block text-sm font-medium text-slate-700">Current password</label>
            <input id="current-password" type="password" required autoComplete="current-password" value={currentPassword} onChange={(event) => setCurrentPassword(event.target.value)} className="w-full rounded-xl border border-slate-300 bg-white px-3 py-3 text-sm outline-none transition focus:border-teal-600 focus:ring-3 focus:ring-teal-600/10" />
          </div>
          <div className="grid gap-5 sm:grid-cols-2">
            <div>
              <label htmlFor="new-password" className="mb-1.5 block text-sm font-medium text-slate-700">New password</label>
              <input id="new-password" type="password" required minLength={6} maxLength={128} autoComplete="new-password" value={newPassword} onChange={(event) => setNewPassword(event.target.value)} className="w-full rounded-xl border border-slate-300 bg-white px-3 py-3 text-sm outline-none transition focus:border-teal-600 focus:ring-3 focus:ring-teal-600/10" />
            </div>
            <div>
              <label htmlFor="confirm-password" className="mb-1.5 block text-sm font-medium text-slate-700">Confirm new password</label>
              <input id="confirm-password" type="password" required minLength={6} maxLength={128} autoComplete="new-password" value={confirmPassword} onChange={(event) => setConfirmPassword(event.target.value)} className="w-full rounded-xl border border-slate-300 bg-white px-3 py-3 text-sm outline-none transition focus:border-teal-600 focus:ring-3 focus:ring-teal-600/10" />
            </div>
          </div>
          {(passwordError || passwordMessage) && <p role="status" className={`text-sm ${passwordError ? 'text-rose-700' : 'text-emerald-700'}`}>{passwordError || passwordMessage}</p>}
          <button type="submit" disabled={savingPassword} className="inline-flex min-h-11 items-center justify-center gap-2 rounded-xl border border-slate-300 bg-white px-5 text-sm font-semibold text-slate-700 transition hover:bg-slate-50 disabled:cursor-wait disabled:opacity-60">
            {savingPassword ? 'Updating…' : 'Update password'}
          </button>
        </form>
      </section>
    </main>
  );
}
