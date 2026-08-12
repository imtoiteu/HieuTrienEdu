'use client';

import Link from 'next/link';
import { useEffect, useMemo, useState } from 'react';

import { Badge, Button, Card, EmptyState, ProgressBar, Spinner } from '@hietedu/ui';

import { AppShell } from '@/components/app/app-shell';
import { api } from '@/lib/api';
import { useRequireAuth } from '@/lib/auth';
import { useI18n } from '@/lib/i18n';

interface MasteryRow {
  skill_id: number;
  skill_slug: string;
  skill_name: string;
  topic: string | null;
  unit: string | null;
  subject_slug: string | null;
  grade: number | null;
  mastery_percent: number;
  attempts: number;
  correct: number;
  accuracy: number | null;
  is_mastered: boolean;
  last_practiced_at: string | null;
}

export default function ProgressPage({ params }: { params: Promise<{ locale: string }> }) {
  const { t, locale, formatDate } = useI18n();
  const { user, loading: authLoading } = useRequireAuth(locale, ['student']);

  const [rows, setRows] = useState<MasteryRow[] | null>(null);
  const [subject, setSubject] = useState<string>('');
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!user) return;
    let cancelled = false;
    api.progress
      .mastery()
      .then((result) => !cancelled && setRows(result as unknown as MasteryRow[]))
      .catch((caught) => !cancelled && setError((caught as Error).message));
    return () => {
      cancelled = true;
    };
  }, [user]);

  const filtered = useMemo(
    () => (rows ?? []).filter((row) => !subject || row.subject_slug === subject),
    [rows, subject],
  );

  // Group by unit so the list reads as a curriculum rather than a flat table of skills.
  const grouped = useMemo(() => {
    const map = new Map<string, MasteryRow[]>();
    filtered.forEach((row) => {
      const key = row.unit ?? t('common.emptyState');
      map.set(key, [...(map.get(key) ?? []), row]);
    });
    return [...map.entries()];
  }, [filtered, t]);

  if (authLoading || !user) return <AppShell role="student" loading />;

  return (
    <AppShell role="student">
      <div className="mx-auto w-full max-w-5xl px-5 py-8 sm:px-8 lg:py-10">
        <h1 className="font-display text-3xl sm:text-4xl">{t('progress.title')}</h1>

        <div className="mt-6 flex flex-wrap gap-2">
          {[
            { value: '', label: t('common.all') },
            { value: 'mathematics', label: t('subject.mathematics.title') },
            { value: 'physics', label: t('subject.physics.title') },
          ].map((option) => (
            <button
              key={option.value}
              type="button"
              onClick={() => setSubject(option.value)}
              aria-pressed={subject === option.value}
              className={`rounded-2xl border-2 px-4 py-2 text-sm font-bold transition-colors ${
                subject === option.value
                  ? 'border-ink-900 bg-brand-500 text-white shadow-pop-sm'
                  : 'border-ink-200 bg-white text-ink-700 hover:border-brand-300'
              }`}
            >
              {option.label}
            </button>
          ))}
        </div>

        {!rows && !error && (
          <div className="flex justify-center py-24">
            <Spinner className="h-8 w-8 text-brand-500" />
            <span className="sr-only">{t('common.loading')}</span>
          </div>
        )}

        {error && (
          <Card className="mt-6 border-red-200 bg-red-50">
            <p className="text-sm text-red-700">{error}</p>
          </Card>
        )}

        {rows && filtered.length === 0 && (
          <EmptyState
            className="mt-8"
            title={t('dashboard.noActivity')}
            action={
              <Link href={`/${locale}/courses`}>
                <Button>{t('dashboard.browseCourses')}</Button>
              </Link>
            }
          />
        )}

        {grouped.length > 0 && (
          <div className="mt-8 space-y-8">
            {grouped.map(([unit, unitRows]) => (
              <section key={unit}>
                <h2 className="font-display text-xl">{unit}</h2>
                <div className="mt-4 space-y-3">
                  {unitRows.map((row) => (
                    <Card key={row.skill_id} className="flex flex-wrap items-center gap-4">
                      <div className="min-w-[12rem] flex-1">
                        <div className="flex flex-wrap items-center gap-2">
                          <Link
                            href={`/${locale}/practice/${row.skill_slug}`}
                            className="font-bold text-ink-900 hover:text-brand-700 hover:underline"
                          >
                            {row.skill_name}
                          </Link>
                          {row.is_mastered && <Badge tone="teal">{t('path.mastered')}</Badge>}
                        </div>
                        <p className="mt-1 text-xs text-ink-500">
                          {row.attempts} {t('progress.attempts')}
                          {row.accuracy !== null &&
                            ` · ${Math.round(row.accuracy * 100)}% ${t('dashboard.accuracy').toLowerCase()}`}
                          {row.last_practiced_at
                            ? ` · ${t('progress.lastPractised', {
                                date: formatDate(row.last_practiced_at),
                              })}`
                            : ''}
                        </p>
                      </div>
                      <div className="w-full sm:w-56">
                        <ProgressBar
                          value={row.mastery_percent}
                          tone={
                            row.subject_slug === 'physics'
                              ? 'teal'
                              : row.is_mastered
                                ? 'teal'
                                : 'brand'
                          }
                          showValue
                          size="sm"
                        />
                      </div>
                    </Card>
                  ))}
                </div>
              </section>
            ))}
          </div>
        )}
      </div>
    </AppShell>
  );
}
