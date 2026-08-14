'use client';

import Link from 'next/link';
import { CalendarPlus, Plus, Trash2, Users } from 'lucide-react';
import { use, useCallback, useEffect, useState } from 'react';

import { Badge, Button, Card } from '@hietedu/ui';

import { AdminShell } from '@/components/admin/admin-shell';
import { ConfirmDialog, Modal } from '@/components/admin/dialog';
import {
  CheckboxField,
  FormRow,
  SelectField,
  StatusBadge,
  TextAreaField,
  TextField,
  TranslationPanel,
  translationsPayload,
  useEnumLabel,
} from '@/components/admin/form';
import { useToast } from '@/components/admin/toast';
import { useContentLabel } from '@/lib/content-label';
import { adminApi, type AdminStudent, type AdminTeacher } from '@/lib/admin-api';
import { useRequireAuth } from '@/lib/auth';
import { useI18n } from '@/lib/i18n';

type Detail = Record<string, any>;
/** Weekday indexes; the names come from the dictionary so they follow the interface language. */
const WEEKDAYS = [0, 1, 2, 3, 4, 5, 6];

export default function ClassDetailPage({
  params,
}: {
  params: Promise<{ locale: string; id: string }>;
}) {
  const { id } = use(params);
  const classId = Number(id);
  const { t, locale, formatDate, formatDateTime } = useI18n();
  const enumLabel = useEnumLabel();
  const label = useContentLabel();
  const { user, loading: authLoading } = useRequireAuth(locale, ['admin']);
  const { run, notify } = useToast();

  const [group, setGroup] = useState<Detail | null>(null);
  const [loading, setLoading] = useState(true);
  const [teachers, setTeachers] = useState<AdminTeacher[]>([]);
  const [students, setStudents] = useState<AdminStudent[]>([]);
  const [addingStudent, setAddingStudent] = useState(false);
  const [newStudentId, setNewStudentId] = useState(0);
  const [generating, setGenerating] = useState(false);
  const [range, setRange] = useState({ from_date: '', to_date: '' });
  const [addingSession, setAddingSession] = useState(false);
  const [sessionVi, setSessionVi] = useState<Record<string, string>>({});
  const [sessionForm, setSessionForm] = useState({
    title: '',
    starts_at: '',
    ends_at: '',
    join_url: '',
    topic_summary: '',
  });
  const [deletingSession, setDeletingSession] = useState<Detail | null>(null);
  const [editingSchedule, setEditingSchedule] = useState(false);
  const [schedule, setSchedule] = useState<
    { weekday: number; start_time: string; end_time: string }[]
  >([]);

  const href = (path: string) => `/${locale}${path}`;

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const result = (await adminApi.classes.get(classId)) as Detail;
      setGroup(result);
      setSchedule(
        (result.schedule ?? []).map((slot: Detail) => ({
          weekday: slot.weekday,
          start_time: slot.start_time,
          end_time: slot.end_time,
        })),
      );
    } catch (caught) {
      notify((caught as Error).message, 'error');
    } finally {
      setLoading(false);
    }
  }, [classId, notify]);

  useEffect(() => {
    if (user) void load();
  }, [user, load]);

  useEffect(() => {
    if (!user) return;
    adminApi.teachers.list({ page_size: 100 }).then((p) => setTeachers(p.items)).catch(() => undefined);
    adminApi.students.list({ page_size: 200 }).then((p) => setStudents(p.items)).catch(() => undefined);
  }, [user]);

  async function patch(body: Record<string, unknown>, message: string) {
    const ok = await run(() => adminApi.classes.update(classId, body), message);
    if (ok) await load();
  }

  if (authLoading || !user) return <AdminShell loading />;

  const enrolledIds = new Set((group?.roster ?? []).map((row: Detail) => row.student_id));

  return (
    <AdminShell
      title={group ? label(group, 'name') : t('admin.a.class')}
      description={
        group
          ? t('admin.cls.metaLine', { format: enumLabel(group.format), mode: enumLabel(group.delivery_mode), taken: group.seats_taken, capacity: group.capacity })
          : undefined
      }
      breadcrumbs={[
        { label: t('admin.a.adminCrumb'), href: '/admin' },
        { label: t('admin.cls.classes'), href: '/admin/classes' },
        { label: group?.name ?? '…' },
      ]}
      actions={
        group && (
          <>
            <Button variant="outline" onClick={() => setAddingSession(true)}>
              <Plus className="h-4 w-4" aria-hidden="true" />{t('admin.cls.addSession')}</Button>
            <Button variant="outline" onClick={() => setGenerating(true)}>
              <CalendarPlus className="h-4 w-4" aria-hidden="true" />{t('admin.cls.generateSessions')}</Button>
            <Button onClick={() => setAddingStudent(true)}>
              <Users className="h-4 w-4" aria-hidden="true" />{t('admin.cls.addStudent')}</Button>
          </>
        )
      }
    >
      {loading || !group ? (
        <p className="py-16 text-center text-sm text-ink-500">{t('admin.a.loading')}</p>
      ) : (
        <div className="grid gap-6 lg:grid-cols-[1fr_20rem]">
          <div className="min-w-0 space-y-6">
            <Card className="p-0">
              <div className="flex items-center justify-between border-b-2 border-ink-100 p-4">
                <h2 className="font-display text-lg">
                  {t('admin.cls.rosterCount', { count: group.roster?.length ?? 0 })}
                </h2>
                <Badge tone={group.seats_available === 0 ? 'coral' : 'neutral'}>
                  {t('admin.cls.placesLeft', { count: group.seats_available })}
                </Badge>
              </div>
              {(group.roster ?? []).length === 0 ? (
                <p className="p-6 text-center text-sm text-ink-500">{t('admin.cls.nobodyEnrolled')}</p>
              ) : (
                <ul className="divide-y divide-ink-100">
                  {group.roster.map((row: Detail) => (
                    <li key={row.enrollment_id} className="flex flex-wrap items-center gap-3 px-4 py-3">
                      <div className="min-w-0 flex-1">
                        <Link
                          href={href(`/admin/students/${row.student_id}`)}
                          className="block truncate font-semibold text-ink-900 hover:text-brand-700 hover:underline"
                        >
                          {row.name}
                        </Link>
                        <p className="truncate text-xs text-ink-500">
                          {row.email} · Grade {row.grade}
                        </p>
                      </div>
                      <StatusBadge value={row.status} kind="enrollment" />
                      <StatusBadge value={row.payment_status} kind="payment" />
                      {row.status === 'pending' && (
                        <Button
                          size="sm"
                          onClick={async () => {
                            const ok = await run(
                              () => adminApi.enrollments.approve(row.enrollment_id),
                              'Approved',
                            );
                            if (ok) await load();
                          }}
                        >{t('admin.a.approve')}</Button>
                      )}
                    </li>
                  ))}
                </ul>
              )}
            </Card>

            <Card className="p-0">
              <div className="flex items-center justify-between border-b-2 border-ink-100 p-4">
                <h2 className="font-display text-lg">
                  {t('admin.cls.sessionsCount', { count: group.sessions?.length ?? 0 })}
                </h2>
              </div>
              {(group.sessions ?? []).length === 0 ? (
                <p className="p-6 text-center text-sm text-ink-500">{t('admin.cls.noSessionsYet')}</p>
              ) : (
                <ul className="max-h-[30rem] divide-y divide-ink-100 overflow-y-auto">
                  {group.sessions.map((session: Detail) => (
                    <li key={session.id} className="flex flex-wrap items-center gap-3 px-4 py-3">
                      <div className="min-w-0 flex-1">
                        <p className="truncate font-semibold text-ink-900">{label(session, 'title')}</p>
                        <p className="truncate text-xs text-ink-500">
                          {formatDateTime(session.starts_at)}
                          {session.topic_summary ? ` · ${label(session, 'topic_summary')}` : ''}
                        </p>
                      </div>
                      {session.join_url && (
                        <a
                          href={session.join_url}
                          target="_blank"
                          rel="noreferrer"
                          className="text-xs font-bold text-brand-600 hover:underline"
                        >
                          Join
                        </a>
                      )}
                      <Badge tone="neutral">{enumLabel(session.status)}</Badge>
                      <button
                        type="button"
                        aria-label={t('admin.a.deleteAria', { name: label(session, 'title') })}
                        onClick={() => setDeletingSession(session)}
                        className="rounded-lg p-1.5 text-coral-500 hover:bg-coral-50"
                      >
                        <Trash2 className="h-4 w-4" aria-hidden="true" />
                      </button>
                    </li>
                  ))}
                </ul>
              )}
            </Card>
          </div>

          <aside className="space-y-4">
            <Card>
              <h2 className="font-display text-lg">{t('admin.cls.settings')}</h2>
              <div className="mt-4 space-y-4">
                <FormRow label={t('admin.a.teacher')} htmlFor="cd-teacher">
                  <SelectField
                    id="cd-teacher"
                    value={group.teacher_id ?? 0}
                    onChange={(e) =>
                      patch(
                        { teacher_id: Number(e.target.value) || null },
                        t('admin.cls.teacherAssigned'),
                      )
                    }
                  >
                    <option value={0}>{t('admin.cls.unassigned')}</option>
                    {teachers.map((teacher) => (
                      <option key={teacher.id} value={teacher.id}>
                        {teacher.full_name}
                      </option>
                    ))}
                  </SelectField>
                </FormRow>
                <FormRow label={t('admin.cls.capacity')} htmlFor="cd-cap">
                  <TextField
                    id="cd-cap"
                    type="number"
                    min={1}
                    defaultValue={group.capacity}
                    onBlur={(e) => {
                      const value = Number(e.target.value);
                      if (value !== group.capacity) patch({ capacity: value }, t('admin.cls.capacityUpdated'));
                    }}
                  />
                </FormRow>
                <FormRow label={t('admin.cls.locationLabel')} htmlFor="cd-loc">
                  <TextField
                    id="cd-loc"
                    defaultValue={group.location ?? ''}
                    onBlur={(e) => {
                      if (e.target.value !== (group.location ?? '')) {
                        patch({ location: e.target.value || null }, t('admin.cls.locationUpdated'));
                      }
                    }}
                  />
                </FormRow>
                <CheckboxField
                  label={t('admin.cls.openForEnrolment')}
                  checked={group.is_open_for_enrollment}
                  onChange={(value) =>
                    patch(
                      { is_open_for_enrollment: value },
                      value ? t('admin.cls.enrolmentOpened') : t('admin.cls.enrolmentClosed'),
                    )
                  }
                />
              </div>
            </Card>

            <Card>
              <div className="flex items-center justify-between">
                <h2 className="font-display text-lg">{t('admin.cls.weeklySchedule')}</h2>
                <Button size="sm" variant="ghost" onClick={() => setEditingSchedule(true)}>{t('admin.a.edit')}</Button>
              </div>
              {(group.schedule ?? []).length === 0 ? (
                <p className="mt-3 text-sm text-ink-500">{t('admin.cls.noRecurring')}</p>
              ) : (
                <ul className="mt-3 space-y-1.5">
                  {group.schedule.map((slot: Detail, index: number) => (
                    <li key={index} className="text-sm">
                      <span className="font-semibold">{t(`common.weekday.${slot.weekday % 7}`)}</span>{' '}
                      {slot.start_time}–{slot.end_time}
                    </li>
                  ))}
                </ul>
              )}
              <dl className="mt-4 space-y-2 text-sm">
                <div>
                  <dt className="text-xs font-bold text-ink-500">{t('admin.cls.runs')}</dt>
                  <dd>
                    {group.start_date ? formatDate(group.start_date) : '—'}
                    {group.end_date ? ` → ${formatDate(group.end_date)}` : ''}
                  </dd>
                </div>
                <div>
                  <dt className="text-xs font-bold text-ink-500">{t('admin.a.course')}</dt>
                  <dd>{group.course_title ?? '—'}</dd>
                </div>
              </dl>
            </Card>
          </aside>
        </div>
      )}

      {/* add student */}
      <Modal
        open={addingStudent}
        onClose={() => setAddingStudent(false)}
        title={t('admin.cls.addStudentTitle')}
        footer={
          <>
            <Button variant="ghost" onClick={() => setAddingStudent(false)}>{t('admin.a.cancel')}</Button>
            <Button
              onClick={async () => {
                if (!newStudentId) {
                  notify(t('admin.cls.chooseStudent'), 'error');
                  return;
                }
                const ok = await run(
                  () =>
                    adminApi.enrollments.create({
                      student_id: newStudentId,
                      class_group_id: classId,
                      status: 'confirmed',
                    }),
                  'Student enrolled',
                );
                if (ok) {
                  setAddingStudent(false);
                  setNewStudentId(0);
                  await load();
                }
              }}
            >{t('admin.cls.enrol')}</Button>
          </>
        }
      >
        <FormRow label={t('admin.a.student')} required htmlFor="add-student">
          <SelectField
            id="add-student"
            value={newStudentId}
            onChange={(e) => setNewStudentId(Number(e.target.value))}
          >
            <option value={0}>{t('admin.cls.chooseStudentPlaceholder')}</option>
            {students
              .filter((student) => !enrolledIds.has(student.id))
              .map((student) => (
                <option key={student.id} value={student.id}>
                  {student.full_name} (Grade {student.grade})
                </option>
              ))}
          </SelectField>
        </FormRow>
      </Modal>

      {/* generate sessions */}
      <Modal
        open={generating}
        onClose={() => setGenerating(false)}
        title={t('admin.cls.generateSessions')}
        description={t('admin.cls.generateHint')}
        footer={
          <>
            <Button variant="ghost" onClick={() => setGenerating(false)}>{t('admin.a.cancel')}</Button>
            <Button
              onClick={async () => {
                if (!range.from_date || !range.to_date) {
                  notify(t('admin.cls.chooseBothDates'), 'error');
                  return;
                }
                const result = await run(
                  () => adminApi.classes.generateSessions(classId, range),
                  t('admin.cls.sessionsGenerated'),
                );
                if (result) {
                  setGenerating(false);
                  notify(t('admin.cls.sessionsCreated', { count: result.created }), 'success');
                  await load();
                }
              }}
            >{t('admin.cls.generate')}</Button>
          </>
        }
      >
        <div className="grid gap-4 sm:grid-cols-2">
          <FormRow label={t('admin.cls.from')} required htmlFor="gen-from">
            <TextField
              id="gen-from"
              type="date"
              value={range.from_date}
              onChange={(e) => setRange({ ...range, from_date: e.target.value })}
            />
          </FormRow>
          <FormRow label={t('admin.cls.to')} required htmlFor="gen-to">
            <TextField
              id="gen-to"
              type="date"
              value={range.to_date}
              onChange={(e) => setRange({ ...range, to_date: e.target.value })}
            />
          </FormRow>
        </div>
        {(group?.schedule ?? []).length === 0 && (
          <p className="mt-3 text-sm font-semibold text-coral-700">{t('admin.cls.noScheduleWarning')}</p>
        )}
      </Modal>

      {/* single session */}
      <Modal
        open={addingSession}
        onClose={() => setAddingSession(false)}
        title={t('admin.cls.addSessionTitle')}
        footer={
          <>
            <Button variant="ghost" onClick={() => setAddingSession(false)}>{t('admin.a.cancel')}</Button>
            <Button
              onClick={async () => {
                if (!sessionForm.title || !sessionForm.starts_at || !sessionForm.ends_at) {
                  notify(t('admin.cls.sessionRequired'), 'error');
                  return;
                }
                const ok = await run(
                  () =>
                    adminApi.sessions.create({
                      class_group_id: classId,
                      title: sessionForm.title,
                      starts_at: new Date(sessionForm.starts_at).toISOString(),
                      ends_at: new Date(sessionForm.ends_at).toISOString(),
                      join_url: sessionForm.join_url || null,
                      topic_summary: sessionForm.topic_summary || null,
                      // A student reads the title and the summary on their schedule, so both
                      // are authored in both languages at the point they are written.
                      translations: translationsPayload(sessionVi),
                    }),
                  t('admin.cls.sessionScheduled'),
                );
                if (ok) {
                  setAddingSession(false);
                  setSessionForm({
                    title: '',
                    starts_at: '',
                    ends_at: '',
                    join_url: '',
                    topic_summary: '',
                  });
                  setSessionVi({});
                  await load();
                }
              }}
            >{t('admin.cls.schedule')}</Button>
          </>
        }
      >
        <div className="grid gap-4 sm:grid-cols-2">
          <FormRow label={t('admin.cls.sessionTitle')} required htmlFor="se-title" className="sm:col-span-2">
            <TextField
              id="se-title"
              value={sessionForm.title}
              onChange={(e) => setSessionForm({ ...sessionForm, title: e.target.value })}
            />
          </FormRow>
          <FormRow label={t('admin.cls.starts')} required htmlFor="se-start">
            <TextField
              id="se-start"
              type="datetime-local"
              value={sessionForm.starts_at}
              onChange={(e) => setSessionForm({ ...sessionForm, starts_at: e.target.value })}
            />
          </FormRow>
          <FormRow label={t('admin.web.endsLabel')} required htmlFor="se-end">
            <TextField
              id="se-end"
              type="datetime-local"
              value={sessionForm.ends_at}
              onChange={(e) => setSessionForm({ ...sessionForm, ends_at: e.target.value })}
            />
          </FormRow>
          <FormRow label={t('admin.cls.meetingLink')} htmlFor="se-url" className="sm:col-span-2">
            <TextField
              id="se-url"
              value={sessionForm.join_url}
              onChange={(e) => setSessionForm({ ...sessionForm, join_url: e.target.value })}
              placeholder="https://meet.google.com/…"
            />
          </FormRow>
          <FormRow label={t('admin.cls.whatCovered')} htmlFor="se-topic" className="sm:col-span-2">
            <TextAreaField
              id="se-topic"
              value={sessionForm.topic_summary}
              onChange={(e) => setSessionForm({ ...sessionForm, topic_summary: e.target.value })}
            />
          </FormRow>
          <div className="sm:col-span-2">
            <TranslationPanel
              fields={[
                { name: 'title', label: t('admin.a.title') },
                { name: 'topic_summary', label: t('admin.cls.whatCovered'), multiline: true },
              ]}
              value={sessionVi}
              onChange={setSessionVi}
            />
          </div>
        </div>
      </Modal>

      {/* schedule editor */}
      <Modal
        open={editingSchedule}
        onClose={() => setEditingSchedule(false)}
        title={t('admin.cls.weeklySchedule')}
        footer={
          <>
            <Button variant="ghost" onClick={() => setEditingSchedule(false)}>{t('admin.a.cancel')}</Button>
            <Button
              onClick={async () => {
                const ok = await run(
                  () => adminApi.classes.update(classId, { schedule }),
                  t('admin.cls.scheduleSaved'),
                );
                if (ok) {
                  setEditingSchedule(false);
                  await load();
                }
              }}
            >{t('admin.cls.saveSchedule')}</Button>
          </>
        }
      >
        <ul className="space-y-2">
          {schedule.map((slot, index) => (
            <li key={index} className="flex flex-wrap items-center gap-2">
              <SelectField
                aria-label={t('admin.cls.day')}
                className="w-40"
                value={slot.weekday}
                onChange={(e) => {
                  const next = [...schedule];
                  next[index] = { ...slot, weekday: Number(e.target.value) };
                  setSchedule(next);
                }}
              >
                {WEEKDAYS.map((dayIndex) => (
                  <option key={dayIndex} value={dayIndex}>
                    {t(`common.weekday.${dayIndex}`)}
                  </option>
                ))}
              </SelectField>
              <TextField
                aria-label={t('admin.cls.startTime')}
                type="time"
                className="w-32"
                value={slot.start_time}
                onChange={(e) => {
                  const next = [...schedule];
                  next[index] = { ...slot, start_time: e.target.value };
                  setSchedule(next);
                }}
              />
              <TextField
                aria-label={t('admin.cls.endTime')}
                type="time"
                className="w-32"
                value={slot.end_time}
                onChange={(e) => {
                  const next = [...schedule];
                  next[index] = { ...slot, end_time: e.target.value };
                  setSchedule(next);
                }}
              />
              <button
                type="button"
                aria-label={t('admin.cls.removeSlot')}
                onClick={() => setSchedule(schedule.filter((_, i) => i !== index))}
                className="rounded-lg p-2 text-coral-500 hover:bg-coral-50"
              >
                <Trash2 className="h-4 w-4" aria-hidden="true" />
              </button>
            </li>
          ))}
        </ul>
        <Button
          size="sm"
          variant="outline"
          className="mt-3"
          onClick={() =>
            setSchedule([...schedule, { weekday: 1, start_time: '18:00', end_time: '19:30' }])
          }
        >
          <Plus className="h-4 w-4" aria-hidden="true" />{t('admin.cls.addSlotShort')}</Button>
      </Modal>

      <ConfirmDialog
        open={deletingSession !== null}
        onClose={() => setDeletingSession(null)}
        title={t('admin.cls.deleteSessionQ')}
        message={t('admin.cls.deleteSessionBody')}
        onConfirm={async () => {
          if (!deletingSession) return;
          const ok = await run(
            () => adminApi.sessions.remove(deletingSession.id),
            t('admin.cls.sessionDeleted'),
          );
          if (ok !== undefined) await load();
        }}
      />
    </AdminShell>
  );
}
