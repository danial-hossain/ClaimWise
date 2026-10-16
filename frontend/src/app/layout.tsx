import type { Metadata } from 'next';
import { Inter } from 'next/font/google';
import './globals.css';
import './workspace.css';
import './theme.css';
import './wizard.css';
import './surfaces.css';
import './hero.css';
import AppLayout from '@/components/AppLayout';

const inter = Inter({
  variable: '--font-inter',
  subsets: ['latin'],
  display: 'swap',
});

export const metadata: Metadata = {
  icons: { icon: '/icon.svg', shortcut: '/icon.svg' },
  title: 'ClaimWise — Evidence-First AI Insurance Assistant',
  description:
    'Evidence first. If no proof, no answer. AI insurance assistant with verifiable citations, deterministic calculation rules, and claim investigation.',
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="en"
      className={`${inter.variable} h-full antialiased`}
    >
      <body className="min-h-full bg-slate-50/60 text-slate-900 antialiased">
        <AppLayout>{children}</AppLayout>
      </body>
    </html>
  );
}
