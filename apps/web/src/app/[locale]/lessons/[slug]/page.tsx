import { MarketingShell } from '@/components/site/marketing-shell';

import { LessonBody } from './lesson-body';

/**
 * Why this page is split in two.
 *
 * `MarketingShell` is an **async server component**: it fetches the admin-managed contact details
 * and the live banner once, on the server. Importing it from a `'use client'` module turns it into
 * a client component — and an async client component never settles. React re-renders it every time
 * its promise resolves, so the two site-chrome requests repeat until the browser runs out of
 * sockets. On a healthy API that shows only as duplicate requests; when the API is unreachable it
 * becomes a retry storm that also stops the lesson itself from ever rendering.
 *
 * The route therefore stays a server component, and the lesson body — which loads its content in
 * the browser so a signed-in student's progress is included — sits inside it as a client child.
 */
export default async function LessonPage({
  params,
}: {
  params: Promise<{ locale: string; slug: string }>;
}) {
  const { locale } = await params;
  return (
    <MarketingShell locale={locale}>
      <LessonBody params={params} />
    </MarketingShell>
  );
}
