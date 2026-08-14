import { MarketingShell } from '@/components/site/marketing-shell';

import { NotFoundBody } from './not-found-body';

/**
 * Why this page is split in two.
 *
 * `MarketingShell` is an **async server component**: it fetches the admin-managed contact details
 * and the live banner once, on the server, and passes them down. Importing it from a `'use client'`
 * module turns it into a client component — and an async client component never settles. React
 * re-renders it every time its promise resolves, so the two site-chrome requests repeat until the
 * browser runs out of sockets. While the API is up that only shows as duplicate requests; the
 * moment it is not, every visitor's browser turns into a retry storm.
 *
 * So the route stays a server component that renders the shell, and everything needing
 * `useI18n()` lives in the client body inside it.
 */
export default function NotFound() {
  return (
    <MarketingShell>
      <NotFoundBody />
    </MarketingShell>
  );
}
