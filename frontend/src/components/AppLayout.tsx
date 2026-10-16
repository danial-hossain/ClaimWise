'use client';

import React, { Suspense } from 'react';
import { usePathname } from 'next/navigation';
import Topbar from './Topbar';
import { ScenarioProvider, ScenarioPageContent } from '@/context/ScenarioContext';
import Stepper from '@/components/features/wizard/Stepper';
import { AuthProvider } from '@/context/AuthContext';
import AuthModal from '@/components/features/auth/AuthModal';
import Footer from './Footer';

interface AppLayoutProps {
  children: React.ReactNode;
}

export default function AppLayout({ children }: AppLayoutProps) {
  const pathname = usePathname();

  const isStandalonePage =
    pathname === '/' || pathname === '/login' || pathname === '/signup';

  return (
    <AuthProvider>
      <ScenarioProvider>
      {isStandalonePage ? (
        <>
          {children}
          <Footer />
          <AuthModal />
        </>
      ) : (
        <div className="app-canvas flex min-h-screen flex-col">
          <a href="#main-content" className="cw-skip-link">Skip to content</a>
          <Topbar />
          <Suspense fallback={null}><Stepper /></Suspense>
          <main id="main-content" tabIndex={-1} className="app-main flex-1"><ScenarioPageContent>{children}</ScenarioPageContent></main>
          <Footer />

          {/* Universal Auth Popup Modal */}
          <AuthModal />
        </div>
      )}
      </ScenarioProvider>
    </AuthProvider>
  );
}
