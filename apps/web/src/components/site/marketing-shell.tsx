import type { ReactNode } from 'react';

import { SiteFooter } from './footer';
import { SiteHeader } from './header';

/** Chrome shared by every public marketing page. */
export function MarketingShell({ children }: { children: ReactNode }) {
  return (
    <div className="flex min-h-screen flex-col bg-cream">
      <SiteHeader />
      <main id="main" className="flex-1">
        {children}
      </main>
      <SiteFooter />
    </div>
  );
}
