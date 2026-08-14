'use client';

import Link from 'next/link';
import { useRouter, useSearchParams } from 'next/navigation';
import { Copy, Layers, Plus, Star, Trash2 } from 'lucide-react';
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
  TextAreaField,
  TextField,
  TranslationPanel,
  translationsPayload,
} from '@/components/admin/form';
import { useToast } from '@/components/admin/toast';
import { useContentLabel, useIsUntranslated } from '@/lib/content-label';
import { adminApi, type AdminCourse, type Category } from '@/lib/admin-api';
import { useRequireAuth } from '@/lib/auth';
import { useI18n } from '@/lib/i18n';

const GRADES = Array.from({ length: 12 }, (_, index) => index + 1);

export default function CoursesPage() {
  const { t, locale } = useI18n();
  const label = useContentLabel();
  // An English title on a Vietnamese screen is ambiguous — content or fallback? — so the
  // fallback says so rather than passing silently for a translation.
  const untranslated = useIsUntranslated();
  const { user, loading: authLoading } = useRequireAuth(locale, ['admin']);
  const { run, notify } = useToast();
  const router = useRouter();
  const params = useSearchParams();

  const [rows, setRows] = useState<AdminCourse[]>([]);
  const [meta, setMeta] = useState({ total: 0, page: 1, page_size: 25, pages: 0 });
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState('');
  const [sort, setSort] = useState('position');
  const [order, setOrder] = useState<'asc' | 'desc'>('asc');
  const [filters, setFilters] = useState<Record<string, string>>({});

  const [subjects, setSubjects] = useState<{ id: number; name: string }[]>([]);
  const [categories, setCategories] = useState<Category[]>([]);
  const [creating, setCreating] = useState(false);
  const [saving, setSaving] = useState(false);
  const [deleting, setDeleting] = useState<AdminCourse | null>(null);
  const [form, setForm] = useState({
    subject_id: 0,
    title: '',
    grade: 6,
    summary: '',
    description: '',
    status: 'draft',
    is_featured: false,
    category_ids: [] as number[],
  });
  const [vi, setVi] = useState<Record<string, string>>({ title: '', summary: '' });

  const href = (path: string) => `/${locale}${path}`;

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const result = await adminApi.courses.list({
        page,
        search,
        sort,
        order,
        ...filters,
      });
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
    if (!user) return;
    Promise.all([adminApi.subjects.list(), adminApi.categories.list({ page_size: 200 })])
      .then(([subjectRows, categoryRows]) => {
        setSubjects(subjectRows);
        setCategories(categoryRows.items);
        setForm((current) => ({
          ...current,
          subject_id: current.subject_id || subjectRows[0]?.id || 0,
        }));
      })
      .catch(() => undefined);
  }, [user]);

  useEffect(() => {
    if (params.get('new')) setCreating(true);
  }, [params]);

  async function create() {
    if (!form.title.trim()) {
      notify(t('admin.a.titleRequired'), 'error');
      return;
    }
    if (!form.subject_id) {
      notify(t('admin.crs.createSubjectFirst'), 'error');
      return;
    }
    setSaving(true);
    const created = await run(
      () =>
        adminApi.courses.create({
          ...form,
          summary: form.summary || null,
          description: form.description || null,
          translations: translationsPayload(vi),
        }),
      t('admin.crs.created'),
    );
    setSaving(false);
    if (created) {
      setCreating(false);
      router.push(href(`/admin/courses/${created.id}`));
    }
  }

  const columns: Column<AdminCourse>[] = [
    {
      key: 'title',
      header: t('admin.a.course'),
      sortKey: 'title',
      render: (row) => (
        <div className="min-w-0">
          <Link
            href={href(`/admin/courses/${row.id}`)}
            className="block truncate font-bold text-ink-900 hover:text-brand-700 hover:underline"
          >
            {label(row, 'title')}
          </Link>
          <p className="truncate text-xs text-ink-500">
            {row.subject_name} · /{row.slug}
          </p>
            {untranslated(row, 'title') && (
              <span
                title={t('admin.a.untranslatedHint', { language: t('admin.les.vietnamese') })}
              >
                <Badge tone="neutral">{t('admin.a.untranslated')}</Badge>
              </span>
            )}
        </div>
      ),
    },
    {
      key: 'grade',
      header: t('admin.a.grade'),
      sortKey: 'grade',
      render: (row) => (
        <Badge tone="neutral">{t('admin.a.gradeN', { n: row.grade })}</Badge>
      ),
    },
    {
      key: 'structure',
      header: t('admin.crs.structure'),
      hideOnMobile: true,
      render: (row) => (
        <span className="text-xs text-ink-600">
          {t('admin.crs.structureSummary', {
            units: row.unit_count ?? 0,
            topics: row.topic_count ?? 0,
            lessons: row.lesson_count ?? 0,
          })}
        </span>
      ),
    },
    {
      key: 'categories',
      header: t('admin.a.categories'),
      hideOnMobile: true,
      render: (row) =>
        row.categories.length === 0 ? (
          <span className="text-xs text-ink-400">—</span>
        ) : (
          <div className="flex flex-wrap gap-1">
            {row.categories.slice(0, 3).map((category) => (
              <Badge key={category.id} tone="brand">
                {category.name}
              </Badge>
            ))}
          </div>
        ),
    },
    {
      key: 'status',
      header: t('admin.a.status'),
      sortKey: 'status',
      render: (row) => (
        <div className="flex items-center gap-1.5">
          <StatusBadge value={row.status} />
          {row.is_featured && (
            <Star className="h-4 w-4 fill-sun-400 text-sun-500" aria-label={t('admin.a.featured')} />
          )}
        </div>
      ),
    },
    {
      key: 'actions',
      header: '',
      className: 'text-right',
      render: (row) => (
        <div className="flex justify-end gap-1">
          <Link href={href(`/admin/courses/${row.id}`)}>
            <Button size="sm" variant="outline">
              <Layers className="h-4 w-4" aria-hidden="true" />{t('admin.crs.structure')}</Button>
          </Link>
          <button
            type="button"
            aria-label={t('admin.a.duplicateAria', { name: label(row, 'title') })}
            onClick={async () => {
              const copy = await run(
                () => adminApi.courses.duplicate(row.id),
                t('admin.crs.duplicated'),
              );
              if (copy) await load();
            }}
            className="rounded-lg p-2 text-ink-500 hover:bg-ink-100"
          >
            <Copy className="h-4 w-4" aria-hidden="true" />
          </button>
          <button
            type="button"
            aria-label={t('admin.a.deleteAria', { name: label(row, 'title') })}
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
      title={t('admin.crs.title')}
      description={t('admin.crs.subtitle')}
      breadcrumbs={[{ label: t('admin.a.adminCrumb'), href: '/admin' }, { label: t('admin.crs.title') }]}
      actions={
        <Button onClick={() => setCreating(true)}>
          <Plus className="h-4 w-4" aria-hidden="true" />{t('admin.crs.new')}</Button>
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
            key: 'grade',
            label: t('admin.a.grade'),
            options: GRADES.map((grade) => ({
              value: String(grade),
              label: t('admin.a.gradeN', { n: grade }),
            })),
          },
          {
            key: 'subject_id',
            label: t('admin.st.subject'),
            options: subjects.map((subject) => ({
              value: String(subject.id),
              label: subject.name,
            })),
          },
          {
            key: 'category_id',
            label: t('admin.a.category'),
            options: categories.map((category) => ({
              value: String(category.id),
              label: category.name,
            })),
          },
        ]}
        filterValues={filters}
        onFilterChange={(key, value) => {
          setFilters((current) => ({ ...current, [key]: value }));
          setPage(1);
        }}
        emptyTitle={t('admin.crs.empty')}
        emptyBody={t('admin.crs.emptyBody')}
        emptyAction={
          <Button onClick={() => setCreating(true)}>
            <Plus className="h-4 w-4" aria-hidden="true" />{t('admin.crs.createFirst')}</Button>
        }
      />

      <Modal
        open={creating}
        onClose={() => setCreating(false)}
        title={t('admin.crs.new')}
        description={t('admin.crs.newHint')}
        footer={
          <>
            <Button variant="ghost" onClick={() => setCreating(false)}>{t('admin.a.cancel')}</Button>
            <Button loading={saving} onClick={create}>{t('admin.crs.createCourse')}</Button>
          </>
        }
      >
        <div className="grid gap-4 sm:grid-cols-2">
          <FormRow label={t('admin.a.title')} required htmlFor="course-title" className="sm:col-span-2">
            <TextField
              id="course-title"
              value={form.title}
              onChange={(event) => setForm({ ...form, title: event.target.value })}
              placeholder={t('admin.crs.placeholderTitle')}
            />
          </FormRow>
          <FormRow label={t('admin.a.subject')} required htmlFor="course-subject">
            <SelectField
              id="course-subject"
              value={form.subject_id}
              onChange={(event) => setForm({ ...form, subject_id: Number(event.target.value) })}
            >
              {subjects.length === 0 && <option value="">{t('admin.crs.noSubjects')}</option>}
              {subjects.map((subject) => (
                <option key={subject.id} value={subject.id}>
                  {subject.name}
                </option>
              ))}
            </SelectField>
          </FormRow>
          <FormRow
            label={t('admin.a.grade')}
            required
            htmlFor="course-grade"
            hint={t('admin.crs.oneGradeHint')}
          >
            <SelectField
              id="course-grade"
              value={form.grade}
              onChange={(event) => setForm({ ...form, grade: Number(event.target.value) })}
            >
              {GRADES.map((grade) => (
                <option key={grade} value={grade}>
                  {t('admin.a.gradeN', { n: grade })}
                </option>
              ))}
            </SelectField>
          </FormRow>
          <FormRow label={t('admin.a.summary')} htmlFor="course-summary" className="sm:col-span-2">
            <TextAreaField
              id="course-summary"
              value={form.summary}
              onChange={(event) => setForm({ ...form, summary: event.target.value })}
            />
          </FormRow>
          <div className="sm:col-span-2">
            <TranslationPanel
              fields={[
                { name: 'title', label: t('admin.a.title') },
                { name: 'summary', label: t('admin.a.summary'), multiline: true },
              ]}
              value={vi}
              onChange={setVi}
            />
          </div>
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
                          ? form.category_ids.filter((id) => id !== category.id)
                          : [...form.category_ids, category.id],
                      })
                    }
                    className={`rounded-full border-2 px-3 py-1 text-xs font-bold ${
                      selected
                        ? 'border-brand-500 bg-brand-500 text-white'
                        : 'border-ink-200 text-ink-700'
                    }`}
                  >
                    {label(category, 'name')}
                  </button>
                );
              })}
              {categories.length === 0 && (
                <p className="text-xs text-ink-500">
                  No categories yet — create some under Topics &amp; categories.
                </p>
              )}
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
        title={t('admin.a.deleteQ', { name: deleting?.title ?? '' })}
        confirmText={deleting?.title}
        message={
          <>
            {t('admin.crs.deleteBody', {
              units: deleting?.unit_count ?? 0,
              topics: deleting?.topic_count ?? 0,
              skills: deleting?.skill_count ?? 0,
              lessons: deleting?.lesson_count ?? 0,
            })}
          </>
        }
        onConfirm={async () => {
          if (!deleting) return;
          const ok = await run(() => adminApi.courses.remove(deleting.id), t('admin.crs.deletedToast'));
          if (ok !== undefined) await load();
        }}
      />
    </AdminShell>
  );
}
