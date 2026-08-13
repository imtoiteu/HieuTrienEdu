import type { ReactNode } from 'react';

import { AdminProviders } from '@/components/admin/providers';

/**
 * Route configuration for the whole admin area.
 *
 * `force-dynamic` is the important line. Every admin screen is auth-gated, reads live data and
 * uses `useSearchParams`, so prerendering it at build time is both impossible (Next.js requires a
 * Suspense boundary around `useSearchParams` in a statically-rendered page) and pointless — there
 * is no cacheable HTML for a page whose entire content depends on who is signed in.
 *
 * This is a server component purely so the route-segment config above is honoured; the actual
 * providers are a client component.
 */
export const dynamic = 'force-dynamic';

export default function AdminLayout({ children }: { children: ReactNode }) {
  return <AdminProviders>{children}</AdminProviders>;
}
