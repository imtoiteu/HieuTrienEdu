import type { ReactNode } from 'react';

import { api, type PublicAnnouncement } from '@/lib/api';
import { safeAll } from '@/lib/server-api';

import { AnnouncementBar } from './announcement-bar';
import { SiteFooter } from './footer';
import { SiteHeader } from './header';

/**
 * Chrome shared by every public marketing page.
 *
 * A server component so that the admin-managed contact details and live banners are fetched once
 * per render and passed down, rather than every page having to remember to load them.
 */
export async function MarketingShell({ children }: { children: ReactNode }) {
  const { settings, announcements } = await safeAll(
    {
      settings: api.site.settings(),
      announcements: api.site.announcements('banner'),
    },
    {
      settings: {} as Record<string, Record<string, string>>,
      announcements: [] as PublicAnnouncement[],
    },
  );

  return (
    <div className="flex min-h-screen flex-col bg-cream">
      {announcements.length > 0 && <AnnouncementBar announcement={announcements[0]} />}
      <SiteHeader />
      <main id="main" className="flex-1">
        {children}
      </main>
      <SiteFooter settings={settings} />
    </div>
  );
}
