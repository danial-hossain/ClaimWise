'use client';

import React from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import {
  Shield,
  Bot,
  FileText,
  ClipboardList,
  GitCompare,
  Settings as SettingsIcon,
  Activity,
  History,
} from 'lucide-react';

const NAV_ITEMS = [
  { href: '/dashboard', label: 'Dashboard', icon: Activity },
  { href: '/workspace', label: 'AI Workspace', icon: Bot },
  { href: '/policies', label: 'My Policies', icon: FileText },
  { href: '/claims', label: 'My Claims', icon: ClipboardList },
  { href: '/activity', label: 'Activity Log', icon: History },
  { href: '/compare', label: 'Compare & Choose', icon: GitCompare },
  { href: '/settings', label: 'Settings & Security', icon: SettingsIcon },
];

export default function Navigation() {
  const pathname = usePathname();

  return (
    <header className="sticky top-0 z-50 w-full border-b border-slate-200 bg-white/95 backdrop-blur-md dark:border-slate-800 dark:bg-slate-900/95">
      <div className="mx-auto flex max-w-7xl items-center justify-between px-4 sm:px-6 lg:px-8 h-16">
        {/* Brand & Tagline */}
        <div className="flex items-center gap-3">
          <Link href="/" className="flex items-center gap-2.5 group">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-tr from-emerald-600 to-teal-500 text-white shadow-md shadow-emerald-500/20 group-hover:scale-105 transition-transform">
              <Shield className="h-5 w-5" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className="font-bold text-lg tracking-tight text-slate-900 dark:text-white">
                  ClaimWise
                </span>
                <span className="inline-flex items-center rounded-md bg-emerald-50 px-2 py-0.5 text-xs font-medium text-emerald-700 ring-1 ring-inset ring-emerald-600/20 dark:bg-emerald-950/40 dark:text-emerald-400">
                  FinTechathon
                </span>
              </div>
              <p className="text-[11px] font-medium text-slate-500 dark:text-slate-400">
                Evidence first. If no proof, no answer.
              </p>
            </div>
          </Link>
        </div>

        {/* Primary Navigation Links */}
        <nav className="hidden md:flex items-center space-x-1 lg:space-x-2">
          {NAV_ITEMS.map((item) => {
            const Icon = item.icon;
            const isActive = pathname === item.href;
            return (
              <Link
                key={item.href}
                href={item.href}
                className={`flex items-center gap-2 px-3 py-2 rounded-lg text-sm font-medium transition-colors ${
                  isActive
                    ? 'bg-emerald-50 text-emerald-700 dark:bg-emerald-950/50 dark:text-emerald-400'
                    : 'text-slate-600 hover:text-slate-900 hover:bg-slate-100 dark:text-slate-300 dark:hover:text-white dark:hover:bg-slate-800/60'
                }`}
              >
                <Icon className={`h-4 w-4 ${isActive ? 'text-emerald-600 dark:text-emerald-400' : 'text-slate-400'}`} />
                <span>{item.label}</span>
              </Link>
            );
          })}
        </nav>

        {/* Product version */}
        <div className="flex items-center gap-3">
          <div className="flex items-center">
            <span className="text-xs text-slate-600 dark:text-slate-400 font-mono bg-slate-100 dark:bg-slate-800 px-2 py-1 rounded">
              v0.1.0-M1
            </span>
          </div>
        </div>
      </div>

      {/* Mobile Navigation Scrollbar */}
      <div className="flex md:hidden overflow-x-auto border-t border-slate-100 px-4 py-2 space-x-2 bg-slate-50 dark:border-slate-800/80 dark:bg-slate-900">
        {NAV_ITEMS.map((item) => {
          const Icon = item.icon;
          const isActive = pathname === item.href;
          return (
            <Link
              key={item.href}
              href={item.href}
              className={`flex shrink-0 items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium ${
                isActive
                  ? 'bg-emerald-600 text-white'
                  : 'text-slate-600 hover:bg-slate-200 dark:text-slate-300 dark:hover:bg-slate-800'
              }`}
            >
              <Icon className="h-3.5 w-3.5" />
              <span>{item.label}</span>
            </Link>
          );
        })}
      </div>
    </header>
  );
}
