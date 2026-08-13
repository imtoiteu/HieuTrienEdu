'use client';

import Link from 'next/link';
import { useRouter, useSearchParams } from 'next/navigation';
import { Copy, Plus, Trash2 } from 'lucide-react';
import { useCallback, useEffect, useState } from 'react';

import { Badge, Button } from '@hietedu/ui';

import { AdminShell } from '@/components/admin/admin-shell';
import { DataTable, type Column } from '@/components/admin/data-table';
import { ConfirmDialog, Modal } from '@/components/admin/dialog';
import { FormRow, SelectField, StatusBadge, TextField } from '@/components/admin/form';
import { useToast } from '@/components/admin/toast';
import { adminApi, type AdminCourse, type AdminLesson, type StructureUnit } from '@/lib/admin-api';
import { useRequireAuth } from '@/lib/auth';
import { useI18n } from '@/lib/i18n';

export default function LessonsPage() {
  const { t, locale, formatDate } = useI18n();
  const { user, loading: authLoading } = useRequireAuth(locale, ['admin']);
  const { run, notify } = useToast();
  const router = useRouter();
  const params = useSearchParams();

  const [rows, setRows] = useState<AdminLesson[]>([]);
  const [meta, setMeta] = useState({ total: 0, page: 1, page_size: 25, pages: 0 });
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState('');
  const [sort, setSort] = useState('updated_at');
  const [order, setOrder] = useState<'asc' | 'desc'>('desc');
  const [filters, setFilters] = useState<Record<string, string>>({});
  const [deleting, setDeleting] = useState<AdminLesson | null>(null);

  const [creating, setCreating] = useState(false);
  const [saving, setSaving] = useState(false);
  const [courses, setCourses] = useState<AdminCourse[]>([]);
  const [units, setUnits] = useState<StructureUnit[]>([]);
  const [form, setForm] = useState({ course_id: 0, topic_id: 0, title: '', estimated_minutes: 15 });

  const href = (path: string) => `/${locale}${path}`;

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const result = await adminApi.lessons.list({ page, search, sort, order, ...filters });
      setRows(result.items);
      setMeta({
        total: result.total,
        page: result.page,
        page_size: result.page_size,
        pages: result.pages,
      });
    } catch (caught) {
      notify((caught as Error).message, 'error');
    } finally {
      setLoading(false);
    }
  }, [page, search, sort, order, filters, notify]);

  useEffect(() => {
    if (user) void load();
  }, [user, load]);

  useEffect(() => {
    if (user) {
      adminApi.courses
        .list({ page_size: 100 })
        .then((result) => setCourses(result.items))
        .catch(() => undefined);
    }
  }, [user]);

  useEffect(() => {
    if (params.get('new')) setCreating(true);
  }, [params]);

  // Loading the course tree is what turns a raw topic_id into a picker an admin can use.
  useEffect(() => {
    if (!form.course_id) {
      setUnits([]);
      return;
    }
    adminApi.courses
      .get(form.course_id)
      .then((course) => setUnits(course.units))
      .catch(() => setUnits([]));
  }, [form.course_id]);

  async function create() {
    if (!form.title.trim() || !form.topic_id) {
      notify(t('admin.les.topicAndTitleRequired'), 'error');
      return;
    }
    setSaving(true);
    const created = await run(
      () =>
        adminApi.lessons.create({
          topic_id: form.topic_id,
          title: form.title,
          estimated_minutes: form.estimated_minutes,
        }),
      t('admin.les.created'),
    );
    setSaving(false);
    if (created) {
      setCreating(false);
      router.push(href(`/admin/lessons/${created.id}`));
    }
  }

  const columns: Column<AdminLesson>[] = [
    {
      key: 'title',
      header: 'Lesson',
      sortKey: 'title',
      render: (row) => (
        <div className="min-w-0">
          <Link
            href={href(`/admin/lessons/${row.id}`)}
            className="block truncate font-bold text-ink-900 hover:text-brand-700 hover:underline"
          >
            {row.title}
          </Link>
          <p className="truncate text-xs text-ink-500">{row.topic_title ?? '—'}</p>
        </div>
      ),
    },
    {
      key: 'blocks',
      header: 'Content',
      hideOnMobile: true,
      render: (row) => (
        <span className="text-xs text-ink-600">
          {row.block_count} block{row.block_count === 1 ? '' : 's'} · {row.estimated_minutes} min
        </span>
      ),
    },
    {
      key: 'status',
      header: 'Status',
      sortKey: 'status',
      render: (row) => (
        <div className="flex flex-wrap items-center gap-1.5">
          <StatusBadge value={row.status} />
          {row.has_draft && <Badge tone="sun">{t('admin.les.unpublishedEdits')}</Badge>}
        </div>
      ),
    },
    {
      key: 'updated',
      header: 'Updated',
      sortKey: 'updated_at',
      hideOnMobile: true,
      render: (row) => <span className="text-xs text-ink-500">{formatDate(row.updated_at)}</span>,
    },
    {
      key: 'actions',
      header: '',
      className: 'text-right',
      render: (row) => (
        <div className="flex justify-end gap-1">
          <button
            type="button"
            aria-label={`Duplicate ${row.title}`}
            onClick={async () => {
              const copy = await run(() => adminApi.lessons.duplicate(row.id), t('admin.les.duplicated'));
              if (copy) await load();
            }}
            className="rounded-lg p-2 text-ink-500 hover:bg-ink-100"
          >
            <Copy className="h-4 w-4" aria-hidden="true" />
          </button>
          <button
            type="button"
            aria-label={`Delete ${row.title}`}
            onClick={() => setDeleting(row)}
            className="rounded-lg p-2 text-coral-600 hover:bg-coral-50"
          >
            <Trash2 className="h-4 w-4" aria-hidden="true" />
          </button>
        </div>
      ),
    },
  ];

  if (authLoading || !user) return <AdminShell loading />;

  const topics = units.flatMap((unit) =>
    unit.topics.map((topic) => ({ ...topic, unitTitle: unit.title })),
  );

  return (
    <AdminShell
      title={t('admin.les.title')}
      description={t('admin.les.subtitle')}
      breadcrumbs={[{ label: t('admin.a.adminCrumb'), href: '/admin' }, { label: t('admin.les.title') }]}
      actions={
        <Button onClick={() => setCreating(true)}>
          <Plus className="h-4 w-4" aria-hidden="true" />{t('admin.les.new')}</Button>
      }
    >
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
        sort={sort}
        order={order}
        onSortChange={(nextSort, nextOrder) => {
          setSort(nextSort);
          setOrder(nextOrder);
        }}
        onPageChange={setPage}
        filters={[
          {
            key: 'status',
            label: t('admin.a.status'),
            options: [
              { value: 'draft', label: t('admin.st.draft') },
              { value: 'published', label: t('admin.st.published') },
              { value: 'archived', label: t('admin.st.archived') },
            ],
          },
          {
            key: 'course_id',
            label: t('admin.crs.course'),
            options: courses.map((course) => ({
              value: String(course.id),
              label: course.title,
            })),
          },
        ]}
        filterValues={filters}
        onFilterChange={(key, value) => {
          setFilters((current) => ({ ...current, [key]: value }));
          setPage(1);
        }}
        emptyTitle={t('admin.les.empty')}
        emptyBody={t('admin.les.emptyBody')}
        emptyAction={
          <Button onClick={() => setCreating(true)}>
            <Plus className="h-4 w-4" aria-hidden="true" />{t('admin.les.createOne')}</Button>
        }
      />

      <Modal
        open={creating}
        onClose={() => setCreating(false)}
        title={t('admin.les.new')}
        description={t('admin.les.newHint')}
        footer={
          <>
            <Button variant="ghost" onClick={() => setCreating(false)}>{t('admin.a.cancel')}</Button>
            <Button loading={saving} onClick={create}>{t('admin.les.createAndEdit')}</Button>
          </>
        }
      >
        <div className="grid gap-4">
          <FormRow label={t('admin.crs.course')} required htmlFor="lesson-course">
            <SelectField
              id="lesson-course"
              value={form.course_id}
              onChange={(event) =>
                setForm({ ...form, course_id: Number(event.target.value), topic_id: 0 })
              }
            >
              <option value={0}>{t('admin.les.chooseCourse')}</option>
              {courses.map((course) => (
                <option key={course.id} value={course.id}>
                  {course.title}
                </option>
              ))}
            </SelectField>
          </FormRow>

          <FormRow label={t('admin.crs.topic')} required htmlFor="lesson-topic">
            <SelectField
              id="lesson-topic"
              value={form.topic_id}
              disabled={!form.course_id}
              onChange={(event) => setForm({ ...form, topic_id: Number(event.target.value) })}
            >
              <option value={0}>
                {form.course_id ? 'Choose a topic…' : 'Choose a course first'}
              </option>
              {topics.map((topic) => (
                <option key={topic.id} value={topic.id}>
                  {topic.unitTitle} → {topic.title}
                </option>
              ))}
            </SelectField>
            {form.course_id > 0 && topics.length === 0 && (
              <p className="mt-1 text-xs text-coral-700">
                This course has no topics yet. Add a module and a topic from the course structure
                screen first.
              </p>
            )}
          </FormRow>

          <FormRow label={t('admin.a.title')} required htmlFor="lesson-title">
            <TextField
              id="lesson-title"
              value={form.title}
              onChange={(event) => setForm({ ...form, title: event.target.value })}
              placeholder={t('admin.crs.placeholderLesson')}
            />
          </FormRow>

          <FormRow label={t('admin.crs.estimatedMinutes')} htmlFor="lesson-minutes">
            <TextField
              id="lesson-minutes"
              type="number"
              min={1}
              value={form.estimated_minutes}
              onChange={(event) =>
                setForm({ ...form, estimated_minutes: Number(event.target.value) })
              }
            />
          </FormRow>
        </div>
      </Modal>

      <ConfirmDialog
        open={deleting !== null}
        onClose={() => setDeleting(null)}
        title={`Delete “${deleting?.title}”?`}
        message="The lesson and its content blocks will be deleted. A snapshot is kept in the activity log."
        onConfirm={async () => {
          if (!deleting) return;
          const ok = await run(() => adminApi.lessons.remove(deleting.id), t('admin.les.deletedToast'));
          if (ok !== undefined) await load();
        }}
      />
    </AdminShell>
  );
}
