"use client";

import { useEffect, useLayoutEffect, useRef, useState } from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { ArrowUpRight, Bot, ChevronDown, ClipboardList, FileText, GitCompare, History, LayoutDashboard, LogOut, Menu, SearchCheck, Settings, X } from 'lucide-react';
import Brand from './Brand';
import { GlassBar } from './ui/Glass';
import { useAuth } from '@/context/AuthContext';
import { useScenario } from '@/context/ScenarioContext';
import { WIZARD_STEPS } from '@/lib/wizard';

const primaryLinks = [
  { href: '/dashboard', label: 'Overview', icon: LayoutDashboard },
  { href: '/policies', label: 'My policies', icon: FileText },
  { href: '/coverage', label: 'Coverage', icon: SearchCheck },
  { href: '/workspace', label: 'Ask ClaimWise', icon: Bot },
  { href: '/claims', label: 'My claims', icon: ClipboardList },
];

export default function Topbar() {
  const path = usePathname();
  const { href: journeyHref, isWizard, scenario, wizardHref } = useScenario();
  const { user, isAuthenticated, openAuthModal, logout } = useAuth();
  const [open, setOpen] = useState<'navigation' | 'account' | null>(null);
  const navigation = useRef<HTMLDivElement>(null);
  const account = useRef<HTMLDivElement>(null);
  const navigationButton = useRef<HTMLButtonElement>(null);
  const accountButton = useRef<HTMLButtonElement>(null);
  const desktopNav = useRef<HTMLElement>(null);
  const activePill = useRef<HTMLSpanElement>(null);
  // One persistent indicator moves between links, including after font loads/resizes.
  useLayoutEffect(() => {
    const nav = desktopNav.current;
    const pill = activePill.current;
    if (!nav || !pill) return;
    let disposed = false;
    const update = () => {
      if (disposed) return;
      const header = nav.closest('header');
      if (header) document.documentElement.style.setProperty('--cw-topbar-height', `${header.getBoundingClientRect().height}px`);
      const current = nav.querySelector<HTMLElement>('[aria-current="page"]');
      pill.style.opacity = current ? '1' : '0';
      if (current) {
        pill.style.width = `${current.offsetWidth}px`;
        pill.style.height = `${current.offsetHeight}px`;
        pill.style.transform = `translate(${current.offsetLeft}px, ${current.offsetTop}px)`;
      }
    };
    update();
    const observer = new ResizeObserver(update);
    observer.observe(nav);
    nav.querySelectorAll('a').forEach(link => observer.observe(link));
    void document.fonts.ready.then(update);
    return () => { disposed = true; observer.disconnect(); };
  }, [path]);
  useEffect(() => {
    const outside = (event: PointerEvent) => {
      if (!navigation.current?.contains(event.target as Node) && !account.current?.contains(event.target as Node)) setOpen(null);
    };
    const escape = (event: KeyboardEvent) => {
      if (event.key !== 'Escape') return;
      if (open === 'navigation') navigationButton.current?.focus();
      if (open === 'account') accountButton.current?.focus();
      setOpen(null);
    };
    document.addEventListener('pointerdown', outside);
    document.addEventListener('keydown', escape);
    return () => { document.removeEventListener('pointerdown', outside); document.removeEventListener('keydown', escape); };
  }, [open]);
  const active = (href: string) => path === href || path.startsWith(`${href}/`) || (isWizard && WIZARD_STEPS.find(step => step.page === href)?.id === (scenario.lastStep || 'policy'));
  const destination = (page: string) => {
    const step = isWizard ? WIZARD_STEPS.find(item => item.page === page) : undefined;
    return step ? wizardHref(step.id) : page === '/dashboard' ? page : journeyHref(page);
  };
  const name = user?.full_name?.trim() || user?.email || '';
  return <GlassBar className="cw-header">
    <div className="cw-header-inner mx-auto flex min-h-[76px] max-w-7xl items-center justify-between gap-4 px-4 sm:px-7 lg:px-10">
      <Link href={isAuthenticated ? '/dashboard' : '/'} onClick={() => setOpen(null)} className="cw-brand inline-flex shrink-0 items-center" aria-label={isAuthenticated ? 'ClaimWise overview' : 'ClaimWise home'}><Brand /></Link>
      <nav ref={desktopNav} className="cw-nav hidden items-center gap-1 lg:flex" aria-label="Main navigation"><span ref={activePill} className="cw-nav-indicator" aria-hidden="true" />{primaryLinks.map(item => <Link key={item.href} href={destination(item.href)} aria-current={active(item.href) ? 'page' : undefined} className={`cw-nav-link ${active(item.href) ? 'is-current' : ''}`}><item.icon className="h-3.5 w-3.5" strokeWidth={1.7} /><span>{item.label}</span></Link>)}</nav>
      <div className="flex items-center gap-2">
        <div className="relative lg:hidden" ref={navigation} onBlur={event => { if (!event.currentTarget.contains(event.relatedTarget)) setOpen(null); }}>
          <button ref={navigationButton} type="button" onClick={() => setOpen(open === 'navigation' ? null : 'navigation')} aria-expanded={open === 'navigation'} aria-controls="cw-mobile-navigation" aria-label="Navigation" className="cw-icon-button">{open === 'navigation' ? <X className="h-4 w-4" /> : <Menu className="h-4 w-4" />}</button>
          {open === 'navigation' && <nav id="cw-mobile-navigation" className="cw-popover absolute right-0 top-[calc(100%+12px)] w-60 p-2" aria-label="Mobile navigation">{primaryLinks.map(item => <Link key={item.href} href={destination(item.href)} aria-current={active(item.href) ? 'page' : undefined} onClick={() => setOpen(null)} className={`cw-menu-link ${active(item.href) ? 'is-current' : ''}`}><item.icon className="h-4 w-4" />{item.label}</Link>)}</nav>}
        </div>
        {isAuthenticated && user ? <div ref={account} className="relative" onBlur={event => { if (!event.currentTarget.contains(event.relatedTarget)) setOpen(null); }}>
          <button ref={accountButton} type="button" onClick={() => setOpen(open === 'account' ? null : 'account')} aria-expanded={open === 'account'} aria-controls="cw-account-menu" aria-label={`${name} account menu`} className="cw-account-button flex items-center gap-2 rounded-full p-1.5 pr-2.5"><span className="cw-avatar flex h-8 w-8 items-center justify-center rounded-full text-xs font-semibold">{name.charAt(0).toUpperCase()}</span><span className="hidden max-w-24 truncate text-xs font-medium text-slate-700 xl:block">{name.split(' ')[0]}</span><ChevronDown className={`h-3.5 w-3.5 text-slate-500 transition-transform ${open === 'account' ? 'rotate-180' : ''}`} /></button>
          {open === 'account' && <div id="cw-account-menu" className="cw-popover absolute right-0 top-[calc(100%+12px)] w-72 max-w-[calc(100vw_-_2rem)] overflow-hidden"><div className="border-b border-slate-200/60 px-4 py-4"><p className="truncate text-sm font-semibold text-slate-900">{name}</p><p className="mt-1 truncate text-xs text-slate-500">{user.email}</p></div><nav aria-label="Account and portfolio" className="p-2"><Link href="/compare" onClick={() => setOpen(null)} className="cw-menu-link"><GitCompare className="h-4 w-4" />Compare policies<ArrowUpRight className="ml-auto h-3.5 w-3.5" /></Link><Link href="/activity" onClick={() => setOpen(null)} className="cw-menu-link"><History className="h-4 w-4" />Activity & Audit log</Link><Link href="/settings" onClick={() => setOpen(null)} className="cw-menu-link"><Settings className="h-4 w-4" />Account settings</Link><button type="button" onClick={() => { setOpen(null); void logout(); }} className="cw-menu-link cw-signout w-full"><LogOut className="h-4 w-4" />Sign out</button></nav></div>}
        </div> : <button type="button" onClick={() => openAuthModal('login')} className="cw-account-button rounded-full px-4 py-2.5 text-xs font-semibold text-teal-800">Sign in</button>}
      </div>
    </div>
  </GlassBar>;
}
