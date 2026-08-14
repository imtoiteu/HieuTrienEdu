import type { Metadata, Viewport } from 'next';
import type { ReactNode } from 'react';

import './globals.css';
import 'katex/dist/katex.min.css';

export const metadata: Metadata = {
  metadataBase: new URL(process.env.NEXT_PUBLIC_SITE_URL ?? 'http://localhost:3000'),
  title: {
    default: 'HieuTrienEducation — Mathematics & Physics for Grades 6–9',
    template: '%s · HieuTrienEducation',
  },
  description:
    'Adaptive Mathematics and Physics learning for grades 6 to 12, with 1-to-1 tutoring, ' +
    'group and online classes. Built by Thầy Hiếu & Cô Triền.',
  applicationName: 'HieuTrienEducation',
  authors: [{ name: 'HieuTrienEducation' }],
  keywords: [
    'mathematics tutoring',
    'physics tutoring',
    'grade 6',
    'grade 7',
    'grade 8',
    'grade 9',
    'adaptive learning',
    'Vietnam',
  ],
  openGraph: {
    type: 'website',
    siteName: 'HieuTrienEducation',
    title: 'HieuTrienEducation — Mathematics & Physics for Grades 6–9',
    description:
      'Find the exact gap holding a student back, then close it with practice that never runs out.',
  },
  robots: { index: true, follow: true },
};

export const viewport: Viewport = {
  themeColor: '#6D4AFF',
  width: 'device-width',
  initialScale: 1,
};

/**
 * The root layout is deliberately minimal: `<html lang>` depends on the locale, which is only
 * known inside `[locale]/layout.tsx`, so the language attribute is set there via a small client
 * effect rather than being wrong here.
 */
export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body>{children}</body>
    </html>
  );
}
