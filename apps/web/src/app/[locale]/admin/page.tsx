'use client';

import Link from 'next/link';
import {
  Activity,
  BookOpen,
  CalendarDays,
  ClipboardList,
  FileText,
  FolderPlus,
  GraduationCap,
  MessageSquare,
  Plus,
  UserCheck,
  Users,
  Wallet,
} from 'lucide-react';
import { useCallback, useEffect, useState } from 'react';

import { Alert, Badge, Button, Card, EmptyState, Spinner } from '@hietedu/ui';

import { AdminShell } from '@/components/admin/admin-shell';
import { StatusBadge, useEnumLabel } from '@/components/admin/form';
import { adminApi, type AdminOverview, type DashboardFeed } from '@/lib/admin-api';
import { useRequireAuth } from '@/lib/auth';
import { useI18n } from '@/lib/i18n';

export default function AdminDashboardPage() {
  const { t, locale, formatCurrency, formatDateTime, formatDate } = useI18n();
  const enumLabel = useEnumLabel();
  const { user, loading: authLoading } = useRequireAuth(locale, ['admin']);

  const [overview, setOverview] = useState<AdminOverview | null>(null);
  const [feed, setFeed] = useState<DashboardFeed | null>(null);
  const [error, setError] = useState<string | null>(null);

  const href = useCallback((path: string) => `/${locale}${path}`, [locale]);

  useEffect(() => {
    if (!user) return;
    Promise.all([adminApi.overview(), adminApi.dashboard()])
      .then(([o, f]) => {
        setOverview(o);
        setFeed(f);
      })
      .catch((caught) => setError((caught as Error).message));
  }, [user]);

  if (authLoading || !user) return <AdminShell loading />;

  const tiles = overview
    ? [
        { icon: Users, label: t('admin.tea.students'), value: overview.students,
          sub: t('admin.dash.activeCount', { count: overview.active_students }), href: '/admin/students' },
        { icon: GraduationCap, label: t('admin.tea.title'), value: overview.teachers,
          href: '/admin/teachers' },
        { icon: BookOpen, label: t('admin.crs.title'), value: overview.courses,
          sub: t('admin.dash.publishedCount', { count: overview.published_courses }), href: '/admin/courses' },
        { icon: FileText, label: t('admin.les.title'), value: overview.lessons,
          sub: t('admin.dash.draftCount', { count: overview.draft_lessons }), href: '/admin/lessons' },
        { icon: ClipboardList, label: t('admin.ex.title'), value: overview.exercises,
          sub: t('admin.dash.publishedCount', { count: overview.published_exercises }), href: '/admin/exercises' },
        { icon: UserCheck, label: t('admin.dash.activeEnrollments'), value: overview.active_enrollments,
          sub: t('admin.dash.pendingCount', { count: overview.pending_enrollments }), href: '/admin/enrollments' },
        { icon: MessageSquare, label: t('admin.dash.openConsultations'),
          value: overview.pending_consultations + overview.pending_registrations,
          sub: t('admin.dash.newCount', { count: overview.new_consultations + overview.new_registrations }),
          href: '/admin/consultations' },
        { icon: CalendarDays, label: t('admin.dash.upcomingClasses'), value: overview.upcoming_classes,
          href: '/admin/classes' },
      ]
    : [];

  const quickActions = [
    { label: t('admin.crs.createCourse'), icon: BookOpen, href: '/admin/courses?new=1' },
    { label: t('admin.dash.createLesson'), icon: FileText, href: '/admin/lessons?new=1' },
    { label: t('admin.dash.createTopic'), icon: FolderPlus, href: '/admin/categories?new=1' },
    { label: t('admin.dash.addExercise'), icon: ClipboardList, href: '/admin/exercises?new=1' },
    { label: t('admin.dash.manageStudents'), icon: Users, href: '/admin/students' },
    { label: t('admin.dash.manageTeachers'), icon: GraduationCap, href: '/admin/teachers' },
    { label: t('admin.dash.consultationRequests'), icon: MessageSquare, href: '/admin/consultations' },
  ];

  return (
    <AdminShell
      title={t('admin.dash.title')}
      description={t('admin.dash.subtitle')}
    >
      {error && (
        <Alert tone="error" className="mb-6">
          {error}
        </Alert>
      )}

      {!overview && !error && (
        <div className="flex justify-center py-24">
          <Spinner className="h-8 w-8 text-brand-500" />
          <span className="sr-only">{t('admin.dash.loading')}</span>
        </div>
      )}

      {overview && (
        <>
          {/* quick actions */}
          <section aria-labelledby="quick-actions" className="mb-8">
            <h2 id="quick-actions" className="sr-only">{t('admin.dash.quickActions')}</h2>
            <div className="flex flex-wrap gap-2">
              {quickActions.map((action) => (
                <Link key={action.label} href={href(action.href)}>
                  <Button size="sm" variant="outline">
                    <action.icon className="h-4 w-4" aria-hidden="true" />
                    {action.label}
                  </Button>
                </Link>
              ))}
            </div>
          </section>

          {/* stats */}
          <dl className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {tiles.map((tile) => (
              <Link key={tile.label} href={href(tile.href)} className="group">
                <Card className="flex h-full items-center gap-4 transition-shadow group-hover:shadow-pop-sm">
                  <span className="inline-flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl bg-brand-100 text-brand-700">
                    <tile.icon className="h-5 w-5" aria-hidden="true" />
                  </span>
                  <div className="min-w-0">
                    <dt className="truncate text-xs font-semibold text-ink-500">{tile.label}</dt>
                    <dd className="font-display text-2xl tabular-nums">{tile.value}</dd>
                    {tile.sub && <p className="truncate text-xs text-ink-500">{tile.sub}</p>}
                  </div>
                </Card>
              </Link>
            ))}
          </dl>

          <div className="mt-4 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <Card className="flex items-center gap-4">
              <span className="inline-flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl bg-teal-100 text-teal-700">
                <Wallet className="h-5 w-5" aria-hidden="true" />
              </span>
              <div className="min-w-0">
                <p className="truncate text-xs font-semibold text-ink-500">{t('admin.dash.revenue')}</p>
                <p className="font-display text-xl">{formatCurrency(overview.revenue_vnd)}</p>
              </div>
            </Card>
            <Card className="flex items-center gap-4">
              <span className="inline-flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl bg-sun-100 text-sun-700">
                <Activity className="h-5 w-5" aria-hidden="true" />
              </span>
              <div className="min-w-0">
                <p className="truncate text-xs font-semibold text-ink-500">{t('admin.dash.attemptsWeek')}</p>
                <p className="font-display text-xl tabular-nums">
                  {feed?.attempts_this_week ?? 0}
                </p>
              </div>
            </Card>
            <Card className="flex items-center gap-4">
              <span className="inline-flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl bg-coral-100 text-coral-700">
                <Users className="h-5 w-5" aria-hidden="true" />
              </span>
              <div className="min-w-0">
                <p className="truncate text-xs font-semibold text-ink-500">{t('admin.dash.newStudentsWeek')}</p>
                <p className="font-display text-xl tabular-nums">
                  {overview.new_students_this_week}
                </p>
              </div>
            </Card>
            <Card className="flex items-center gap-4">
              <span className="inline-flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl bg-ink-100 text-ink-700">
                <Wallet className="h-5 w-5" aria-hidden="true" />
              </span>
              <div className="min-w-0">
                <p className="truncate text-xs font-semibold text-ink-500">{t('admin.dash.awaitingPayment')}</p>
                <p className="font-display text-xl tabular-nums">
                  {overview.orders_awaiting_payment}
                </p>
              </div>
            </Card>
          </div>

          {overview.pending_review_questions > 0 && (
            <Alert tone="warning" className="mt-6" title={t('admin.dash.reviewAlert')}>
              {overview.pending_review_questions} exercise(s) are pending review and are not being
              served to students.{' '}
              <Link
                href={href('/admin/exercises?status=pending_review')}
                className="font-bold underline"
              >{t('admin.dash.reviewThem')}</Link>
            </Alert>
          )}

          {/* work queues */}
          <div className="mt-8 grid gap-6 lg:grid-cols-2">
            <section aria-labelledby="consultations-heading">
              <div className="mb-3 flex items-center justify-between">
                <h2 id="consultations-heading" className="font-display text-xl">{t('admin.dash.latestConsultations')}</h2>
                <Link
                  href={href('/admin/consultations')}
                  className="text-sm font-bold text-brand-600 hover:underline"
                >{t('admin.a.viewAll')}</Link>
              </div>
              <Card className="p-0">
                {!feed?.recent_consultations.length ? (
                  <EmptyState
                    className="border-0"
                    title={t('admin.dash.noRequests')}
                    description={t('admin.dash.noRequestsBody')}
                  />
                ) : (
                  <ul className="divide-y divide-ink-100">
                    {feed.recent_consultations.slice(0, 6).map((lead) => (
                      <li key={`${lead.source}-${lead.id}`}>
                        <Link
                          href={href(`/admin/consultations/${lead.source}/${lead.id}`)}
                          className="flex flex-wrap items-center gap-3 px-4 py-3 hover:bg-brand-50/50"
                        >
                          <div className="min-w-0 flex-1">
                            <p className="truncate font-bold text-ink-900">{lead.name}</p>
                            <p className="truncate text-xs text-ink-500">
                              {lead.email} · {enumLabel(lead.interest)}
                            </p>
                          </div>
                          <StatusBadge value={lead.status} kind="lead" />
                          <span className="text-xs text-ink-400">
                            {formatDate(lead.created_at)}
                          </span>
                        </Link>
                      </li>
                    ))}
                  </ul>
                )}
              </Card>
            </section>

            <section aria-labelledby="enrollments-heading">
              <div className="mb-3 flex items-center justify-between">
                <h2 id="enrollments-heading" className="font-display text-xl">{t('admin.dash.pendingEnrollments')}</h2>
                <Link
                  href={href('/admin/enrollments?status=pending')}
                  className="text-sm font-bold text-brand-600 hover:underline"
                >{t('admin.a.viewAll')}</Link>
              </div>
              <Card className="p-0">
                {!feed?.pending_enrollments.length ? (
                  <EmptyState
                    className="border-0"
                    title={t('admin.dash.nothingPending')}
                    description={t('admin.dash.nothingPendingBody')}
                  />
                ) : (
                  <ul className="divide-y divide-ink-100">
                    {feed.pending_enrollments.map((enrollment) => (
                      <li
                        key={enrollment.id}
                        className="flex flex-wrap items-center gap-3 px-4 py-3"
                      >
                        <div className="min-w-0 flex-1">
                          <p className="truncate font-bold text-ink-900">
                            {enrollment.student_name ?? t('admin.dash.unknownStudent')}
                          </p>
                          <p className="truncate text-xs text-ink-500">{enrollment.class_name}</p>
                        </div>
                        <StatusBadge value={enrollment.payment_status} kind="payment" />
                      </li>
                    ))}
                  </ul>
                )}
              </Card>
            </section>

            <section aria-labelledby="upcoming-heading">
              <div className="mb-3 flex items-center justify-between">
                <h2 id="upcoming-heading" className="font-display text-xl">{t('admin.dash.upcomingClasses')}</h2>
                <Link
                  href={href('/admin/classes')}
                  className="text-sm font-bold text-brand-600 hover:underline"
                >{t('admin.dash.schedule')}</Link>
              </div>
              <Card className="p-0">
                {!feed?.upcoming_classes.length ? (
                  <EmptyState
                    className="border-0"
                    title={t('admin.dash.noClasses')}
                    description={t('admin.dash.noClassesBody')}
                    action={
                      <Link href={href('/admin/classes')}>
                        <Button size="sm">
                          <Plus className="h-4 w-4" aria-hidden="true" />{t('admin.dash.createClass')}</Button>
                      </Link>
                    }
                  />
                ) : (
                  <ul className="divide-y divide-ink-100">
                    {feed.upcoming_classes.map((session) => (
                      <li key={session.id} className="flex flex-wrap items-center gap-3 px-4 py-3">
                        <div className="min-w-0 flex-1">
                          <p className="truncate font-bold text-ink-900">{session.title}</p>
                          <p className="truncate text-xs text-ink-500">{session.class_name}</p>
                        </div>
                        <span className="text-xs font-semibold text-ink-600">
                          {formatDateTime(session.starts_at)}
                        </span>
                      </li>
                    ))}
                  </ul>
                )}
              </Card>
            </section>

            <section aria-labelledby="students-heading">
              <div className="mb-3 flex items-center justify-between">
                <h2 id="students-heading" className="font-display text-xl">{t('admin.dash.recentStudents')}</h2>
                <Link
                  href={href('/admin/students')}
                  className="text-sm font-bold text-brand-600 hover:underline"
                >{t('admin.a.viewAll')}</Link>
              </div>
              <Card className="p-0">
                {!feed?.recent_students.length ? (
                  <EmptyState className="border-0" title={t('admin.dash.noStudents')} />
                ) : (
                  <ul className="divide-y divide-ink-100">
                    {feed.recent_students.map((student) => (
                      <li key={student.id}>
                        <Link
                          href={href(`/admin/students/${student.id}`)}
                          className="flex flex-wrap items-center gap-3 px-4 py-3 hover:bg-brand-50/50"
                        >
                          <div className="min-w-0 flex-1">
                            <p className="truncate font-bold text-ink-900">{student.name}</p>
                            <p className="truncate text-xs text-ink-500">{student.email}</p>
                          </div>
                          <Badge tone="neutral">{t('admin.a.gradeN', { n: student.grade })}</Badge>
                          {!student.is_active && <Badge tone="coral">{t('admin.dash.inactive')}</Badge>}
                        </Link>
                      </li>
                    ))}
                  </ul>
                )}
              </Card>
            </section>
          </div>

          {/* activity */}
          <section aria-labelledby="activity-heading" className="mt-8">
            <div className="mb-3 flex items-center justify-between">
              <h2 id="activity-heading" className="font-display text-xl">{t('admin.dash.recentActivity')}</h2>
              <Link
                href={href('/admin/audit')}
                className="text-sm font-bold text-brand-600 hover:underline"
              >{t('admin.dash.fullLog')}</Link>
            </div>
            <Card className="p-0">
              {!feed?.recent_activity.length ? (
                <EmptyState
                  className="border-0"
                  title={t('admin.dash.noActivity')}
                  description={t('admin.dash.noActivityBody')}
                />
              ) : (
                <ul className="divide-y divide-ink-100">
                  {feed.recent_activity.map((entry) => (
                    <li key={entry.id} className="flex flex-wrap items-center gap-3 px-4 py-3">
                      <Badge tone="neutral">{enumLabel(entry.action)}</Badge>
                      <p className="min-w-0 flex-1 truncate text-sm text-ink-700">
                        {entry.summary}
                      </p>
                      <span className="text-xs text-ink-400">
                        {entry.actor ?? t('admin.aud.system')} · {formatDateTime(entry.created_at)}
                      </span>
                    </li>
                  ))}
                </ul>
              )}
            </Card>
          </section>
        </>
      )}
    </AdminShell>
  );
}
