'use client';

import Link from 'next/link';
import { AlertTriangle, BarChart3, CalendarDays, ClipboardList, Users } from 'lucide-react';
import { useEffect, useState } from 'react';

import { Badge, Card, EmptyState, ProgressBar, Spinner } from '@hietedu/ui';

import { AppShell } from '@/components/app/app-shell';
import { api } from '@/lib/api';
import { useRequireAuth } from '@/lib/auth';
import { useI18n } from '@/lib/i18n';

interface StudentRow {
  student_id: number;
  name: string;
  grade: number;
  email: string;
  average_mastery: number;
  skills_mastered: number;
  attempts: number;
  accuracy: number | null;
  last_active_at: string | null;
}

interface Analytics {
  student_count: number;
  class_average_mastery_percent: number;
  total_attempts: number;
  completion_rate: number;
  hardest_questions: {
    id: number;
    slug: string;
    prompt: string;
    difficulty: number;
    times_served: number;
    success_rate: number;
  }[];
  weakest_skills: { skill_id: number; name: string; slug: string; average_mastery: number }[];
  most_common_mistakes: { skill: string; answer: string; count: number }[];
}

export default function TeacherDashboardPage({
  params,
}: {
  params: Promise<{ locale: string }>;
}) {
  const { t, locale, formatDate } = useI18n();
  const { user, loading: authLoading } = useRequireAuth(locale, ['teacher', 'admin']);

  const [students, setStudents] = useState<StudentRow[] | null>(null);
  const [analytics, setAnalytics] = useState<Analytics | null>(null);
  const [classes, setClasses] = useState<Record<string, unknown>[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!user) return;
    let cancelled = false;
    Promise.all([api.teacher.students(), api.teacher.analytics(), api.teacher.classes()])
      .then(([studentRows, analyticsResult, classRows]) => {
        if (cancelled) return;
        setStudents(studentRows as unknown as StudentRow[]);
        setAnalytics(analyticsResult as unknown as Analytics);
        setClasses(classRows);
      })
      .catch((caught) => !cancelled && setError((caught as Error).message));
    return () => {
      cancelled = true;
    };
  }, [user]);

  if (authLoading || !user) return <AppShell role="teacher" loading />;

  const loading = !students && !error;

  return (
    <AppShell role="teacher">
      <div className="mx-auto w-full max-w-6xl px-5 py-8 sm:px-8 lg:py-10">
        <header>
          <h1 className="font-display text-3xl sm:text-4xl">{t('teacher.title')}</h1>
          <p className="mt-1 text-ink-600">{user.full_name}</p>
        </header>

        {loading && (
          <div className="flex justify-center py-24">
            <Spinner className="h-8 w-8 text-brand-500" />
            <span className="sr-only">{t('common.loading')}</span>
          </div>
        )}

        {error && (
          <Card className="mt-6 border-red-200 bg-red-50">
            <p className="font-bold text-red-800">{t('common.error')}</p>
            <p className="mt-1 text-sm text-red-700">{error}</p>
          </Card>
        )}

        {analytics && (
          <>
            <dl className="mt-8 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
              <StatCard
                icon={Users}
                label={t('teacher.students')}
                value={analytics.student_count}
              />
              <StatCard
                icon={BarChart3}
                label={t('teacher.classAverage')}
                value={`${analytics.class_average_mastery_percent}%`}
              />
              <StatCard
                icon={ClipboardList}
                label={t('teacher.completionRate')}
                value={`${Math.round(analytics.completion_rate * 100)}%`}
              />
              <StatCard
                icon={CalendarDays}
                label={t('teacher.classes')}
                value={classes?.length ?? 0}
              />
            </dl>

            <div className="mt-8 grid gap-6 lg:grid-cols-2">
              <Card>
                <h2 className="font-display text-xl">{t('teacher.weakestSkills')}</h2>
                {analytics.weakest_skills.length === 0 ? (
                  <p className="mt-3 text-sm text-ink-500">{t('common.emptyState')}</p>
                ) : (
                  <ul className="mt-4 space-y-3">
                    {analytics.weakest_skills.map((skill) => (
                      <li key={skill.skill_id}>
                        <ProgressBar
                          value={Math.round(skill.average_mastery * 100)}
                          label={skill.name}
                          tone="coral"
                          size="sm"
                          showValue
                        />
                      </li>
                    ))}
                  </ul>
                )}
              </Card>

              <Card>
                <h2 className="flex items-center gap-2 font-display text-xl">
                  <AlertTriangle className="h-5 w-5 text-sun-600" aria-hidden="true" />
                  {t('teacher.commonMistakes')}
                </h2>
                {analytics.most_common_mistakes.length === 0 ? (
                  <p className="mt-3 text-sm text-ink-500">{t('common.emptyState')}</p>
                ) : (
                  <ul className="mt-4 space-y-2">
                    {analytics.most_common_mistakes.slice(0, 8).map((mistake, index) => (
                      <li
                        key={index}
                        className="flex items-center justify-between gap-3 rounded-xl bg-ink-50 px-3 py-2 text-sm"
                      >
                        <span className="min-w-0 flex-1 truncate text-ink-700">
                          {mistake.skill}
                        </span>
                        <code className="rounded bg-white px-2 py-0.5 font-mono text-xs text-coral-700">
                          {mistake.answer}
                        </code>
                        <Badge tone="neutral">×{mistake.count}</Badge>
                      </li>
                    ))}
                  </ul>
                )}
              </Card>
            </div>

            {analytics.hardest_questions.length > 0 && (
              <Card className="mt-6">
                <h2 className="font-display text-xl">{t('teacher.hardestQuestions')}</h2>
                <div className="scroll-x mt-4">
                  <table className="w-full min-w-[36rem] text-left text-sm">
                    <thead>
                      <tr className="border-b-2 border-ink-100">
                        <th scope="col" className="pb-2 font-display">{t('admin.ex.question')}</th>
                        <th scope="col" className="pb-2 font-display">
                          {t('common.difficulty')}
                        </th>
                        <th scope="col" className="pb-2 font-display">{t('teacher.qServed')}</th>
                        <th scope="col" className="pb-2 font-display">{t('teacher.qSuccess')}</th>
                      </tr>
                    </thead>
                    <tbody>
                      {analytics.hardest_questions.map((question) => (
                        <tr key={question.id} className="border-b border-ink-100">
                          <td className="max-w-md truncate py-2.5 pr-4 text-ink-700">
                            {question.prompt}
                          </td>
                          <td className="py-2.5 pr-4">{question.difficulty}/5</td>
                          <td className="py-2.5 pr-4 tabular-nums">{question.times_served}</td>
                          <td className="py-2.5">
                            <Badge tone={question.success_rate < 0.4 ? 'danger' : 'neutral'}>
                              {Math.round(question.success_rate * 100)}%
                            </Badge>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </Card>
            )}
          </>
        )}

        {students && (
          <section className="mt-10">
            <div className="flex items-baseline justify-between">
              <h2 className="font-display text-2xl">{t('teacher.students')}</h2>
              <Link
                href={`/${locale}/teacher/questions`}
                className="text-sm font-bold text-brand-700 hover:underline"
              >
                {t('teacher.questionBank')}
              </Link>
            </div>

            {students.length === 0 ? (
              <EmptyState className="mt-5" title={t('common.emptyState')} />
            ) : (
              <Card className="mt-5 p-0">
                <div className="scroll-x">
                  <table className="w-full min-w-[44rem] text-left text-sm">
                    <thead className="bg-ink-50">
                      <tr>
                        {['Student', t('common.grade'), t('dashboard.overallMastery'),
                          t('dashboard.skillsMastered'), t('dashboard.accuracy'),
                          'Last active'].map((heading) => (
                          <th key={heading} scope="col" className="px-4 py-3 font-display">
                            {heading}
                          </th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {students.map((student) => (
                        <tr key={student.student_id} className="border-t border-ink-100">
                          <td className="px-4 py-3">
                            <Link
                              href={`/${locale}/teacher/students/${student.student_id}`}
                              className="font-bold text-ink-900 hover:text-brand-700 hover:underline"
                            >
                              {student.name}
                            </Link>
                            <span className="block text-xs text-ink-500">{student.email}</span>
                          </td>
                          <td className="px-4 py-3">{student.grade}</td>
                          <td className="w-40 px-4 py-3">
                            <ProgressBar
                              value={Math.round(student.average_mastery * 100)}
                              size="sm"
                              showValue
                            />
                          </td>
                          <td className="px-4 py-3 tabular-nums">{student.skills_mastered}</td>
                          <td className="px-4 py-3 tabular-nums">
                            {student.accuracy === null
                              ? '—'
                              : `${Math.round(student.accuracy * 100)}%`}
                          </td>
                          <td className="px-4 py-3 text-xs text-ink-500">
                            {student.last_active_at ? formatDate(student.last_active_at) : '—'}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </Card>
            )}
          </section>
        )}
      </div>
    </AppShell>
  );
}

function StatCard({
  icon: Icon,
  label,
  value,
}: {
  icon: typeof Users;
  label: string;
  value: string | number;
}) {
  return (
    <Card className="flex items-center gap-4">
      <span className="inline-flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl bg-brand-100 text-brand-700">
        <Icon className="h-5 w-5" aria-hidden="true" />
      </span>
      <div className="min-w-0">
        <dt className="truncate text-xs font-semibold text-ink-500">{label}</dt>
        <dd className="font-display text-2xl">{value}</dd>
      </div>
    </Card>
  );
}
