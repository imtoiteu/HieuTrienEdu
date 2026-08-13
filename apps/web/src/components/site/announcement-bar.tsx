'use client';

import Link from 'next/link';
import { X } from 'lucide-react';
import { useState } from 'react';

import { cn } from '@hietedu/ui';

import type { PublicAnnouncement } from '@/lib/api';
import { useI18n } from '@/lib/i18n';

const TONES: Record<string, string> = {
  brand: 'bg-brand-600 text-white',
  coral: 'bg-coral-500 text-white',
  teal: 'bg-teal-600 text-white',
  sun: 'bg-sun-400 text-ink-900',
};

/**
 * The admin-scheduled banner strip.
 *
 * Dismissal is per-page-load rather than persisted: a centre that puts up an enrolment banner
 * wants it seen on the next visit too, and remembering a dismissal across sessions would need a
 * cookie for something that expires on its own anyway.
 */
export function AnnouncementBar({ announcement }: { announcement: PublicAnnouncement }) {
  const { locale, t } = useI18n();
  const [dismissed, setDismissed] = useState(false);

  if (dismissed) return null;

  const href = announcement.link_url?.startsWith('/')
    ? `/${locale}${announcement.link_url}`
    : announcement.link_url;

  return (
    <div className={cn('relative px-4 py-2.5 text-center text-sm', TONES[announcement.tone] ?? TONES.brand)}>
      <span className="font-bold">{announcement.title}</span>
      {announcement.body && <span className="ml-2 opacity-90">{announcement.body}</span>}
      {href && (
        <Link href={href} className="ml-3 font-extrabold underline underline-offset-2">
          {announcement.link_label ?? 'Learn more'}
        </Link>
      )}
      <button
        type="button"
        onClick={() => setDismissed(true)}
        aria-label={t('a11y.dismissAnnouncement')}
        className="absolute right-2 top-1/2 -translate-y-1/2 rounded-lg p-1.5 hover:bg-black/10"
      >
        <X className="h-4 w-4" aria-hidden="true" />
      </button>
    </div>
  );
}
