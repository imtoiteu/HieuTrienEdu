'use client';

import Link from 'next/link';
import { CalendarDays, List, Plus, Trash2 } from 'lucide-react';
import { useCallback, useEffect, useState } from 'react';

import { Badge, Button, Card } from '@hietedu/ui';

import { AdminShell } from '@/components/admin/admin-shell';
import { DataTable, type Column } from '@/components/admin/data-table';
import { ConfirmDialog, Modal } from '@/components/admin/dialog';
import {
  CheckboxField,
  FormRow,
  SelectField,
  TextField,
  humanise,
} from '@/components/admin/form';
import { useToast } from '@/components/admin/toast';
import {
  adminApi,
  type AdminClass,
  type AdminCourse,
  type AdminSession,
  type AdminTeacher,
} from '@/lib/admin-api';
import { useRequireAuth } from '@/lib/auth';
import { useI18n } from '@/lib/i18n';

const WEEKDAYS = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'];
const FORMATS = ['one_to_one', 'group', 'online_live', 'recorded', 'hybrid'];
const MODES = ['online', 'offline', 'hybrid'];

interface Slot {
  weekday: number;
  start_time: string;
  end_time: string;
}

export default function ClassesPage() {
  const { t, locale, formatDate, formatDateTime } = useI18n();
  const { user, loading: authLoading } = useRequireAuth(locale, ['admin']);
  const { run, notify } = useToast();

  const [view, setView] = useState<'classes' | 'schedule'>('classes');
  const [rows, setRows] = useState<AdminClass[]>([]);
  const [sessions, setSessions] = useState<AdminSession[]>([]);
  const [meta, setMeta] = useState({ total: 0, page: 1, page_size: 25, pages: 0 });
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState('');
  const [filters, setFilters] = useState<Record<string, string>>({});
  const [teachers, setTeachers] = useState<AdminTeacher[]>([]);
  const [courses, setCourses] = useState<AdminCourse[]>([]);
  const [creating, setCreating] = useState(false);
  const [saving, setSaving] = useState(false);
  const [deleting, setDeleting] = useState<AdminClass | null>(null);
  const [form, setForm] = useState({
    name: '',
    course_id: 0,
    teacher_id: 0,
    format: 'group',
    delivery_mode: 'online',
    capacity: 12,
    start_date: '',
    end_date: '',
    location: '',
    is_open_for_enrollment: true,
    schedule: [] as Slot[],
  });

  const href = (path: string) => `/${locale}${path}`;

  const load = useCallback(async () => {
    setLoading(true);
    try {
      if (view === 'classes') {
        const result = await adminApi.classes.list({ page, search, ...filters });
        setRows(result.items);
        setMeta({
          total: result.total,
          page: result.page,
          page_size: result.page_size,
          pages: result.pages,
        });
      } else {
        const result = await adminApi.sessions.list({ page, upcoming: true, page_size: 50 });
        setSessions(result.items);
        setMeta({
          total: result.total,
          page: result.page,
          page_size: result.page_size,
          pages: result.pages,
        });
      }
    } catch (caught) {
      notify((caught as Error).message, 'error');
    } finally {
      setLoading(false);
    }
  }, [view, page, search, filters, notify]);

  useEffect(() => {
    if (user) void load();
  }, [user, load]);

  useEffect(() => {
    if (!user) return;
    adminApi.teachers.list({ page_size: 100 }).then((p) => setTeachers(p.items)).catch(() => undefined);
    adminApi.courses.list({ page_size: 100 }).then((p) => setCourses(p.items)).catch(() => undefined);
  }, [user]);

  const columns: Column<AdminClass>[] = [
    {
      key: 'name',
      header: 'Class',
      sortKey: 'name',
      render: (row) => (
        <div className="min-w-0">
          <Link
            href={href(`/admin/classes/${row.id}`)}
            className="block truncate font-bold text-ink-900 hover:text-brand-700 hover:underline"
          >
            {row.name}
          </Link>
          <p className="truncate text-xs text-ink-500">
            {humanise(row.format)} · {humanise(row.delivery_mode)}
            {row.location ? ` · ${row.location}` : ''}
          </p>
        </div>
      ),
    },
    {
      key: 'teacher',
      header: 'Teacher',
      render: (row) =>
        row.teacher_name ? (
          <span className="text-sm">{row.teacher_name}</span>
        ) : (
          <span className="text-xs font-semibold text-coral-600">{t('admin.cls.unassigned')}</span>
        ),
    },
    {
      key: 'seats',
      header: 'Places',
      render: (row) => (
        <Badge tone={row.seats_available === 0 ? 'coral' : 'neutral'}>
          {row.seats_taken}/{row.capacity}
        </Badge>
      ),
    },
    {
      key: 'schedule',
      header: 'Schedule',
      hideOnMobile: true,
      render: (row) =>
        row.schedule.length === 0 ? (
          <span className="text-xs text-ink-400">{t('admin.cls.notSet')}</span>
        ) : (
          <div className="flex flex-wrap gap-1">
            {row.schedule.map((slot, index) => (
              <Badge key={index} tone="brand">
                {slot.weekday_label.slice(0, 3)} {slot.start_time}
              </Badge>
            ))}
          </div>
        ),
    },
    {
      key: 'dates',
      header: 'Runs',
      hideOnMobile: true,
      render: (row) => (
        <span className="text-xs text-ink-600">
          {row.start_date ? formatDate(row.start_date) : '—'}
          {row.end_date ? ` → ${formatDate(row.end_date)}` : ''}
        </span>
      ),
    },
    {
      key: 'open',
      header: 'Enrolment',
      render: (row) =>
        row.is_open_for_enrollment ? (
          <Badge tone="teal">{t('admin.cls.open')}</Badge>
        ) : (
          <Badge tone="neutral">{t('admin.cls.closed')}</Badge>
        ),
    },
    {
      key: 'actions',
      header: '',
      className: 'text-right',
      render: (row) => (
        <button
          type="button"
          aria-label={`Delete ${row.name}`}
          onClick={() => setDeleting(row)}
          className="rounded-lg p-2 text-coral-600 hover:bg-coral-50"
        >
          <Trash2 className="h-4 w-4" aria-hidden="true" />
        </button>
      ),
    },
  ];

  if (authLoading || !user) return <AdminShell loading />;

  return (
    <AdminShell
      title={t('admin.cls.title')}
      description={t('admin.cls.subtitle')}
      breadcrumbs={[{ label: t('admin.a.adminCrumb'), href: '/admin' }, { label: t('admin.cls.classes') }]}
      actions={
        <Button onClick={() => setCreating(true)}>
          <Plus className="h-4 w-4" aria-hidden="true" />{t('admin.cls.new')}</Button>
      }
    >
      <div className="mb-4 flex gap-2">
        <Button
          size="sm"
          variant={view === 'classes' ? 'primary' : 'outline'}
          onClick={() => {
            setView('classes');
            setPage(1);
          }}
        >
          <List className="h-4 w-4" aria-hidden="true" />{t('admin.cls.classes')}</Button>
        <Button
          size="sm"
          variant={view === 'schedule' ? 'primary' : 'outline'}
          onClick={() => {
            setView('schedule');
            setPage(1);
          }}
        >
          <CalendarDays className="h-4 w-4" aria-hidden="true" />{t('admin.cls.upcomingSessions')}</Button>
      </div>

      {view === 'classes' ? (
        <DataTable
          columns={columns}
          rows={rows}
          total={meta.total}
          page={meta.page}
          pageSize={meta.page_size}
          pages={meta.pages}
          loading={loading}
          search={search}
          onSearchChange={(value) => {
            setSearch(value);
            setPage(1);
          }}
          onPageChange={setPage}
          filters={[
            {
              key: 'format',
              label: t('admin.a.format'),
              options: FORMATS.map((f) => ({ value: f, label: humanise(f) })),
            },
            {
              key: 'delivery_mode',
              label: t('admin.a.delivery'),
              options: MODES.map((m) => ({ value: m, label: humanise(m) })),
            },
            {
              key: 'teacher_id',
              label: t('admin.a.teacher'),
              options: teachers.map((t) => ({
                value: String(t.id),
                label: t.full_name ?? String(t.id),
              })),
            },
            {
              key: 'open_only',
              label: t('admin.cls.enrolment'),
              options: [
                { value: 'true', label: t('admin.cls.open') },
                { value: 'false', label: t('admin.cls.closed') },
              ],
            },
          ]}
          filterValues={filters}
          onFilterChange={(key, value) => {
            setFilters((current) => ({ ...current, [key]: value }));
            setPage(1);
          }}
          emptyTitle={t('admin.cls.empty')}
          emptyBody={t('admin.cls.emptyBody')}
          emptyAction={
            <Button onClick={() => setCreating(true)}>
              <Plus className="h-4 w-4" aria-hidden="true" />{t('admin.cls.createOne')}</Button>
          }
        />
      ) : (
        <Card className="p-0">
          {loading ? (
            <p className="p-8 text-center text-sm text-ink-500">{t('admin.a.loading')}</p>
          ) : sessions.length === 0 ? (
            <p className="p-8 text-center text-sm text-ink-500">
              No upcoming sessions. Open a class and generate its sessions from the weekly
              schedule.
            </p>
          ) : (
            <ul className="divide-y divide-ink-100">
              {sessions.map((session) => (
                <li key={session.id} className="flex flex-wrap items-center gap-3 px-4 py-3">
                  <div className="min-w-0 flex-1">
                    <p className="truncate font-bold text-ink-900">{session.title}</p>
                    <p className="truncate text-xs text-ink-500">
                      {session.class_name}
                      {session.teacher_name ? ` · ${session.teacher_name}` : ''}
                      {session.location ? ` · ${session.location}` : ''}
                    </p>
                  </div>
                  {session.join_url && (
                    <a
                      href={session.join_url}
                      target="_blank"
                      rel="noreferrer"
                      className="text-xs font-bold text-brand-600 hover:underline"
                    >{t('admin.cls.joinLink')}</a>
                  )}
                  <Badge tone="neutral">{humanise(session.status)}</Badge>
                  <span className="text-xs font-semibold text-ink-700">
                    {formatDateTime(session.starts_at)}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </Card>
      )}

      <Modal
        open={creating}
        onClose={() => setCreating(false)}
        title={t('admin.cls.new')}
        size="lg"
        footer={
          <>
            <Button variant="ghost" onClick={() => setCreating(false)}>{t('admin.a.cancel')}</Button>
            <Button
              loading={saving}
              onClick={async () => {
                if (!form.name.trim()) {
                  notify('A class name is required', 'error');
                  return;
                }
                setSaving(true);
                const ok = await run(
                  () =>
                    adminApi.classes.create({
                      ...form,
                      course_id: form.course_id || null,
                      teacher_id: form.teacher_id || null,
                      start_date: form.start_date || null,
                      end_date: form.end_date || null,
                      location: form.location || null,
                    }),
                  t('admin.cls.created'),
                );
                setSaving(false);
                if (ok) {
                  setCreating(false);
                  await load();
                }
              }}
            >{t('admin.cls.createClass')}</Button>
          </>
        }
      >
        <div className="grid gap-4 sm:grid-cols-2">
          <FormRow label={t('admin.cls.className')} required htmlFor="cl-name" className="sm:col-span-2">
            <TextField
              id="cl-name"
              value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
              placeholder={t('admin.cls.namePlaceholder')}
            />
          </FormRow>
          <FormRow label={t('admin.a.course')} htmlFor="cl-course">
            <SelectField
              id="cl-course"
              value={form.course_id}
              onChange={(e) => setForm({ ...form, course_id: Number(e.target.value) })}
            >
              <option value={0}>{t('admin.a.none')}</option>
              {courses.map((course) => (
                <option key={course.id} value={course.id}>
                  {course.title}
                </option>
              ))}
            </SelectField>
          </FormRow>
          <FormRow label={t('admin.a.teacher')} htmlFor="cl-teacher">
            <SelectField
              id="cl-teacher"
              value={form.teacher_id}
              onChange={(e) => setForm({ ...form, teacher_id: Number(e.target.value) })}
            >
              <option value={0}>{t('admin.cls.unassigned')}</option>
              {teachers.map((teacher) => (
                <option key={teacher.id} value={teacher.id}>
                  {teacher.full_name}
                </option>
              ))}
            </SelectField>
          </FormRow>
          <FormRow label={t('admin.a.format')} htmlFor="cl-format">
            <SelectField
              id="cl-format"
              value={form.format}
              onChange={(e) => setForm({ ...form, format: e.target.value })}
            >
              {FORMATS.map((f) => (
                <option key={f} value={f}>
                  {humanise(f)}
                </option>
              ))}
            </SelectField>
          </FormRow>
          <FormRow label={t('admin.a.delivery')} htmlFor="cl-mode">
            <SelectField
              id="cl-mode"
              value={form.delivery_mode}
              onChange={(e) => setForm({ ...form, delivery_mode: e.target.value })}
            >
              {MODES.map((m) => (
                <option key={m} value={m}>
                  {humanise(m)}
                </option>
              ))}
            </SelectField>
          </FormRow>
          <FormRow label={t('admin.cls.capacity')} htmlFor="cl-cap">
            <TextField
              id="cl-cap"
              type="number"
              min={1}
              value={form.capacity}
              onChange={(e) => setForm({ ...form, capacity: Number(e.target.value) })}
            />
          </FormRow>
          <FormRow label={t('admin.cls.location')} htmlFor="cl-loc">
            <TextField
              id="cl-loc"
              value={form.location}
              onChange={(e) => setForm({ ...form, location: e.target.value })}
            />
          </FormRow>
          <FormRow label={t('admin.cls.startDate')} htmlFor="cl-start">
            <TextField
              id="cl-start"
              type="date"
              value={form.start_date}
              onChange={(e) => setForm({ ...form, start_date: e.target.value })}
            />
          </FormRow>
          <FormRow label={t('admin.cls.endDate')} htmlFor="cl-end">
            <TextField
              id="cl-end"
              type="date"
              value={form.end_date}
              onChange={(e) => setForm({ ...form, end_date: e.target.value })}
            />
          </FormRow>

          <div className="sm:col-span-2">
            <p className="text-xs font-bold text-ink-700">{t('admin.cls.weeklySchedule')}</p>
            <ul className="mt-2 space-y-2">
              {form.schedule.map((slot, index) => (
                <li key={index} className="flex flex-wrap items-center gap-2">
                  <SelectField
                    aria-label={t('admin.cls.day')}
                    className="w-40"
                    value={slot.weekday}
                    onChange={(e) => {
                      const next = [...form.schedule];
                      next[index] = { ...slot, weekday: Number(e.target.value) };
                      setForm({ ...form, schedule: next });
                    }}
                  >
                    {WEEKDAYS.map((day, dayIndex) => (
                      <option key={day} value={dayIndex}>
                        {day}
                      </option>
                    ))}
                  </SelectField>
                  <TextField
                    aria-label={t('admin.cls.startTime')}
                    type="time"
                    className="w-32"
                    value={slot.start_time}
                    onChange={(e) => {
                      const next = [...form.schedule];
                      next[index] = { ...slot, start_time: e.target.value };
                      setForm({ ...form, schedule: next });
                    }}
                  />
                  <TextField
                    aria-label={t('admin.cls.endTime')}
                    type="time"
                    className="w-32"
                    value={slot.end_time}
                    onChange={(e) => {
                      const next = [...form.schedule];
                      next[index] = { ...slot, end_time: e.target.value };
                      setForm({ ...form, schedule: next });
                    }}
                  />
                  <button
                    type="button"
                    aria-label={t('admin.cls.removeSlot')}
                    onClick={() =>
                      setForm({
                        ...form,
                        schedule: form.schedule.filter((_, i) => i !== index),
                      })
                    }
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
              className="mt-2"
              onClick={() =>
                setForm({
                  ...form,
                  schedule: [
                    ...form.schedule,
                    { weekday: 1, start_time: '18:00', end_time: '19:30' },
                  ],
                })
              }
            >
              <Plus className="h-4 w-4" aria-hidden="true" />{t('admin.cls.addSlot')}</Button>
          </div>

          <div className="sm:col-span-2">
            <CheckboxField
              label={t('admin.cls.openForEnrolment')}
              checked={form.is_open_for_enrollment}
              onChange={(value) => setForm({ ...form, is_open_for_enrollment: value })}
            />
          </div>
        </div>
      </Modal>

      <ConfirmDialog
        open={deleting !== null}
        onClose={() => setDeleting(null)}
        title={`Delete “${deleting?.name}”?`}
        message="Classes with enrolled students cannot be deleted — move or cancel them first."
        onConfirm={async () => {
          if (!deleting) return;
          const ok = await run(() => adminApi.classes.remove(deleting.id), t('admin.cls.deletedToast'));
          if (ok !== undefined) await load();
        }}
      />
    </AdminShell>
  );
}
