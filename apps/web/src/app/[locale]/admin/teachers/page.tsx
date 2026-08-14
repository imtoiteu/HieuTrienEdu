'use client';

import Link from 'next/link';
import { Eye, EyeOff, Plus, Star } from 'lucide-react';
import { useCallback, useEffect, useState } from 'react';

import { Alert, Avatar, Badge, Button } from '@hietedu/ui';

import { AdminShell } from '@/components/admin/admin-shell';
import { DataTable, type Column } from '@/components/admin/data-table';
import { Modal } from '@/components/admin/dialog';
import { CheckboxField, FormRow, StringListField, TextAreaField, TextField } from '@/components/admin/form';
import { useToast } from '@/components/admin/toast';
import { adminApi, type AdminTeacher } from '@/lib/admin-api';
import { useRequireAuth } from '@/lib/auth';
import { useI18n } from '@/lib/i18n';

export default function TeachersPage() {
  const { t, locale } = useI18n();
  const { user, loading: authLoading } = useRequireAuth(locale, ['admin']);
  const { run, notify } = useToast();

  const [rows, setRows] = useState<AdminTeacher[]>([]);
  const [meta, setMeta] = useState({ total: 0, page: 1, page_size: 25, pages: 0 });
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState('');
  const [filters, setFilters] = useState<Record<string, string>>({});
  const [creating, setCreating] = useState(false);
  const [saving, setSaving] = useState(false);
  const [created, setCreated] = useState<AdminTeacher | null>(null);
  const [form, setForm] = useState({
    full_name: '',
    email: '',
    headline: '',
    bio: '',
    subjects: [] as string[],
    grades: [] as number[],
    years_experience: 0,
    is_published: false,
  });

  const href = (path: string) => `/${locale}${path}`;

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const result = await adminApi.teachers.list({ page, search, ...filters });
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

  const columns: Column<AdminTeacher>[] = [
    {
      key: 'name',
      header: t('admin.a.teacher'),
      sortKey: 'name',
      render: (row) => (
        <div className="flex min-w-0 items-center gap-3">
          <Avatar name={row.full_name ?? ''} src={row.photo_url} size="sm" />
          <div className="min-w-0">
            <Link
              href={href(`/admin/teachers/${row.id}`)}
              className="block truncate font-bold text-ink-900 hover:text-brand-700 hover:underline"
            >
              {row.full_name}
            </Link>
            <p className="truncate text-xs text-ink-500">{row.headline ?? row.email}</p>
          </div>
        </div>
      ),
    },
    {
      key: 'subjects',
      header: t('admin.tea.teaches'),
      hideOnMobile: true,
      render: (row) => (
        <div className="flex flex-wrap gap-1">
          {(row.subjects ?? []).map((subject) => (
            <Badge key={subject} tone="brand">
              {subject}
            </Badge>
          ))}
          {(row.grades ?? []).length > 0 && (
            <Badge tone="neutral">Grades {row.grades.join(', ')}</Badge>
          )}
        </div>
      ),
    },
    {
      key: 'experience',
      header: t('admin.tea.experience'),
      sortKey: 'experience',
      hideOnMobile: true,
      render: (row) => <span className="text-sm">{row.years_experience} years</span>,
    },
    {
      key: 'classes',
      header: 'Classes',
      hideOnMobile: true,
      render: (row) => <span className="tabular-nums">{row.class_count ?? 0}</span>,
    },
    {
      key: 'status',
      header: t('admin.tea.profile'),
      render: (row) => (
        <div className="flex items-center gap-1.5">
          {row.is_published ? (
            <Badge tone="teal">{t('admin.tea.public')}</Badge>
          ) : (
            <Badge tone="neutral">{t('admin.a.hidden')}</Badge>
          )}
          {row.is_featured && (
            <Star className="h-4 w-4 fill-sun-400 text-sun-500" aria-label={t('admin.a.featured')} />
          )}
          {!row.is_active && <Badge tone="coral">{t('admin.tea.disabled')}</Badge>}
        </div>
      ),
    },
    {
      key: 'actions',
      header: '',
      className: 'text-right',
      render: (row) => (
        <button
          type="button"
          aria-label={row.is_published ? `Hide ${row.full_name}` : `Publish ${row.full_name}`}
          onClick={async () => {
            const ok = await run(
              () =>
                row.is_published
                  ? adminApi.teachers.unpublish(row.id)
                  : adminApi.teachers.publish(row.id),
              row.is_published ? 'Profile hidden' : 'Profile published',
            );
            if (ok) await load();
          }}
          className="rounded-lg p-2 text-ink-500 hover:bg-ink-100"
        >
          {row.is_published ? (
            <EyeOff className="h-4 w-4" aria-hidden="true" />
          ) : (
            <Eye className="h-4 w-4" aria-hidden="true" />
          )}
        </button>
      ),
    },
  ];

  if (authLoading || !user) return <AdminShell loading />;

  return (
    <AdminShell
      title={t('admin.tea.title')}
      description={t('admin.tea.subtitle')}
      breadcrumbs={[{ label: t('admin.a.adminCrumb'), href: '/admin' }, { label: t('admin.tea.title') }]}
      actions={
        <Button onClick={() => setCreating(true)}>
          <Plus className="h-4 w-4" aria-hidden="true" />{t('admin.tea.add')}</Button>
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
            key: 'published',
            label: t('admin.tea.publicProfile'),
            options: [
              { value: 'true', label: t('admin.st.published') },
              { value: 'false', label: t('admin.a.hidden') },
            ],
          },
          {
            key: 'active',
            label: t('admin.tea.account'),
            options: [
              { value: 'true', label: t('admin.st.active') },
              { value: 'false', label: t('admin.tea.disabled') },
            ],
          },
          {
            key: 'subject',
            label: t('admin.st.subject'),
            options: [
              { value: 'mathematics', label: t('admin.blk.group.Mathematics') },
              { value: 'physics', label: t('subject.physics.title') },
            ],
          },
        ]}
        filterValues={filters}
        onFilterChange={(key, value) => {
          setFilters((current) => ({ ...current, [key]: value }));
          setPage(1);
        }}
        emptyTitle={t('admin.tea.empty')}
        emptyBody={t('admin.tea.emptyBody')}
        emptyAction={
          <Button onClick={() => setCreating(true)}>
            <Plus className="h-4 w-4" aria-hidden="true" />{t('admin.tea.addOne')}</Button>
        }
      />

      <Modal
        open={creating}
        onClose={() => setCreating(false)}
        title={t('admin.tea.addOne')}
        size="lg"
        footer={
          <>
            <Button variant="ghost" onClick={() => setCreating(false)}>{t('admin.a.cancel')}</Button>
            <Button
              loading={saving}
              onClick={async () => {
                if (!form.full_name.trim() || !form.email.trim()) {
                  notify(t('admin.stu.nameEmailRequired'), 'error');
                  return;
                }
                setSaving(true);
                const result = await run(
                  () =>
                    adminApi.teachers.create({
                      ...form,
                      headline: form.headline || null,
                      bio: form.bio || null,
                    }),
                  t('admin.tea.created'),
                );
                setSaving(false);
                if (result) {
                  setCreating(false);
                  setCreated(result);
                  await load();
                }
              }}
            >{t('admin.tea.create')}</Button>
          </>
        }
      >
        <div className="grid gap-4 sm:grid-cols-2">
          <FormRow label={t('admin.stu.fullName')} required htmlFor="t-name">
            <TextField
              id="t-name"
              value={form.full_name}
              onChange={(event) => setForm({ ...form, full_name: event.target.value })}
              placeholder={t('admin.tea.namePlaceholder')}
            />
          </FormRow>
          <FormRow label={t('admin.a.email')} required htmlFor="t-email">
            <TextField
              id="t-email"
              type="email"
              value={form.email}
              onChange={(event) => setForm({ ...form, email: event.target.value })}
            />
          </FormRow>
          <FormRow label={t('admin.tea.headline')} htmlFor="t-headline" className="sm:col-span-2">
            <TextField
              id="t-headline"
              value={form.headline}
              onChange={(event) => setForm({ ...form, headline: event.target.value })}
              placeholder={t('admin.tea.headlinePlaceholder')}
            />
          </FormRow>
          <FormRow label={t('admin.tea.shortBio')} htmlFor="t-bio" className="sm:col-span-2">
            <TextAreaField
              id="t-bio"
              value={form.bio}
              onChange={(event) => setForm({ ...form, bio: event.target.value })}
            />
          </FormRow>
          <FormRow label={t('admin.tea.subjects')}>
            <StringListField
              values={form.subjects}
              onChange={(subjects) => setForm({ ...form, subjects })}
              placeholder="mathematics"
            />
          </FormRow>
          <FormRow label={t('admin.tea.gradesTaught')} hint={t('admin.tea.gradesHint')}>
            <StringListField
              values={form.grades.map(String)}
              onChange={(grades) =>
                setForm({
                  ...form,
                  grades: grades.map(Number).filter((value) => Number.isFinite(value)),
                })
              }
              placeholder="8"
            />
          </FormRow>
          <FormRow label={t('admin.tea.years')} htmlFor="t-years">
            <TextField
              id="t-years"
              type="number"
              min={0}
              value={form.years_experience}
              onChange={(event) =>
                setForm({ ...form, years_experience: Number(event.target.value) })
              }
            />
          </FormRow>
          <div className="sm:col-span-2">
            <CheckboxField
              label={t('admin.tea.publishNow')}
              hint={t('admin.tea.publishNowHint')}
              checked={form.is_published}
              onChange={(value) => setForm({ ...form, is_published: value })}
            />
          </div>
        </div>
      </Modal>

      <Modal
        open={created !== null}
        onClose={() => setCreated(null)}
        title={t('admin.tea.created')}
        size="sm"
      >
        {created && (
          <div className="space-y-3">
            <p className="text-sm">
              <strong>{created.full_name}</strong> can sign in with {created.email}.
            </p>
            {created.temporary_password && (
              <Alert tone="warning" title={t('admin.a.tempPassword')}>
                <code className="select-all font-mono text-base font-bold">
                  {created.temporary_password}
                </code>
                <p className="mt-1 text-xs">{t('admin.tea.shownOnce')}</p>
              </Alert>
            )}
            <Link href={href(`/admin/teachers/${created.id}`)}>
              <Button className="w-full">{t('admin.tea.completeProfile')}</Button>
            </Link>
          </div>
        )}
      </Modal>
    </AdminShell>
  );
}
