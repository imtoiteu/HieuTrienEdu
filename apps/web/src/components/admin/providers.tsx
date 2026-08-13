'use client';

import type { ReactNode } from 'react';

import { ToastProvider } from './toast';

/**
 * Client-side providers shared by every admin screen.
 *
 * Mounted from the admin layout rather than per page, so a toast raised just before a navigation
 * survives the route change — otherwise "Saved" vanishes the instant you are sent back to a list.
 */
export function AdminProviders({ children }: { children: ReactNode }) {
  return <ToastProvider>{children}</ToastProvider>;
}
