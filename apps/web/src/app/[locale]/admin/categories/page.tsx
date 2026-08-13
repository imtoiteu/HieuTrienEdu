'use client';

import { ArrowDown, ArrowUp, Eye, EyeOff, Pencil, Plus, Trash2 } from 'lucide-react';
import { useSearchParams } from 'next/navigation';
import { useCallback, useEffect, useMemo, useState } from 'react';

import { Badge, Button, Card } from '@hietedu/ui';

import { AdminShell } from '@/components/admin/admin-shell';
import { ConfirmDialog, Modal } from '@/components/admin/dialog';
import {
  CheckboxField,
  FormRow,
  SelectField,
  TextAreaField,
  TextField,
  humanise,
} from '@/components/admin/form';
import { useToast } from '@/components/admin/toast';
import { adminApi, type Category, type CategoryKind } from '@/lib/admin-api';
import { useRequireAuth } from '@/lib/auth';
import { useI18n } from '@/lib/i18n';

const KINDS: CategoryKind[] = ['subject', 'grade', 'program', 'topic', 'tag'];

const BLANK = {
  name: '',
  slug: '',
  description: '',
  kind: 'topic' as CategoryKind,
  parent_id: null as number | null,
  image_url: '',
  is_published: true,
  is_visible_in_nav: false,
  seo_title: '',
  seo_description: '',
};

export default function CategoriesPage() {
  const { t, locale } = useI18n();
  const { user, loading: authLoading } = useRequireAuth(locale, ['admin']);
  const { run, notify } = useToast();
  const params = useSearchParams();

  const [rows, setRows] = useState<Category[]>([]);
  const [loading, setLoading] = useState(true);
  const [editing, setEditing] = useState<Category | null>(null);
  const [creating, setCreating] = useState(false);
  const [form, setForm] = useState({ ...BLANK });
  const [saving, setSaving] = useState(false);
  const [deleting, setDeleting] = useState<Category | null>(null);
  const [kindFilter, setKindFilter] = useState('');

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const result = await adminApi.categories.list({ page_size: 200 });
      setRows(result.items);
    } catch (caught) {
      notify((caught as Error).message, 'error');
    } finally {
      setLoading(false);
    }
  }, [notify]);

  useEffect(() => {
    if (user) void load();
  }, [user, load]);

  // `?new=1` from a dashboard quick action opens the create form directly.
  useEffect(() => {
    if (params.get('new')) {
      setForm({ ...BLANK });
      setCreating(true);
    }
  }, [params]);

  const visible = useMemo(
    () => (kindFilter ? rows.filter((row) => row.kind === kindFilter) : rows),
    [rows, kindFilter],
  );

  /** Rows arranged parent-then-children, so the tree reads correctly in a flat list. */
  const ordered = useMemo(() => {
    const byParent = new Map<number | null, Category[]>();
    visible.forEach((row) => {
      const key = row.parent_id && visible.some((r) => r.id === row.parent_id)
        ? row.parent_id
        : null;
      byParent.set(key, [...(byParent.get(key) ?? []), row]);
    });
    const result: { row: Category; depth: number }[] = [];
    const walk = (parent: number | null, depth: number) => {
      (byParent.get(parent) ?? [])
        .sort((a, b) => a.position - b.position)
        .forEach((row) => {
          result.push({ row, depth });
          walk(row.id, depth + 1);
        });
    };
    walk(null, 0);
    return result;
  }, [visible]);

  function openEdit(category: Category) {
    setForm({
      name: category.name,
      slug: category.slug,
      description: category.description ?? '',
      kind: category.kind,
      parent_id: category.parent_id,
      image_url: category.image_url ?? '',
      is_published: category.is_published,
      is_visible_in_nav: category.is_visible_in_nav,
      seo_title: category.seo_title ?? '',
      seo_description: category.seo_description ?? '',
    });
    setEditing(category);
  }

  async function save() {
    if (!form.name.trim()) {
      notify(t('admin.a.nameRequired'), 'error');
      return;
    }
    setSaving(true);
    const body = {
      ...form,
      slug: form.slug.trim() || undefined,
      description: form.description || null,
      image_url: form.image_url || null,
      seo_title: form.seo_title || null,
      seo_description: form.seo_description || null,
    };
    const result = await run(
      async () =>
        editing
          ? adminApi.categories.update(editing.id, body)
          : adminApi.categories.create(body),
      editing ? 'Category updated' : 'Category created',
    );
    setSaving(false);
    if (result) {
      setEditing(null);
      setCreating(false);
      await load();
    }
  }

  async function move(category: Category, direction: -1 | 1) {
    const siblings = ordered
      .map((entry) => entry.row)
      .filter((row) => row.parent_id === category.parent_id);
    const index = siblings.findIndex((row) => row.id === category.id);
    const target = index + direction;
    if (target < 0 || target >= siblings.length) return;

    const reordered = [...siblings];
    [reordered[index], reordered[target]] = [reordered[target], reordered[index]];
    const ok = await run(
      () => adminApi.categories.reorder(reordered.map((row) => row.id)),
      t('admin.a.orderSaved'),
    );
    if (ok) await load();
  }

  async function togglePublish(category: Category) {
    const ok = await run(
      () =>
        category.is_published
          ? adminApi.categories.unpublish(category.id)
          : adminApi.categories.publish(category.id),
      category.is_published ? 'Category hidden from the site' : 'Category published',
    );
    if (ok) await load();
  }

  if (authLoading || !user) return <AdminShell loading />;

  const dialogOpen = creating || editing !== null;

  return (
    <AdminShell
      title={t('admin.cat.title')}
      description={t('admin.cat.subtitle')}
      breadcrumbs={[{ label: t('admin.a.adminCrumb'), href: '/admin' }, { label: t('admin.cat.title') }]}
      actions={
        <Button
          onClick={() => {
            setForm({ ...BLANK });
            setCreating(true);
          }}
        >
          <Plus className="h-4 w-4" aria-hidden="true" />{t('admin.cat.new')}</Button>
      }
    >
      <div className="mb-4 flex flex-wrap gap-2">
        <button
          type="button"
          onClick={() => setKindFilter('')}
          className={`rounded-full border-2 px-3 py-1 text-xs font-bold ${
            kindFilter === '' ? 'border-brand-500 bg-brand-500 text-white' : 'border-ink-200'
          }`}
        >
          All ({rows.length})
        </button>
        {KINDS.map((kind) => {
          const count = rows.filter((row) => row.kind === kind).length;
          return (
            <button
              key={kind}
              type="button"
              onClick={() => setKindFilter(kind)}
              className={`rounded-full border-2 px-3 py-1 text-xs font-bold ${
                kindFilter === kind ? 'border-brand-500 bg-brand-500 text-white' : 'border-ink-200'
              }`}
            >
              {humanise(kind)} ({count})
            </button>
          );
        })}
      </div>

      <Card className="p-0">
        {loading ? (
          <p className="p-8 text-center text-sm text-ink-500">{t('admin.a.loading')}</p>
        ) : ordered.length === 0 ? (
          <div className="p-8 text-center">
            <p className="font-bold text-ink-800">{t('admin.cat.empty')}</p>
            <p className="mt-1 text-sm text-ink-500">{t('admin.cat.emptyBody')}</p>
            <Button
              className="mt-4"
              onClick={() => {
                setForm({ ...BLANK });
                setCreating(true);
              }}
            >
              <Plus className="h-4 w-4" aria-hidden="true" />{t('admin.cat.new')}</Button>
          </div>
        ) : (
          <ul className="divide-y divide-ink-100">
            {ordered.map(({ row, depth }) => (
              <li
                key={row.id}
                className="flex flex-wrap items-center gap-3 px-4 py-3"
                style={{ paddingLeft: `${1 + depth * 1.5}rem` }}
              >
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="font-bold text-ink-900">{row.name}</span>
                    <Badge tone="neutral">{humanise(row.kind)}</Badge>
                    {!row.is_published && <Badge tone="coral">{t('admin.a.hidden')}</Badge>}
                    {row.is_visible_in_nav && <Badge tone="brand">{t('admin.cat.inMenu')}</Badge>}
                  </div>
                  <p className="truncate text-xs text-ink-500">
                    /{row.slug}
                    {(row.course_count ?? 0) > 0 && ` · ${row.course_count} course(s)`}
                    {(row.product_count ?? 0) > 0 && ` · ${row.product_count} programme(s)`}
                  </p>
                </div>
                <div className="flex items-center gap-1">
                  <button
                    type="button"
                    onClick={() => move(row, -1)}
                    aria-label={`Move ${row.name} up`}
                    className="rounded-lg p-1.5 text-ink-500 hover:bg-ink-100"
                  >
                    <ArrowUp className="h-4 w-4" aria-hidden="true" />
                  </button>
                  <button
                    type="button"
                    onClick={() => move(row, 1)}
                    aria-label={`Move ${row.name} down`}
                    className="rounded-lg p-1.5 text-ink-500 hover:bg-ink-100"
                  >
                    <ArrowDown className="h-4 w-4" aria-hidden="true" />
                  </button>
                  <button
                    type="button"
                    onClick={() => togglePublish(row)}
                    aria-label={row.is_published ? `Hide ${row.name}` : `Publish ${row.name}`}
                    className="rounded-lg p-1.5 text-ink-500 hover:bg-ink-100"
                  >
                    {row.is_published ? (
                      <EyeOff className="h-4 w-4" aria-hidden="true" />
                    ) : (
                      <Eye className="h-4 w-4" aria-hidden="true" />
                    )}
                  </button>
                  <button
                    type="button"
                    onClick={() => openEdit(row)}
                    aria-label={`Edit ${row.name}`}
                    className="rounded-lg p-1.5 text-ink-500 hover:bg-ink-100"
                  >
                    <Pencil className="h-4 w-4" aria-hidden="true" />
                  </button>
                  <button
                    type="button"
                    onClick={() => setDeleting(row)}
                    aria-label={`Delete ${row.name}`}
                    className="rounded-lg p-1.5 text-coral-600 hover:bg-coral-50"
                  >
                    <Trash2 className="h-4 w-4" aria-hidden="true" />
                  </button>
                </div>
              </li>
            ))}
          </ul>
        )}
      </Card>

      <Modal
        open={dialogOpen}
        onClose={() => {
          setEditing(null);
          setCreating(false);
        }}
        title={editing ? `Edit “${editing.name}”` : 'New category'}
        description={t('admin.cat.modalHint')}
        footer={
          <>
            <Button
              variant="ghost"
              onClick={() => {
                setEditing(null);
                setCreating(false);
              }}
            >{t('admin.a.cancel')}</Button>
            <Button loading={saving} onClick={save}>
              {editing ? 'Save changes' : 'Create category'}
            </Button>
          </>
        }
      >
        <div className="grid gap-4 sm:grid-cols-2">
          <FormRow label={t('admin.a.name')} required htmlFor="cat-name" className="sm:col-span-2">
            <TextField
              id="cat-name"
              value={form.name}
              onChange={(event) => setForm({ ...form, name: event.target.value })}
              placeholder="e.g. Luyện thi vào 10"
            />
          </FormRow>

          <FormRow
            label={t('admin.a.slug')}
            hint={t('admin.a.slugHint')}
            htmlFor="cat-slug"
          >
            <TextField
              id="cat-slug"
              value={form.slug}
              onChange={(event) => setForm({ ...form, slug: event.target.value })}
              placeholder="luyen-thi-vao-10"
            />
          </FormRow>

          <FormRow label={t('admin.cat.kind')} htmlFor="cat-kind">
            <SelectField
              id="cat-kind"
              value={form.kind}
              onChange={(event) =>
                setForm({ ...form, kind: event.target.value as CategoryKind })
              }
            >
              {KINDS.map((kind) => (
                <option key={kind} value={kind}>
                  {humanise(kind)}
                </option>
              ))}
            </SelectField>
          </FormRow>

          <FormRow label={t('admin.cat.parent')} htmlFor="cat-parent" className="sm:col-span-2">
            <SelectField
              id="cat-parent"
              value={form.parent_id ?? ''}
              onChange={(event) =>
                setForm({
                  ...form,
                  parent_id: event.target.value ? Number(event.target.value) : null,
                })
              }
            >
              <option value="">{t('admin.cat.topLevel')}</option>
              {rows
                .filter((row) => row.id !== editing?.id)
                .map((row) => (
                  <option key={row.id} value={row.id}>
                    {row.name}
                  </option>
                ))}
            </SelectField>
          </FormRow>

          <FormRow label={t('admin.a.description')} htmlFor="cat-desc" className="sm:col-span-2">
            <TextAreaField
              id="cat-desc"
              value={form.description}
              onChange={(event) => setForm({ ...form, description: event.target.value })}
            />
          </FormRow>

          <FormRow label={t('admin.a.imageUrl')} htmlFor="cat-image" className="sm:col-span-2">
            <TextField
              id="cat-image"
              value={form.image_url}
              onChange={(event) => setForm({ ...form, image_url: event.target.value })}
              placeholder="/media/image/…"
            />
          </FormRow>

          <FormRow label={t('admin.a.seoTitle')} htmlFor="cat-seo-title">
            <TextField
              id="cat-seo-title"
              value={form.seo_title}
              onChange={(event) => setForm({ ...form, seo_title: event.target.value })}
            />
          </FormRow>

          <FormRow label={t('admin.a.seoDescription')} htmlFor="cat-seo-desc">
            <TextField
              id="cat-seo-desc"
              value={form.seo_description}
              onChange={(event) => setForm({ ...form, seo_description: event.target.value })}
            />
          </FormRow>

          <div className="space-y-2 sm:col-span-2">
            <CheckboxField
              label={t('admin.a.published')}
              hint="Unpublished categories are hidden from the public website."
              checked={form.is_published}
              onChange={(value) => setForm({ ...form, is_published: value })}
            />
            <CheckboxField
              label={t('admin.cat.showInNav')}
              checked={form.is_visible_in_nav}
              onChange={(value) => setForm({ ...form, is_visible_in_nav: value })}
            />
          </div>
        </div>
      </Modal>

      <ConfirmDialog
        open={deleting !== null}
        onClose={() => setDeleting(null)}
        title={`Delete “${deleting?.name}”?`}
        message={
          <>
            This removes the category from the site. Courses and programmes in it are not deleted,
            but they lose this grouping.
            {rows.some((row) => row.parent_id === deleting?.id) && (
              <span className="mt-2 block font-semibold">{t('admin.cat.deleteChildren')}</span>
            )}
          </>
        }
        onConfirm={async () => {
          if (!deleting) return;
          const ok = await run(
            () => adminApi.categories.remove(deleting.id),
            t('admin.cat.deleted'),
          );
          if (ok !== undefined) await load();
        }}
      />
    </AdminShell>
  );
}
