'use client';

import { Pencil, Plus, Trash2 } from 'lucide-react';
import { useCallback, useEffect, useState } from 'react';

import { Badge, Button } from '@hietedu/ui';

import { AdminShell } from '@/components/admin/admin-shell';
import { DataTable, type Column } from '@/components/admin/data-table';
import { ConfirmDialog, Modal } from '@/components/admin/dialog';
import {
  CheckboxField,
  FormRow,
  SelectField,
  StatusBadge,
  StringListField,
  TextAreaField,
  TextField,
  TranslationPanel,
  humanise,
  translationDraft,
  translationsPayload,
} from '@/components/admin/form';
import { useToast } from '@/components/admin/toast';
import { adminApi, type AdminTeacher, type Category, type ProgramRow } from '@/lib/admin-api';
import { useRequireAuth } from '@/lib/auth';
import { useI18n } from '@/lib/i18n';

const FORMATS = ['one_to_one', 'group', 'online_live', 'recorded', 'hybrid'];
const MODES = ['online', 'offline', 'hybrid'];

const PROGRAM_FIELDS = [
  { name: 'name', label: '' },
  { name: 'tagline', label: '' },
  { name: 'description', label: '' },
];

const BLANK = {
  name: '',
  tagline: '',
  description: '',
  format: 'group',
  delivery_mode: 'online',
  subject_slug: '',
  grade_min: 6,
  grade_max: 9,
  price_vnd: 0,
  price_unit: 'session',
  sessions_included: 1,
  session_minutes: 90,
  capacity: 1,
  features: [] as string[],
  thumbnail_url: '',
  teacher_id: 0,
  start_date: '',
  end_date: '',
  status: 'draft',
  is_featured: false,
  category_ids: [] as number[],
};

export default function ProgramsPage() {
  const { t, locale, formatCurrency } = useI18n();
  const { user, loading: authLoading } = useRequireAuth(locale, ['admin']);
  const { run, notify } = useToast();

  const [rows, setRows] = useState<ProgramRow[]>([]);
  const [meta, setMeta] = useState({ total: 0, page: 1, page_size: 25, pages: 0 });
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState('');
  const [filters, setFilters] = useState<Record<string, string>>({});
  const [teachers, setTeachers] = useState<AdminTeacher[]>([]);
  const [categories, setCategories] = useState<Category[]>([]);
  const [editing, setEditing] = useState<ProgramRow | null>(null);
  const [creating, setCreating] = useState(false);
  const [saving, setSaving] = useState(false);
  const [form, setForm] = useState({ ...BLANK });
  // The public pricing and tutoring pages localise these, so they need somewhere to be typed.
  const [vi, setVi] = useState<Record<string, string>>({});
  const [deleting, setDeleting] = useState<ProgramRow | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const result = await adminApi.programs.list({ page, search, ...filters });
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
  }, [page, search, filters, notify]);

  useEffect(() => {
    if (user) void load();
  }, [user, load]);

  useEffect(() => {
    if (!user) return;
    adminApi.teachers.list({ page_size: 100 }).then((p) => setTeachers(p.items)).catch(() => undefined);
    adminApi.categories.list({ page_size: 200 }).then((p) => setCategories(p.items)).catch(() => undefined);
  }, [user]);

  function openEdit(program: ProgramRow) {
    setForm({
      name: program.name,
      tagline: program.tagline ?? '',
      description: program.description ?? '',
      format: program.format,
      delivery_mode: program.delivery_mode,
      subject_slug: program.subject_slug ?? '',
      grade_min: program.grade_min,
      grade_max: program.grade_max,
      price_vnd: program.price_vnd,
      price_unit: program.price_unit,
      sessions_included: program.sessions_included,
      session_minutes: program.session_minutes,
      capacity: program.capacity,
      features: program.features ?? [],
      thumbnail_url: program.thumbnail_url ?? '',
      teacher_id: program.teacher_id ?? 0,
      start_date: program.start_date ?? '',
      end_date: program.end_date ?? '',
      status: program.status,
      is_featured: program.is_featured,
      category_ids: program.categories.map((c) => c.id),
    });
    setVi(
      translationDraft(
        (program as { translations?: Record<string, Record<string, unknown>> }).translations,
        PROGRAM_FIELDS,
      ),
    );
    setEditing(program);
  }

  async function save() {
    if (!form.name.trim()) {
      notify(t('admin.a.nameRequired'), 'error');
      return;
    }
    setSaving(true);
    const body = {
      ...form,
      tagline: form.tagline || null,
      description: form.description || null,
      subject_slug: form.subject_slug || null,
      thumbnail_url: form.thumbnail_url || null,
      teacher_id: form.teacher_id || null,
      start_date: form.start_date || null,
      end_date: form.end_date || null,
      translations: translationsPayload(vi),
    };
    const ok = await run(
      () => (editing ? adminApi.programs.update(editing.id, body) : adminApi.programs.create(body)),
      editing ? t('admin.pro.saved') : t('admin.pro.created'),
    );
    setSaving(false);
    if (ok) {
      setEditing(null);
      setCreating(false);
      setForm({ ...BLANK });
      await load();
    }
  }

  const columns: Column<ProgramRow>[] = [
    {
      key: 'name',
      header: t('admin.pro.programme'),
      render: (row) => (
        <div className="min-w-0">
          <button
            type="button"
            onClick={() => openEdit(row)}
            className="block truncate text-left font-bold text-ink-900 hover:text-brand-700 hover:underline"
          >
            {row.name}
          </button>
          <p className="truncate text-xs text-ink-500">{row.tagline ?? `/${row.slug}`}</p>
        </div>
      ),
    },
    {
      key: 'format',
      header: t('admin.a.format'),
      render: (row) => (
        <div className="flex flex-wrap gap-1">
          <Badge tone="brand">{humanise(row.format)}</Badge>
          <Badge tone="neutral">{humanise(row.delivery_mode)}</Badge>
        </div>
      ),
    },
    {
      key: 'grades',
      header: t('admin.pro.grades'),
      hideOnMobile: true,
      render: (row) => (
        <span className="text-sm">
          {row.grade_min === row.grade_max
            ? `Grade ${row.grade_min}`
            : `${row.grade_min}–${row.grade_max}`}
        </span>
      ),
    },
    {
      key: 'price',
      header: t('admin.pro.price'),
      render: (row) => (
        <span className="font-bold tabular-nums">
          {formatCurrency(row.price_vnd)}
          <span className="text-xs font-normal text-ink-500">/{row.price_unit}</span>
        </span>
      ),
    },
    {
      key: 'status',
      header: t('admin.a.status'),
      render: (row) => <StatusBadge value={row.status} />,
    },
    {
      key: 'actions',
      header: '',
      className: 'text-right',
      render: (row) => (
        <div className="flex justify-end gap-1">
          {row.status === 'published' ? (
            <Button
              size="sm"
              variant="outline"
              onClick={async () => {
                const ok = await run(
                  () => adminApi.programs.setStatus(row.id, 'draft'),
                  t('admin.pro.unpublishedToast'),
                );
                if (ok) await load();
              }}
            >{t('admin.a.unpublish')}</Button>
          ) : (
            <Button
              size="sm"
              variant="outline"
              onClick={async () => {
                const ok = await run(
                  () => adminApi.programs.setStatus(row.id, 'published'),
                  t('admin.pro.publishedToast'),
                );
                if (ok) await load();
              }}
            >{t('admin.a.publish')}</Button>
          )}
          <button
            type="button"
            aria-label={`Edit ${row.name}`}
            onClick={() => openEdit(row)}
            className="rounded-lg p-2 text-ink-500 hover:bg-ink-100"
          >
            <Pencil className="h-4 w-4" aria-hidden="true" />
          </button>
          <button
            type="button"
            aria-label={`Delete ${row.name}`}
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

  return (
    <AdminShell
      title={t('admin.pro.title')}
      description={t('admin.pro.subtitle')}
      breadcrumbs={[{ label: t('admin.a.adminCrumb'), href: '/admin' }, { label: 'Programs' }]}
      actions={
        <Button
          onClick={() => {
            setForm({ ...BLANK });
            setVi({});
            setCreating(true);
          }}
        >
          <Plus className="h-4 w-4" aria-hidden="true" />{t('admin.pro.new')}</Button>
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
        onPageChange={setPage}
        filters={[
          {
            key: 'format',
            label: t('admin.a.format'),
            options: FORMATS.map((f) => ({ value: f, label: humanise(f) })),
          },
          {
            key: 'status',
            label: t('admin.a.status'),
            options: [
              { value: 'draft', label: t('admin.st.draft') },
              { value: 'published', label: t('admin.st.published') },
              { value: 'archived', label: t('admin.st.archived') },
            ],
          },
        ]}
        filterValues={filters}
        onFilterChange={(key, value) => {
          setFilters((current) => ({ ...current, [key]: value }));
          setPage(1);
        }}
        emptyTitle={t('admin.pro.empty')}
        emptyBody={t('admin.pro.emptyBody')}
      />

      <Modal
        open={creating || editing !== null}
        onClose={() => {
          setCreating(false);
          setEditing(null);
        }}
        title={editing ? `Edit “${editing.name}”` : 'New programme'}
        size="lg"
        footer={
          <>
            <Button
              variant="ghost"
              onClick={() => {
                setCreating(false);
                setEditing(null);
              }}
            >{t('admin.a.cancel')}</Button>
            <Button loading={saving} onClick={save}>
              {editing ? 'Save changes' : 'Create programme'}
            </Button>
          </>
        }
      >
        <div className="grid gap-4 sm:grid-cols-2">
          <FormRow label={t('admin.a.name')} required htmlFor="p-name" className="sm:col-span-2">
            <TextField
              id="p-name"
              value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
              placeholder={t('admin.pro.namePlaceholder')}
            />
          </FormRow>
          <FormRow label={t('admin.pro.tagline')} htmlFor="p-tagline" className="sm:col-span-2">
            <TextField
              id="p-tagline"
              value={form.tagline}
              onChange={(e) => setForm({ ...form, tagline: e.target.value })}
            />
          </FormRow>
          <FormRow label={t('admin.a.description')} htmlFor="p-desc" className="sm:col-span-2">
            <TextAreaField
              id="p-desc"
              value={form.description}
              onChange={(e) => setForm({ ...form, description: e.target.value })}
            />
          </FormRow>
          <div className="sm:col-span-2">
            <TranslationPanel
              fields={[
                { name: 'name', label: t('admin.a.name') },
                { name: 'tagline', label: t('admin.pro.tagline') },
                { name: 'description', label: t('admin.a.description'), multiline: true },
              ]}
              value={vi}
              onChange={setVi}
            />
          </div>
          <FormRow label={t('admin.a.format')} htmlFor="p-format">
            <SelectField
              id="p-format"
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
          <FormRow label={t('admin.a.delivery')} htmlFor="p-mode">
            <SelectField
              id="p-mode"
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
          <FormRow label={t('admin.pro.lowestGrade')} htmlFor="p-gmin">
            <TextField
              id="p-gmin"
              type="number"
              min={1}
              max={12}
              value={form.grade_min}
              onChange={(e) => setForm({ ...form, grade_min: Number(e.target.value) })}
            />
          </FormRow>
          <FormRow label={t('admin.pro.highestGrade')} htmlFor="p-gmax">
            <TextField
              id="p-gmax"
              type="number"
              min={1}
              max={12}
              value={form.grade_max}
              onChange={(e) => setForm({ ...form, grade_max: Number(e.target.value) })}
            />
          </FormRow>
          <FormRow label={t('admin.pro.priceVnd')} htmlFor="p-price">
            <TextField
              id="p-price"
              type="number"
              min={0}
              value={form.price_vnd}
              onChange={(e) => setForm({ ...form, price_vnd: Number(e.target.value) })}
            />
          </FormRow>
          <FormRow label={t('admin.pro.priceUnit')} htmlFor="p-unit">
            <SelectField
              id="p-unit"
              value={form.price_unit}
              onChange={(e) => setForm({ ...form, price_unit: e.target.value })}
            >
              <option value="session">per session</option>
              <option value="month">per month</option>
              <option value="course">per course</option>
            </SelectField>
          </FormRow>
          <FormRow label={t('admin.pro.sessionsIncluded')} htmlFor="p-sessions">
            <TextField
              id="p-sessions"
              type="number"
              min={1}
              value={form.sessions_included}
              onChange={(e) => setForm({ ...form, sessions_included: Number(e.target.value) })}
            />
          </FormRow>
          <FormRow label={t('admin.pro.sessionMinutes')} htmlFor="p-minutes">
            <TextField
              id="p-minutes"
              type="number"
              min={15}
              value={form.session_minutes}
              onChange={(e) => setForm({ ...form, session_minutes: Number(e.target.value) })}
            />
          </FormRow>
          <FormRow label={t('admin.pro.classSize')} htmlFor="p-capacity">
            <TextField
              id="p-capacity"
              type="number"
              min={1}
              value={form.capacity}
              onChange={(e) => setForm({ ...form, capacity: Number(e.target.value) })}
            />
          </FormRow>
          <FormRow label={t('admin.pro.subjectSlug')} htmlFor="p-subject">
            <TextField
              id="p-subject"
              value={form.subject_slug}
              onChange={(e) => setForm({ ...form, subject_slug: e.target.value })}
              placeholder="mathematics"
            />
          </FormRow>
          <FormRow label={t('admin.a.teacher')} htmlFor="p-teacher">
            <SelectField
              id="p-teacher"
              value={form.teacher_id}
              onChange={(e) => setForm({ ...form, teacher_id: Number(e.target.value) })}
            >
              <option value={0}>{t('admin.a.none')}</option>
              {teachers.map((teacher) => (
                <option key={teacher.id} value={teacher.id}>
                  {teacher.full_name}
                </option>
              ))}
            </SelectField>
          </FormRow>
          <FormRow label={t('admin.a.thumbnailUrl')} htmlFor="p-thumb">
            <TextField
              id="p-thumb"
              value={form.thumbnail_url}
              onChange={(e) => setForm({ ...form, thumbnail_url: e.target.value })}
            />
          </FormRow>
          <FormRow label={t('admin.pro.starts')} htmlFor="p-start">
            <TextField
              id="p-start"
              type="date"
              value={form.start_date}
              onChange={(e) => setForm({ ...form, start_date: e.target.value })}
            />
          </FormRow>
          <FormRow label={t('admin.pro.ends')} htmlFor="p-end">
            <TextField
              id="p-end"
              type="date"
              value={form.end_date}
              onChange={(e) => setForm({ ...form, end_date: e.target.value })}
            />
          </FormRow>
          <FormRow label={t('admin.pro.included')} className="sm:col-span-2">
            <StringListField
              values={form.features}
              onChange={(features) => setForm({ ...form, features })}
              placeholder={t('admin.pro.includedPlaceholder')}
            />
          </FormRow>
          <FormRow label={t('admin.a.categories')} className="sm:col-span-2">
            <div className="flex flex-wrap gap-1.5">
              {categories.map((category) => {
                const selected = form.category_ids.includes(category.id);
                return (
                  <button
                    key={category.id}
                    type="button"
                    onClick={() =>
                      setForm({
                        ...form,
                        category_ids: selected
                          ? form.category_ids.filter((cid) => cid !== category.id)
                          : [...form.category_ids, category.id],
                      })
                    }
                    className={`rounded-full border-2 px-3 py-1 text-xs font-bold ${
                      selected
                        ? 'border-brand-500 bg-brand-500 text-white'
                        : 'border-ink-200 text-ink-700'
                    }`}
                  >
                    {category.name}
                  </button>
                );
              })}
            </div>
          </FormRow>
          <div className="sm:col-span-2">
            <CheckboxField
              label={t('admin.a.featureOnHome')}
              checked={form.is_featured}
              onChange={(value) => setForm({ ...form, is_featured: value })}
            />
          </div>
        </div>
      </Modal>

      <ConfirmDialog
        open={deleting !== null}
        onClose={() => setDeleting(null)}
        title={`Delete “${deleting?.name}”?`}
        message={t('admin.pro.deleteBody')}
        onConfirm={async () => {
          if (!deleting) return;
          const ok = await run(() => adminApi.programs.remove(deleting.id), t('admin.pro.deletedToast'));
          if (ok !== undefined) await load();
        }}
      />
    </AdminShell>
  );
}
