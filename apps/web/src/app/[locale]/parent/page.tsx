'use client';

import { CalendarClock, Flame, TrendingUp, Users } from 'lucide-react';
import { useCallback, useEffect, useState } from 'react';

import { Alert, Avatar, Badge, Button, Card, EmptyState, Field, Input, ProgressBar, Spinner } from '@hietedu/ui';

import { AppShell } from '@/components/app/app-shell';
import { api } from '@/lib/api';
import { useRequireAuth } from '@/lib/auth';
import { useI18n } from '@/lib/i18n';

interface Child {
  student_id: number;
  name: string;
  grade: number;
  avatar_url: string | null;
  xp_total: number;
  level: number;
  streak_days: number;
  average_mastery_percent: number;
  skills_mastered: number;
  attempts: number;
  accuracy: number | null;
  last_active_at: string | null;
}

interface ChildProgress {
  subjects: { slug: string; name: string; mastery_percent: number; skills_tracked: number }[];
  weak_skills: {
    skill_name: string;
    skill_slug: string;
    mastery_percent: number;
    attempts: number;
    accuracy: number | null;
  }[];
  stats: { total_attempts: number; skills_mastered: number; accuracy: number | null };
}

export default function ParentPage({ params }: { params: Promise<{ locale: string }> }) {
  const { t, locale, formatDate } = useI18n();
  const { user, loading: authLoading } = useRequireAuth(locale, ['parent']);

  const [children, setChildren] = useState<Child[] | null>(null);
  const [selected, setSelected] = useState<number | null>(null);
  const [progress, setProgress] = useState<ChildProgress | null>(null);
  const [linkEmail, setLinkEmail] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [linking, setLinking] = useState(false);

  const loadChildren = useCallback(async () => {
    const rows = (await api.parent.children()) as unknown as Child[];
    setChildren(rows);
    if (rows.length > 0) setSelected((current) => current ?? rows[0].student_id);
  }, []);

  useEffect(() => {
    if (!user) return;
    loadChildren().catch((caught) => setError((caught as Error).message));
  }, [user, loadChildren]);

  useEffect(() => {
    if (selected === null) return;
    let cancelled = false;
    setProgress(null);
    api.parent
      .childProgress(selected)
      .then((result) => !cancelled && setProgress(result as unknown as ChildProgress))
      .catch((caught) => !cancelled && setError((caught as Error).message));
    return () => {
      cancelled = true;
    };
  }, [selected]);

  async function linkChild(event: React.FormEvent) {
    event.preventDefault();
    setLinking(true);
    setError(null);
    try {
      await api.parent.linkChild(linkEmail.trim());
      setLinkEmail('');
      await loadChildren();
    } catch (caught) {
      setError((caught as Error).message);
    } finally {
      setLinking(false);
    }
  }

  if (authLoading || !user) return <AppShell role="parent" loading />;

  const activeChild = children?.find((child) => child.student_id === selected) ?? null;

  return (
    <AppShell role="parent">
      <div className="mx-auto w-full max-w-5xl px-5 py-8 sm:px-8 lg:py-10">
        <h1 className="font-display text-3xl sm:text-4xl">{t('parent.title')}</h1>
        <p className="mt-1 text-ink-600">{user.full_name}</p>

        {error && (
          <Alert tone="error" className="mt-5">
            {error}
          </Alert>
        )}

        {!children && !error && (
          <div className="flex justify-center py-24">
            <Spinner className="h-8 w-8 text-brand-500" />
            <span className="sr-only">{t('common.loading')}</span>
          </div>
        )}

        {children && children.length === 0 && (
          <EmptyState
            className="mt-8"
            icon={<Users className="h-10 w-10" />}
            title={t('parent.noChildren')}
            description={t('parent.linkAria')}
          />
        )}

        {children && children.length > 0 && (
          <>
            <div className="mt-8 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
              {children.map((child) => (
                <button
                  key={child.student_id}
                  type="button"
                  onClick={() => setSelected(child.student_id)}
                  aria-pressed={selected === child.student_id}
                  className="text-left"
                >
                  <Card
                    interactive
                    className={
                      selected === child.student_id
                        ? 'border-brand-500 shadow-lift'
                        : undefined
                    }
                  >
                    <div className="flex items-center gap-3">
                      <Avatar name={child.name} src={child.avatar_url} size="lg" />
                      <div className="min-w-0">
                        <p className="truncate font-display text-lg">{child.name}</p>
                        <p className="text-sm text-ink-500">
                          {t('common.grade')} {child.grade}
                        </p>
                      </div>
                    </div>

                    <ProgressBar
                      className="mt-4"
                      value={child.average_mastery_percent}
                      label={t('dashboard.overallMastery')}
                      showValue
                    />

                    <div className="mt-4 flex flex-wrap gap-2">
                      <Badge tone="sun">
                        <Flame className="h-3.5 w-3.5" aria-hidden="true" />
                        {child.streak_days} {t('dashboard.streak')}
                      </Badge>
                      <Badge tone="teal">
                        {child.skills_mastered} {t('dashboard.skillsMastered')}
                      </Badge>
                    </div>

                    <p className="mt-3 text-xs text-ink-500">
                      {child.last_active_at
                        ? `${t('progress.lastPractised', { date: formatDate(child.last_active_at) })}`
                        : t('progress.neverPractised')}
                    </p>
                  </Card>
                </button>
              ))}
            </div>

            {activeChild && (
              <section className="mt-10">
                <h2 className="flex items-center gap-2 font-display text-2xl">
                  <TrendingUp className="h-5 w-5 text-brand-600" aria-hidden="true" />
                  {activeChild.name} — {t('parent.childProgress')}
                </h2>

                {!progress ? (
                  <div className="flex justify-center py-12">
                    <Spinner className="h-6 w-6 text-brand-400" />
                  </div>
                ) : (
                  <div className="mt-5 grid gap-6 lg:grid-cols-2">
                    <Card>
                      <h3 className="font-display text-lg">{t('progress.bySubject')}</h3>
                      {progress.subjects.length === 0 ? (
                        <p className="mt-3 text-sm text-ink-500">{t('dashboard.noActivity')}</p>
                      ) : (
                        <div className="mt-4 space-y-4">
                          {progress.subjects.map((subject) => (
                            <ProgressBar
                              key={subject.slug}
                              value={subject.mastery_percent}
                              label={subject.name}
                              tone={subject.slug === 'physics' ? 'teal' : 'brand'}
                              showValue
                            />
                          ))}
                        </div>
                      )}

                      <dl className="mt-6 grid grid-cols-3 gap-3 border-t-2 border-ink-100 pt-4 text-center">
                        <div>
                          <dt className="text-xs text-ink-500">
                            {t('dashboard.questionsAnswered')}
                          </dt>
                          <dd className="font-display text-xl">{progress.stats.total_attempts}</dd>
                        </div>
                        <div>
                          <dt className="text-xs text-ink-500">{t('dashboard.accuracy')}</dt>
                          <dd className="font-display text-xl">
                            {progress.stats.accuracy === null
                              ? '—'
                              : `${Math.round(progress.stats.accuracy * 100)}%`}
                          </dd>
                        </div>
                        <div>
                          <dt className="text-xs text-ink-500">
                            {t('dashboard.skillsMastered')}
                          </dt>
                          <dd className="font-display text-xl">
                            {progress.stats.skills_mastered}
                          </dd>
                        </div>
                      </dl>
                    </Card>

                    <Card>
                      <h3 className="font-display text-lg">{t('dashboard.weakSkills')}</h3>
                      {progress.weak_skills.length === 0 ? (
                        <p className="mt-3 text-sm text-ink-500">{t('common.emptyState')}</p>
                      ) : (
                        <ul className="mt-4 space-y-3">
                          {progress.weak_skills.map((skill) => (
                            <li key={skill.skill_slug}>
                              <ProgressBar
                                value={skill.mastery_percent}
                                label={skill.skill_name}
                                tone="coral"
                                size="sm"
                                showValue
                              />
                              <p className="mt-1 text-xs text-ink-500">
                                {skill.attempts} {t('progress.attempts')}
                                {skill.accuracy !== null &&
                                  ` · ${Math.round(skill.accuracy * 100)}% ${t('dashboard.accuracy').toLowerCase()}`}
                              </p>
                            </li>
                          ))}
                        </ul>
                      )}
                    </Card>
                  </div>
                )}
              </section>
            )}
          </>
        )}

        <Card className="mt-10">
          <h2 className="font-display text-xl">{t('parent.linkChild')}</h2>
          <p className="mt-1 text-sm text-ink-600">{t('parent.linkHint')}</p>
          <form onSubmit={linkChild} className="mt-4 flex flex-wrap items-end gap-3">
            <div className="min-w-[16rem] flex-1">
              <Field label={t('auth.email')} htmlFor="link_email" required>
                <Input
                  id="link_email"
                  type="email"
                  required
                  value={linkEmail}
                  onChange={(event) => setLinkEmail(event.target.value)}
                />
              </Field>
            </div>
            <Button type="submit" loading={linking}>
              {t('parent.linkChild')}
            </Button>
          </form>
        </Card>

        <Card className="mt-6 bg-sun-50">
          <h2 className="flex items-center gap-2 font-display text-lg">
            <CalendarClock className="h-5 w-5 text-sun-700" aria-hidden="true" />
            {t('parent.schedule')} &amp; {t('parent.payments')}
          </h2>
          <p className="mt-2 text-sm text-ink-700">
            Attendance records, upcoming class schedules and payment history for each child are
            available from the navigation. They populate once a child is enrolled in a class.
          </p>
        </Card>
      </div>
    </AppShell>
  );
}
