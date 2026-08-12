'use client';

import Link from 'next/link';
import {
  ArrowRight,
  BookOpen,
  CalendarClock,
  CheckCircle2,
  Flame,
  Target,
  TrendingUp,
  Trophy,
  XCircle,
  Zap,
} from 'lucide-react';
import { useEffect, useState } from 'react';

import { Badge, Button, Card, EmptyState, ProgressBar, Spinner } from '@hietedu/ui';

import { AppShell } from '@/components/app/app-shell';
import { api, type Dashboard } from '@/lib/api';
import { useRequireAuth } from '@/lib/auth';
import { useI18n } from '@/lib/i18n';
import { masteryPercent } from '@/lib/utils';

const STUDENT_ROLES = ['student'] as const;

export default function DashboardPage({ params }: { params: Promise<{ locale: string }> }) {
  const { t, locale, formatDateTime, formatRelativeDay } = useI18n();
  const { user, loading: authLoading } = useRequireAuth(locale, [...STUDENT_ROLES]);
  const [data, setData] = useState<Dashboard | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!user) return;
    let cancelled = false;
    api.progress
      .dashboard()
      .then((result) => !cancelled && setData(result))
      .catch((caught) => !cancelled && setError((caught as Error).message));
    return () => {
      cancelled = true;
    };
  }, [user]);

  const href = (path: string) => `/${locale}${path}`;

  if (authLoading || !user) {
    return <AppShell role="student" loading />;
  }

  return (
    <AppShell role="student">
      <div className="mx-auto w-full max-w-6xl px-5 py-8 sm:px-8 lg:py-10">
        {!data && !error && (
          <div className="flex justify-center py-24">
            <Spinner className="h-8 w-8 text-brand-500" />
            <span className="sr-only">{t('common.loading')}</span>
          </div>
        )}

        {error && (
          <Card className="border-red-200 bg-red-50">
            <p className="font-bold text-red-800">{t('common.error')}</p>
            <p className="mt-1 text-sm text-red-700">{error}</p>
          </Card>
        )}

        {data && (
          <>
            {/* ---------------------------------------------------------- header */}
            <header className="flex flex-wrap items-end justify-between gap-4">
              <div>
                <h1 className="font-display text-3xl sm:text-4xl">
                  {t(data.stats.total_attempts > 0 ? 'dashboard.welcome' : 'dashboard.welcomeNew', {
                    name: data.student.name?.split(' ').slice(-1)[0] ?? '',
                  })}{' '}
                  <span aria-hidden="true">👋</span>
                </h1>
                <p className="mt-1 text-ink-600">
                  {t('common.grade')} {data.student.grade}
                </p>
              </div>

              <div className="flex flex-wrap gap-2">
                <Badge tone="sun">
                  <Flame className="h-3.5 w-3.5" aria-hidden="true" />
                  {data.student.streak_days} {t('dashboard.streak')}
                </Badge>
                <Badge tone="brand">
                  <Zap className="h-3.5 w-3.5" aria-hidden="true" />
                  {t('dashboard.level')} {data.student.level}
                </Badge>
                <Badge tone="teal">
                  <Trophy className="h-3.5 w-3.5" aria-hidden="true" />
                  {data.stats.skills_mastered} {t('dashboard.skillsMastered')}
                </Badge>
              </div>
            </header>

            {/* ---------------------------------------------------------- progress */}
            <div className="mt-8 grid gap-6 lg:grid-cols-3">
              <Card className="lg:col-span-2">
                <div className="flex items-baseline justify-between">
                  <h2 className="font-display text-xl">{t('dashboard.yourProgress')}</h2>
                  <Link
                    href={href('/progress')}
                    className="text-sm font-bold text-brand-700 hover:underline"
                  >
                    {t('common.viewAll')}
                  </Link>
                </div>

                <ProgressBar
                  className="mt-5"
                  value={data.overall_mastery_percent}
                  label={t('dashboard.overallMastery')}
                  size="lg"
                  showValue
                />

                <div className="mt-6 space-y-4">
                  {data.subjects.length === 0 && (
                    <p className="text-sm text-ink-500">{t('dashboard.noActivity')}</p>
                  )}
                  {data.subjects.map((subject) => (
                    <ProgressBar
                      key={subject.subject_slug}
                      value={subject.mastery_percent}
                      label={subject.subject_name}
                      tone={subject.subject_slug === 'physics' ? 'teal' : 'brand'}
                      showValue
                    />
                  ))}
                </div>

                <dl className="mt-7 grid grid-cols-3 gap-4 border-t-2 border-ink-100 pt-5 text-center">
                  <div>
                    <dt className="text-xs font-semibold text-ink-500">
                      {t('dashboard.questionsAnswered')}
                    </dt>
                    <dd className="font-display text-2xl">{data.stats.total_attempts}</dd>
                  </div>
                  <div>
                    <dt className="text-xs font-semibold text-ink-500">
                      {t('dashboard.accuracy')}
                    </dt>
                    <dd className="font-display text-2xl">
                      {data.stats.accuracy === null
                        ? '—'
                        : `${Math.round(data.stats.accuracy * 100)}%`}
                    </dd>
                  </div>
                  <div>
                    <dt className="text-xs font-semibold text-ink-500">{t('dashboard.xp')}</dt>
                    <dd className="font-display text-2xl">{data.student.xp_total}</dd>
                  </div>
                </dl>
              </Card>

              {/* ------------------------------------------------------ recommendations */}
              <Card className="border-brand-200 bg-brand-50">
                <h2 className="flex items-center gap-2 font-display text-xl">
                  <Target className="h-5 w-5 text-brand-600" aria-hidden="true" />
                  {t('dashboard.recommended')}
                </h2>
                <p className="mt-1 text-sm text-ink-600">{t('dashboard.recommendedSubtitle')}</p>

                {data.recommendations.length === 0 ? (
                  <p className="mt-4 text-sm text-ink-500">{t('common.emptyState')}</p>
                ) : (
                  <ol className="mt-4 space-y-2.5">
                    {data.recommendations.map((recommendation, index) => (
                      <li key={recommendation.skill_id}>
                        <Link
                          href={href(`/practice/${recommendation.skill_slug}`)}
                          className="group flex items-center gap-3 rounded-2xl border-2 border-white bg-white p-3 transition-all hover:border-brand-300 hover:shadow-soft"
                        >
                          <span className="inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-xl bg-brand-100 font-display text-sm font-extrabold text-brand-700">
                            {index + 1}
                          </span>
                          <span className="min-w-0 flex-1">
                            <span className="block truncate text-sm font-bold text-ink-900">
                              {recommendation.skill_name}
                            </span>
                            <span className="block truncate text-xs text-ink-500">
                              {recommendation.detail}
                            </span>
                          </span>
                          <span className="shrink-0 text-xs font-bold tabular-nums text-brand-700">
                            {masteryPercent(recommendation.mastery)}%
                          </span>
                          <ArrowRight
                            className="h-4 w-4 shrink-0 text-brand-500 transition-transform group-hover:translate-x-0.5"
                            aria-hidden="true"
                          />
                        </Link>
                      </li>
                    ))}
                  </ol>
                )}
              </Card>
            </div>

            {/* ---------------------------------------------------------- second row */}
            <div className="mt-6 grid gap-6 lg:grid-cols-3">
              {/* weak skills */}
              <Card>
                <h2 className="font-display text-lg">{t('dashboard.weakSkills')}</h2>
                {data.weak_skills.length === 0 ? (
                  <p className="mt-3 text-sm text-ink-500">{t('common.emptyState')}</p>
                ) : (
                  <ul className="mt-4 space-y-3">
                    {data.weak_skills.map((skill) => (
                      <li key={skill.skill_id}>
                        <Link
                          href={href(`/practice/${skill.skill_slug}`)}
                          className="block rounded-xl p-2 transition-colors hover:bg-ink-50"
                        >
                          <ProgressBar
                            value={masteryPercent(skill.mastery)}
                            label={skill.skill_name}
                            tone="coral"
                            size="sm"
                            showValue
                          />
                        </Link>
                      </li>
                    ))}
                  </ul>
                )}
              </Card>

              {/* upcoming classes */}
              <Card>
                <h2 className="flex items-center gap-2 font-display text-lg">
                  <CalendarClock className="h-5 w-5 text-teal-600" aria-hidden="true" />
                  {t('dashboard.upcomingClasses')}
                </h2>
                {data.upcoming_sessions.length === 0 ? (
                  <p className="mt-3 text-sm text-ink-500">{t('dashboard.noUpcoming')}</p>
                ) : (
                  <ul className="mt-4 space-y-3">
                    {data.upcoming_sessions.slice(0, 4).map((session) => (
                      <li key={session.id} className="rounded-2xl border-2 border-ink-100 p-3">
                        <p className="text-sm font-bold text-ink-900">{session.class_name}</p>
                        <p className="mt-0.5 text-xs text-ink-500">
                          {formatRelativeDay(session.starts_at)} ·{' '}
                          {formatDateTime(session.starts_at)}
                        </p>
                        {session.teacher_name && (
                          <p className="mt-0.5 text-xs text-ink-500">{session.teacher_name}</p>
                        )}
                        {session.join_url && (
                          <a
                            href={session.join_url}
                            target="_blank"
                            rel="noreferrer noopener"
                            className="mt-2 inline-block text-xs font-bold text-brand-700 hover:underline"
                          >
                            {t('nav.liveClasses')} →
                          </a>
                        )}
                      </li>
                    ))}
                  </ul>
                )}
              </Card>

              {/* recent attempts */}
              <Card>
                <h2 className="font-display text-lg">{t('dashboard.recentScores')}</h2>
                {data.recent_attempts.length === 0 ? (
                  <p className="mt-3 text-sm text-ink-500">{t('dashboard.noActivity')}</p>
                ) : (
                  <ul className="mt-4 space-y-2">
                    {data.recent_attempts.slice(0, 6).map((attempt) => (
                      <li key={attempt.id} className="flex items-center gap-2.5 text-sm">
                        {attempt.is_correct ? (
                          <CheckCircle2
                            className="h-4 w-4 shrink-0 text-teal-500"
                            aria-label={t('a11y.correctAnswer')}
                          />
                        ) : (
                          <XCircle
                            className="h-4 w-4 shrink-0 text-coral-500"
                            aria-label={t('a11y.incorrectAnswer')}
                          />
                        )}
                        <span className="min-w-0 flex-1 truncate text-ink-700">
                          {attempt.skill_name}
                        </span>
                      </li>
                    ))}
                  </ul>
                )}
              </Card>
            </div>

            {/* ---------------------------------------------------------- courses */}
            <section className="mt-10">
              <div className="flex items-baseline justify-between">
                <h2 className="font-display text-2xl">{t('dashboard.myCourses')}</h2>
                <Link
                  href={href('/courses')}
                  className="text-sm font-bold text-brand-700 hover:underline"
                >
                  {t('dashboard.browseCourses')}
                </Link>
              </div>

              {data.enrolled_courses.length === 0 ? (
                <EmptyState
                  className="mt-5"
                  icon={<BookOpen className="h-10 w-10" />}
                  title={t('dashboard.noCourses')}
                  action={
                    <Link href={href('/courses')}>
                      <Button>{t('dashboard.browseCourses')}</Button>
                    </Link>
                  }
                />
              ) : (
                <div className="mt-5 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                  {data.enrolled_courses.map((course) => (
                    <Link key={course.course_id} href={href(`/courses/${course.slug}`)}>
                      <Card interactive className="h-full">
                        <Badge tone={course.slug.startsWith('physics') ? 'teal' : 'brand'}>
                          {t('common.grade')} {course.grade}
                        </Badge>
                        <h3 className="mt-3 font-display text-lg">{course.title}</h3>
                        <p className="mt-3 flex items-center gap-1.5 text-sm font-bold text-brand-700">
                          {t('courses.continue')}
                          <ArrowRight className="h-4 w-4" aria-hidden="true" />
                        </p>
                      </Card>
                    </Link>
                  ))}
                </div>
              )}
            </section>

            {/* ---------------------------------------------------------- achievements */}
            {data.achievements.length > 0 && (
              <section className="mt-10">
                <h2 className="font-display text-2xl">{t('dashboard.achievements')}</h2>
                <ul className="mt-5 flex flex-wrap gap-3">
                  {data.achievements.map((achievement) => (
                    <li key={achievement.slug}>
                      <div
                        className="flex items-center gap-3 rounded-2xl border-2 border-ink-100 bg-white px-4 py-3 shadow-soft"
                        title={achievement.description}
                      >
                        <span
                          className={`inline-flex h-10 w-10 items-center justify-center rounded-xl ${
                            achievement.tier === 'gold'
                              ? 'bg-sun-200 text-sun-800'
                              : achievement.tier === 'silver'
                                ? 'bg-ink-200 text-ink-700'
                                : 'bg-coral-100 text-coral-700'
                          }`}
                        >
                          <Trophy className="h-5 w-5" aria-hidden="true" />
                        </span>
                        <div>
                          <p className="text-sm font-bold text-ink-900">{achievement.name}</p>
                          <p className="text-xs text-ink-500">{achievement.description}</p>
                        </div>
                      </div>
                    </li>
                  ))}
                </ul>
              </section>
            )}

            {/* ---------------------------------------------------------- activity */}
            {data.activity.length > 0 && (
              <section className="mt-10">
                <h2 className="flex items-center gap-2 font-display text-2xl">
                  <TrendingUp className="h-5 w-5 text-brand-600" aria-hidden="true" />
                  {t('dashboard.activity')}
                </h2>
                <Card className="mt-5">
                  <ActivityHeatmap activity={data.activity} />
                </Card>
              </section>
            )}
          </>
        )}
      </div>
    </AppShell>
  );
}

function ActivityHeatmap({ activity }: { activity: { date: string; xp: number }[] }) {
  const byDate = new Map(activity.map((entry) => [entry.date, entry.xp]));
  const max = Math.max(1, ...activity.map((entry) => entry.xp));

  // 12 weeks back, aligned so each column is a week.
  const days: { date: string; xp: number }[] = [];
  const today = new Date();
  for (let offset = 83; offset >= 0; offset -= 1) {
    const date = new Date(today);
    date.setDate(today.getDate() - offset);
    const key = date.toISOString().slice(0, 10);
    days.push({ date: key, xp: byDate.get(key) ?? 0 });
  }

  const intensity = (xp: number) => {
    if (xp === 0) return 'bg-ink-100';
    const ratio = xp / max;
    if (ratio > 0.66) return 'bg-brand-600';
    if (ratio > 0.33) return 'bg-brand-400';
    return 'bg-brand-200';
  };

  return (
    <div className="scroll-x">
      <div className="grid min-w-[38rem] grid-flow-col grid-rows-7 gap-1">
        {days.map((day) => (
          <div
            key={day.date}
            className={`h-4 w-4 rounded ${intensity(day.xp)}`}
            title={`${day.date}: ${day.xp} XP`}
          />
        ))}
      </div>
    </div>
  );
}
