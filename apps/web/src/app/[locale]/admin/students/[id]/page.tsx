'use client';

import { KeyRound, Pencil, UserX } from 'lucide-react';
import { use, useCallback, useEffect, useState } from 'react';

import { Alert, Badge, Button, Card, ProgressBar } from '@hietedu/ui';

import { AdminShell } from '@/components/admin/admin-shell';
import { Modal } from '@/components/admin/dialog';
import {
  FormRow,
  SelectField,
  StatusBadge,
  StringListField,
  TextField,
  useEnumLabel,
} from '@/components/admin/form';
import { useToast } from '@/components/admin/toast';
import { adminApi } from '@/lib/admin-api';
import { useRequireAuth } from '@/lib/auth';
import { useI18n } from '@/lib/i18n';

type Detail = Record<string, any>;

const TABS = [
  { id: 'overview', labelKey: 'admin.stu.tab.overview' },
  { id: 'courses', labelKey: 'admin.stu.tab.courses' },
  { id: 'progress', labelKey: 'admin.stu.tab.progress' },
  { id: 'work', labelKey: 'admin.stu.tab.work' },
  { id: 'attendance', labelKey: 'admin.stu.tab.attendance' },
  { id: 'enquiries', labelKey: 'admin.stu.tab.enquiries' },
] as const;

type TabId = (typeof TABS)[number]['id'];

export default function StudentDetailPage({
  params,
}: {
  params: Promise<{ locale: string; id: string }>;
}) {
  const { id } = use(params);
  const studentId = Number(id);
  const { t, locale, formatDate, formatDateTime, formatCurrency } = useI18n();
  const enumLabel = useEnumLabel();
  const { user, loading: authLoading } = useRequireAuth(locale, ['admin']);
  const { run, notify } = useToast();

  const [student, setStudent] = useState<Detail | null>(null);
  const [loading, setLoading] = useState(true);
  const [tab, setTab] = useState<TabId>('overview');
  const [editing, setEditing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [form, setForm] = useState({
    full_name: '',
    email: '',
    phone: '',
    grade: 6,
    school: '',
    learning_goals: [] as string[],
  });

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const result = (await adminApi.students.get(studentId)) as Detail;
      setStudent(result);
      setForm({
        full_name: result.full_name ?? '',
        email: result.email ?? '',
        phone: result.phone ?? '',
        grade: result.grade ?? 6,
        school: result.school ?? '',
        learning_goals: result.learning_goals ?? [],
      });
    } catch (caught) {
      notify((caught as Error).message, 'error');
    } finally {
      setLoading(false);
    }
  }, [studentId, notify]);

  useEffect(() => {
    if (user) void load();
  }, [user, load]);

  if (authLoading || !user) return <AdminShell loading />;

  const stats = student?.stats ?? {};

  return (
    <AdminShell
      title={student?.full_name ?? t('admin.st.student')}
      description={
        student
          ? t('admin.stu.metaLine', { email: student.email, grade: student.grade ?? '' })
          : undefined
      }
      breadcrumbs={[
        { label: t('admin.a.adminCrumb'), href: '/admin' },
        { label: t('admin.tea.students'), href: '/admin/students' },
        { label: student?.full_name ?? '…' },
      ]}
      actions={
        student && (
          <>
            <Button variant="outline" onClick={() => setEditing(true)}>
              <Pencil className="h-4 w-4" aria-hidden="true" />{t('admin.stu.editProfile')}</Button>
            <Button
              variant="outline"
              onClick={async () => {
                const result = await run(() => adminApi.students.resetPassword(studentId));
                if (result?.temporary_password) {
                  notify(
                    t('admin.stu.tempPasswordToast', { password: result.temporary_password }),
                    'info',
                    t('admin.stu.copyNow'),
                  );
                }
              }}
            >
              <KeyRound className="h-4 w-4" aria-hidden="true" />{t('admin.a.resetPassword')}</Button>
            <Button
              variant={student.is_active ? 'ghost' : 'primary'}
              onClick={async () => {
                const ok = await run(
                  () => adminApi.students.setActive(studentId, !student.is_active),
                  student.is_active ? t('admin.stu.accountDisabled') : t('admin.stu.accountEnabled'),
                );
                if (ok) await load();
              }}
            >
              <UserX className="h-4 w-4" aria-hidden="true" />
              {student.is_active ? t('admin.a.deactivate') : 'Activate'}
            </Button>
          </>
        )
      }
    >
      {loading || !student ? (
        <p className="py-16 text-center text-sm text-ink-500">{t('admin.a.loading')}</p>
      ) : (
        <>
          {!student.is_active && (
            <Alert tone="warning" className="mb-6" title={t('admin.stu.disabledAlert')}>{t('admin.stu.disabledAlertBody')}</Alert>
          )}

          <div className="mb-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <StatCard label={t('admin.stu.level')} value={String(student.level)} sub={`${student.xp_total} XP`} />
            <StatCard
              label={t('admin.stu.skillsMastered')}
              value={`${stats.skills_mastered ?? 0}/${stats.skills_tracked ?? 0}`}
            />
            <StatCard
              label={t('admin.stu.accuracy')}
              value={stats.accuracy != null ? `${Math.round(stats.accuracy * 100)}%` : '—'}
              sub={t('admin.stu.attemptCount', { count: stats.total_attempts ?? 0 })}
            />
            <StatCard
              label={t('admin.stu.attendance')}
              value={
                student.attendance_rate != null
                  ? `${Math.round(student.attendance_rate * 100)}%`
                  : '—'
              }
              sub={t('admin.stu.sessionCount', { count: (student.attendance ?? []).length })}
            />
          </div>

          <div className="mb-4 flex flex-wrap gap-2 border-b-2 border-ink-100">
            {TABS.map((entry) => (
              <button
                key={entry.id}
                type="button"
                onClick={() => setTab(entry.id)}
                aria-current={tab === entry.id ? 'true' : undefined}
                className={`-mb-0.5 border-b-4 px-3 py-2 text-sm font-bold ${
                  tab === entry.id
                    ? 'border-brand-500 text-brand-700'
                    : 'border-transparent text-ink-500 hover:text-ink-800'
                }`}
              >
                {t(entry.labelKey)}
              </button>
            ))}
          </div>

          {tab === 'overview' && (
            <div className="grid gap-4 lg:grid-cols-2">
              <Card>
                <h2 className="font-display text-lg">{t('admin.stu.profile')}</h2>
                <dl className="mt-4 grid gap-3 sm:grid-cols-2">
                  <Field label={t('admin.stu.fullName')} value={student.full_name} />
                  <Field label={t('admin.a.email')} value={student.email} />
                  <Field label={t('admin.a.phone')} value={student.phone ?? '—'} />
                  <Field label={t('admin.a.grade')} value={t('admin.a.gradeN', { n: student.grade })} />
                  <Field label={t('admin.stu.school')} value={student.school ?? '—'} />
                  <Field
                    label={t('admin.stu.dob')}
                    value={student.date_of_birth ? formatDate(student.date_of_birth) : '—'}
                  />
                  <Field label={t('admin.stu.joined')} value={formatDate(student.created_at)} />
                  <Field
                    label={t('admin.stu.lastSignIn')}
                    value={student.last_login_at ? formatDateTime(student.last_login_at) : t('admin.a.never')}
                  />
                  <Field
                    label={t('admin.stu.lastActivity')}
                    value={
                      student.last_activity_date ? formatDate(student.last_activity_date) : '—'
                    }
                  />
                  <Field label={t('admin.stu.streak')} value={t('admin.stu.streakValue', { count: student.streak_days })} />
                </dl>
                {(student.learning_goals ?? []).length > 0 && (
                  <div className="mt-4">
                    <p className="text-xs font-bold text-ink-500">{t('admin.stu.learningGoals')}</p>
                    <ul className="mt-1 flex flex-wrap gap-1.5">
                      {student.learning_goals.map((goal: string) => (
                        <li key={goal}>
                          <Badge tone="brand">{goal}</Badge>
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
              </Card>

              <Card>
                <h2 className="font-display text-lg">{t('admin.stu.guardians')}</h2>
                {(student.guardians ?? []).length === 0 ? (
                  <p className="mt-3 text-sm text-ink-500">{t('admin.stu.noGuardians')}</p>
                ) : (
                  <ul className="mt-3 divide-y divide-ink-100">
                    {student.guardians.map((guardian: Detail) => (
                      <li key={guardian.parent_id} className="py-2">
                        <p className="font-semibold text-ink-900">{guardian.name}</p>
                        <p className="text-xs text-ink-500">
                          {guardian.email} · {enumLabel(guardian.relationship)}
                        </p>
                      </li>
                    ))}
                  </ul>
                )}

                <h2 className="mt-6 font-display text-lg">{t('admin.stu.orders')}</h2>
                {(student.orders ?? []).length === 0 ? (
                  <p className="mt-3 text-sm text-ink-500">{t('admin.stu.noOrders')}</p>
                ) : (
                  <ul className="mt-3 divide-y divide-ink-100">
                    {student.orders.map((order: Detail) => (
                      <li key={order.id} className="flex items-center gap-3 py-2">
                        <span className="font-mono text-xs">{order.reference}</span>
                        <span className="ml-auto font-bold tabular-nums">
                          {formatCurrency(order.total)}
                        </span>
                        <Badge tone={order.status === 'paid' ? 'teal' : 'sun'}>
                          {enumLabel(order.status)}
                        </Badge>
                      </li>
                    ))}
                  </ul>
                )}
              </Card>
            </div>
          )}

          {tab === 'courses' && (
            <div className="grid gap-4 lg:grid-cols-2">
              <Card>
                <h2 className="font-display text-lg">{t('admin.stu.classes')}</h2>
                {(student.classes ?? []).length === 0 ? (
                  <p className="mt-3 text-sm text-ink-500">{t('admin.stu.notInClass')}</p>
                ) : (
                  <ul className="mt-3 divide-y divide-ink-100">
                    {student.classes.map((entry: Detail) => (
                      <li key={entry.enrollment_id} className="flex flex-wrap items-center gap-2 py-3">
                        <div className="min-w-0 flex-1">
                          <p className="truncate font-semibold text-ink-900">{entry.class_name}</p>
                          <p className="text-xs text-ink-500">
                            {enumLabel(entry.format ?? '')} · {enumLabel(entry.delivery_mode ?? '')}
                          </p>
                        </div>
                        <StatusBadge value={entry.status} kind="enrollment" />
                        <StatusBadge value={entry.payment_status} kind="payment" />
                      </li>
                    ))}
                  </ul>
                )}
              </Card>

              <Card>
                <h2 className="font-display text-lg">{t('admin.stu.selfStudy')}</h2>
                {(student.courses ?? []).length === 0 ? (
                  <p className="mt-3 text-sm text-ink-500">{t('admin.stu.notInCourse')}</p>
                ) : (
                  <ul className="mt-3 divide-y divide-ink-100">
                    {student.courses.map((course: Detail) => (
                      <li key={course.course_id} className="flex items-center gap-3 py-3">
                        <div className="min-w-0 flex-1">
                          <p className="truncate font-semibold text-ink-900">{course.title}</p>
                          <p className="text-xs text-ink-500">{t('admin.a.gradeN', { n: course.grade })}</p>
                        </div>
                        {course.last_activity_at && (
                          <span className="text-xs text-ink-500">
                            {formatDate(course.last_activity_at)}
                          </span>
                        )}
                      </li>
                    ))}
                  </ul>
                )}
              </Card>
            </div>
          )}

          {tab === 'progress' && (
            <Card className="p-0">
              {(student.mastery ?? []).length === 0 ? (
                <p className="p-8 text-center text-sm text-ink-500">{t('admin.stu.noMastery')}</p>
              ) : (
                <div className="scroll-x">
                  <table className="w-full min-w-[36rem] text-left text-sm">
                    <thead className="bg-ink-50">
                      <tr>
                        <th className="px-4 py-3 font-display">{t('admin.stu.skill')}</th>
                        <th className="px-4 py-3 font-display">{t('admin.stu.mastery')}</th>
                        <th className="px-4 py-3 font-display">{t('admin.stu.attempts')}</th>
                        <th className="px-4 py-3 font-display">{t('admin.stu.accuracy')}</th>
                        <th className="px-4 py-3 font-display">{t('admin.stu.lastPractised')}</th>
                      </tr>
                    </thead>
                    <tbody>
                      {student.mastery.map((entry: Detail) => (
                        <tr key={entry.skill_id} className="border-t border-ink-100">
                          <td className="px-4 py-3">
                            <span className="font-semibold text-ink-900">{entry.skill_name}</span>
                            {entry.is_mastered && (
                              <Badge tone="teal" className="ml-2">{t('admin.stu.mastered')}</Badge>
                            )}
                          </td>
                          <td className="w-40 px-4 py-3">
                            <ProgressBar value={Math.round(entry.mastery * 100)} />
                          </td>
                          <td className="px-4 py-3 tabular-nums">{entry.attempts}</td>
                          <td className="px-4 py-3 tabular-nums">
                            {entry.accuracy != null ? `${Math.round(entry.accuracy * 100)}%` : '—'}
                          </td>
                          <td className="px-4 py-3 text-xs text-ink-500">
                            {entry.last_practiced_at ? formatDate(entry.last_practiced_at) : '—'}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </Card>
          )}

          {tab === 'work' && (
            <div className="grid gap-4 lg:grid-cols-2">
              <Card>
                <h2 className="font-display text-lg">{t('admin.stu.homework')}</h2>
                {(student.assignments ?? []).length === 0 ? (
                  <p className="mt-3 text-sm text-ink-500">{t('admin.stu.noHomework')}</p>
                ) : (
                  <ul className="mt-3 divide-y divide-ink-100">
                    {student.assignments.map((entry: Detail) => (
                      <li key={entry.id} className="flex flex-wrap items-center gap-2 py-3">
                        <div className="min-w-0 flex-1">
                          <p className="truncate font-semibold">{entry.title}</p>
                          <p className="text-xs text-ink-500">
                            {entry.due_at ? t('admin.stu.due', { date: formatDate(entry.due_at) }) : t('admin.stu.noDueDate')}
                          </p>
                        </div>
                        {entry.score_percent != null && (
                          <Badge tone="teal">{Math.round(entry.score_percent)}%</Badge>
                        )}
                        <Badge tone="neutral">{enumLabel(entry.status)}</Badge>
                      </li>
                    ))}
                  </ul>
                )}
              </Card>

              <Card>
                <h2 className="font-display text-lg">{t('admin.stu.recentAttempts')}</h2>
                {(student.recent_attempts ?? []).length === 0 ? (
                  <p className="mt-3 text-sm text-ink-500">{t('admin.stu.noAttempts')}</p>
                ) : (
                  <ul className="mt-3 max-h-96 divide-y divide-ink-100 overflow-y-auto">
                    {student.recent_attempts.map((attempt: Detail) => (
                      <li key={attempt.id} className="flex items-center gap-3 py-2">
                        <span
                          className={`h-2 w-2 shrink-0 rounded-full ${
                            attempt.is_correct ? 'bg-teal-500' : 'bg-coral-500'
                          }`}
                        />
                        <span className="min-w-0 flex-1 truncate text-sm">
                          {attempt.skill_name}
                        </span>
                        <span className="text-xs text-ink-500">
                          {attempt.hints_used > 0 &&
                            `${t('admin.stu.hintsUsed', { count: attempt.hints_used })} · `}
                          {formatDate(attempt.created_at)}
                        </span>
                      </li>
                    ))}
                  </ul>
                )}
              </Card>
            </div>
          )}

          {tab === 'attendance' && (
            <Card className="p-0">
              {(student.attendance ?? []).length === 0 ? (
                <p className="p-8 text-center text-sm text-ink-500">{t('admin.stu.noAttendance')}</p>
              ) : (
                <ul className="divide-y divide-ink-100">
                  {student.attendance.map((entry: Detail) => (
                    <li key={entry.id} className="flex flex-wrap items-center gap-3 px-4 py-3">
                      <div className="min-w-0 flex-1">
                        <p className="truncate font-semibold">{entry.session_title}</p>
                        <p className="text-xs text-ink-500">
                          {entry.class_name} · {formatDateTime(entry.starts_at)}
                        </p>
                      </div>
                      <Badge
                        tone={
                          entry.status === 'present'
                            ? 'teal'
                            : entry.status === 'late'
                              ? 'sun'
                              : entry.status === 'excused'
                                ? 'neutral'
                                : 'coral'
                        }
                      >
                        {enumLabel(entry.status)}
                      </Badge>
                    </li>
                  ))}
                </ul>
              )}
            </Card>
          )}

          {tab === 'enquiries' && (
            <Card className="p-0">
              {(student.consultation_history ?? []).length === 0 ? (
                <p className="p-8 text-center text-sm text-ink-500">{t('admin.stu.noEnquiries')}</p>
              ) : (
                <ul className="divide-y divide-ink-100">
                  {student.consultation_history.map((entry: Detail) => (
                    <li
                      key={`${entry.source}-${entry.id}`}
                      className="flex flex-wrap items-center gap-3 px-4 py-3"
                    >
                      <Badge tone="neutral">
                        {entry.source === 'tutoring' ? t('admin.stu.tutoringRequest') : t('admin.stu.contactForm')}
                      </Badge>
                      <p className="min-w-0 flex-1 truncate text-sm">
                        {entry.message ?? enumLabel(entry.interest ?? '')}
                      </p>
                      <StatusBadge value={entry.status} kind="lead" />
                      <span className="text-xs text-ink-500">{formatDate(entry.created_at)}</span>
                    </li>
                  ))}
                </ul>
              )}
            </Card>
          )}
        </>
      )}

      <Modal
        open={editing}
        onClose={() => setEditing(false)}
        title={t('admin.stu.editStudent')}
        footer={
          <>
            <Button variant="ghost" onClick={() => setEditing(false)}>{t('admin.a.cancel')}</Button>
            <Button
              loading={saving}
              onClick={async () => {
                setSaving(true);
                const ok = await run(
                  () =>
                    adminApi.students.update(studentId, {
                      ...form,
                      phone: form.phone || null,
                      school: form.school || null,
                    }),
                  t('admin.stu.updated'),
                );
                setSaving(false);
                if (ok) {
                  setEditing(false);
                  await load();
                }
              }}
            >{t('admin.a.saveChanges')}</Button>
          </>
        }
      >
        <div className="grid gap-4 sm:grid-cols-2">
          <FormRow label={t('admin.stu.fullName')} required htmlFor="e-name" className="sm:col-span-2">
            <TextField
              id="e-name"
              value={form.full_name}
              onChange={(event) => setForm({ ...form, full_name: event.target.value })}
            />
          </FormRow>
          <FormRow label={t('admin.a.email')} required htmlFor="e-email" className="sm:col-span-2">
            <TextField
              id="e-email"
              type="email"
              value={form.email}
              onChange={(event) => setForm({ ...form, email: event.target.value })}
            />
          </FormRow>
          <FormRow label={t('admin.a.phone')} htmlFor="e-phone">
            <TextField
              id="e-phone"
              value={form.phone}
              onChange={(event) => setForm({ ...form, phone: event.target.value })}
            />
          </FormRow>
          <FormRow label={t('admin.a.grade')} htmlFor="e-grade">
            <SelectField
              id="e-grade"
              value={form.grade}
              onChange={(event) => setForm({ ...form, grade: Number(event.target.value) })}
            >
              {Array.from({ length: 12 }, (_, index) => index + 1).map((grade) => (
                <option key={grade} value={grade}>
                  Grade {grade}
                </option>
              ))}
            </SelectField>
          </FormRow>
          <FormRow label={t('admin.stu.school')} htmlFor="e-school" className="sm:col-span-2">
            <TextField
              id="e-school"
              value={form.school}
              onChange={(event) => setForm({ ...form, school: event.target.value })}
            />
          </FormRow>
          <FormRow label={t('admin.stu.learningGoals')} className="sm:col-span-2">
            <StringListField
              values={form.learning_goals}
              onChange={(learning_goals) => setForm({ ...form, learning_goals })}
            />
          </FormRow>
        </div>
      </Modal>
    </AdminShell>
  );
}

function StatCard({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <Card>
      <p className="text-xs font-semibold text-ink-500">{label}</p>
      <p className="font-display text-2xl tabular-nums">{value}</p>
      {sub && <p className="text-xs text-ink-500">{sub}</p>}
    </Card>
  );
}

function Field({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="min-w-0">
      <dt className="text-xs font-bold text-ink-500">{label}</dt>
      <dd className="mt-0.5 break-words text-sm text-ink-800">{value}</dd>
    </div>
  );
}
