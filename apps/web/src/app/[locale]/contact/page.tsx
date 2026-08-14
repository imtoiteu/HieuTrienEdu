import { MarketingShell } from '@/components/site/marketing-shell';

import { ContactBody } from './contact-body';

/**
 * Why this page is split in two.
 *
 * `MarketingShell` is an **async server component**: it fetches the admin-managed contact details
 * and the live banner once, on the server. Importing it from a `'use client'` module turns it into
 * a client component — and an async client component never settles. React re-renders it every time
 * its promise resolves, so the two site-chrome requests repeat until the browser runs out of
 * sockets.
 *
 * The route therefore stays a server component, and the enquiry form — which has to run in the
 * browser — sits inside it as a client child.
 */
export default async function ContactPage({
  params,
}: {
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params;
  return (
    <MarketingShell locale={locale}>
      <ContactBody />
    </MarketingShell>
  );
}
