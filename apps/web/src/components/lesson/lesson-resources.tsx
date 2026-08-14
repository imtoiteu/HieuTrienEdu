'use client';

import { BookOpen, ExternalLink, FlaskConical, Image as ImageIcon, Table2 } from 'lucide-react';

import { Card } from '@hietedu/ui';

import type { LessonResource } from '@/lib/api';
import { useI18n } from '@/lib/i18n';

/** Resource types the authored content uses, mapped to the icon that reads fastest. */
const ICONS: Record<string, typeof BookOpen> = {
  simulation: FlaskConical,
  reading: BookOpen,
  dataset: Table2,
  image: ImageIcon,
};

/**
 * Curated links out of the site, shown under a lesson.
 *
 * These all point at other people's work — PhET simulations, OpenStax chapters, NASA pages —
 * which is why the source host is on the card rather than hidden behind the link text, and why
 * the attribution line is rendered rather than merely stored: most of these sources are openly
 * licensed on the condition that they are credited.
 */
export function LessonResources({ resources }: { resources: LessonResource[] }) {
  const { t } = useI18n();

  if (resources.length === 0) return null;

  return (
    <section className="mt-12" aria-labelledby="further-reading">
      <h2 id="further-reading" className="font-display text-2xl">
        {t('lesson.furtherReading')}
      </h2>
      <p className="mt-1.5 text-sm text-ink-600">{t('lesson.furtherReadingIntro')}</p>

      <ul className="mt-5 space-y-3">
        {resources.map((resource) => {
          const Icon = ICONS[resource.resource_type] ?? ExternalLink;
          return (
            <li key={resource.id}>
              <Card className="transition hover:border-brand-300 hover:shadow-pop">
                <a
                  href={resource.url}
                  target="_blank"
                  // noopener is the security half (the opened page cannot reach back through
                  // window.opener); noreferrer keeps our URLs out of third-party analytics.
                  rel="noopener noreferrer"
                  className="flex items-start gap-3.5"
                >
                  <span
                    className="mt-0.5 shrink-0 rounded-xl bg-brand-50 p-2 text-brand-600"
                    aria-hidden="true"
                  >
                    <Icon className="h-5 w-5" />
                  </span>
                  <span className="min-w-0 flex-1">
                    <span className="flex items-center gap-1.5 font-bold text-ink-900">
                      {resource.title}
                      <ExternalLink className="h-3.5 w-3.5 shrink-0 text-ink-400" aria-hidden="true" />
                    </span>
                    {resource.description && (
                      <span className="mt-1 block text-sm text-ink-600">{resource.description}</span>
                    )}
                    <span className="mt-2 block text-xs text-ink-500">
                      {resource.host}
                      {resource.attribution ? ` · ${resource.attribution}` : ''}
                      {resource.license ? ` · ${resource.license}` : ''}
                    </span>
                  </span>
                </a>
              </Card>
            </li>
          );
        })}
      </ul>
    </section>
  );
}
