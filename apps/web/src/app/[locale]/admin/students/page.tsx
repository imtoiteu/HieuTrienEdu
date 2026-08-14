'use client';

import Link from 'next/link';
import { KeyRound, Plus, UserX } from 'lucide-react';
import { useCallback, useEffect, useState } from 'react';

import { Alert, Badge, Button } from '@hietedu/ui';

import { AdminShell } from '@/components/admin/admin-shell';
import { DataTable, type Column } from '@/components/admin/data-table';
import { Modal } from '@/components/admin/dialog';
import { FormRow, SelectField, TextField } from '@/components/admin/form';
import { useToast } from '@/components/admin/toast';
import { adminApi, type AdminStudent } from '@/lib/admin-api';
import { useRequireAuth } from '@/lib/auth';
import { useI18n } from '@/lib/i18n';

export default function StudentsPage() {
  const { t, locale, formatDate } = useI18n();
  const { user, loading: authLoading } = useRequireAuth(locale, ['admin']);
  const { run, notify } = useToast();

  const [rows, setRows] = useState<AdminStudent[]>([]);
  const [meta, setMeta] = useState({ total: 0, page: 1, page_size: 25, pages: 0 });
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState('');
  const [sort, setSort] = useState('created_at');
  const [order, setOrder] = useState<'asc' | 'desc'>('desc');
  const [filters, setFilters] = useState<Record<string, string>>({});
  const [creating, setCreating] = useState(false);
  const [saving, setSaving] = useState(false);
  const [created, setCreated] = useState<AdminStudent | null>(null);
  const [form, setForm] = useState({ full_name: '', email: '', grade: 6, phone: '', school: '' });

  const href = (path: string) => `/${locale}${path}`;

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const result = await adminApi.students.list({ page, search, sort, order, ...filters });
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

  const columns: Column<AdminStudent>[] = [
    {
      key: 'name',
      header: t('admin.a.student'),
      sortKey: 'name',
      render: (row) => (
        <div className="min-w-0">
          <Link
            href={href(`/admin/students/${row.id}`)}
            className="block truncate font-bold text-ink-900 hover:text-brand-700 hover:underline"
          >
            {row.full_name}
          </Link>
          <p className="truncate text-xs text-ink-500">{row.email}</p>
        </div>
      ),
    },
    {
      key: 'grade',
      header: t('admin.a.grade'),
      sortKey: 'grade',
      render: (row) => <Badge tone="neutral">{t('admin.a.gradeN', { n: row.grade })}</Badge>,
    },
    {
      key: 'school',
      header: t('admin.stu.school'),
      hideOnMobile: true,
      render: (row) => <span className="text-sm text-ink-600">{row.school ?? '—'}</span>,
    },
    {
      key: 'progress',
      header: t('admin.stu.progress'),
      sortKey: 'xp',
      hideOnMobile: true,
      render: (row) => (
        <span className="text-xs text-ink-600">
          {t('admin.stu.progressValue', {
            level: row.level,
            xp: row.xp_total,
            streak: row.streak_days,
          })}
        </span>
      ),
    },
    {
      key: 'active',
      header: t('admin.stu.account'),
      render: (row) =>
        row.is_active ? <Badge tone="teal">{t('admin.st.active')}</Badge> : <Badge tone="coral">{t('admin.stu.disabled')}</Badge>,
    },
    {
      key: 'joined',
      header: t('admin.stu.joined'),
      sortKey: 'created_at',
      hideOnMobile: true,
      render: (row) => <span className="text-xs text-ink-500">{formatDate(row.created_at)}</span>,
    },
    {
      key: 'actions',
      header: '',
      className: 'text-right',
      render: (row) => (
        <div className="flex justify-end gap-1">
          <button
            type="button"
            aria-label={t('admin.stu.resetAria', { name: row.full_name ?? '' })}
            onClick={async () => {
              const result = await run(() => adminApi.students.resetPassword(row.id));
              if (result?.temporary_password) {
                notify(
                  t('admin.stu.tempPasswordToast', { password: result.temporary_password }),
                  'info',
                  t('admin.stu.copyNow'),
                );
              }
            }}
            className="rounded-lg p-2 text-ink-500 hover:bg-ink-100"
          >
            <KeyRound className="h-4 w-4" aria-hidden="true" />
          </button>
          <button
            type="button"
            aria-label={`${row.is_active ? 'Deactivate' : 'Activate'} ${row.full_name}`}
            onClick={async () => {
              const ok = await run(
                () => adminApi.students.setActive(row.id, !row.is_active),
                row.is_active ? t('admin.stu.accountDisabled') : t('admin.stu.accountEnabled'),
              );
              if (ok) await load();
            }}
            className="rounded-lg p-2 text-ink-500 hover:bg-ink-100"
          >
            <UserX className="h-4 w-4" aria-hidden="true" />
          </button>
        </div>
      ),
    },
  ];

  if (authLoading || !user) return <AdminShell loading />;

  return (
    <AdminShell
      title={t('admin.stu.title')}
      description={t('admin.stu.subtitle')}
      breadcrumbs={[{ label: t('admin.a.adminCrumb'), href: '/admin' }, { label: t('admin.tea.students') }]}
      actions={
        <Button onClick={() => setCreating(true)}>
          <Plus className="h-4 w-4" aria-hidden="true" />{t('admin.stu.add')}</Button>
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
            key: 'grade',
            label: t('admin.a.grade'),
            options: Array.from({ length: 12 }, (_, index) => ({
              value: String(index + 1),
              label: t('admin.a.gradeN', { n: index + 1 }),
            })),
          },
          {
            key: 'active',
            label: t('admin.tea.account'),
            options: [
              { value: 'true', label: t('admin.st.active') },
              { value: 'false', label: t('admin.tea.disabled') },
            ],
          },
        ]}
        filterValues={filters}
        onFilterChange={(key, value) => {
          setFilters((current) => ({ ...current, [key]: value }));
          setPage(1);
        }}
        emptyTitle={t('admin.stu.empty')}
        emptyBody={t('admin.stu.emptyBody')}
      />

      <Modal
        open={creating}
        onClose={() => setCreating(false)}
        title={t('admin.stu.addAStudent')}
        description={t('admin.stu.addHint')}
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
                    adminApi.students.create({
                      ...form,
                      phone: form.phone || null,
                      school: form.school || null,
                    }),
                  t('admin.stu.created'),
                );
                setSaving(false);
                if (result) {
                  setCreating(false);
                  setCreated(result);
                  setForm({ full_name: '', email: '', grade: 6, phone: '', school: '' });
                  await load();
                }
              }}
            >{t('admin.stu.create')}</Button>
          </>
        }
      >
        <div className="grid gap-4 sm:grid-cols-2">
          <FormRow label={t('admin.stu.fullName')} required htmlFor="s-name" className="sm:col-span-2">
            <TextField
              id="s-name"
              value={form.full_name}
              onChange={(event) => setForm({ ...form, full_name: event.target.value })}
            />
          </FormRow>
          <FormRow label={t('admin.a.email')} required htmlFor="s-email" className="sm:col-span-2">
            <TextField
              id="s-email"
              type="email"
              value={form.email}
              onChange={(event) => setForm({ ...form, email: event.target.value })}
            />
          </FormRow>
          <FormRow label={t('admin.a.grade')} htmlFor="s-grade">
            <SelectField
              id="s-grade"
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
          <FormRow label={t('admin.a.phone')} htmlFor="s-phone">
            <TextField
              id="s-phone"
              value={form.phone}
              onChange={(event) => setForm({ ...form, phone: event.target.value })}
            />
          </FormRow>
          <FormRow label={t('admin.stu.school')} htmlFor="s-school" className="sm:col-span-2">
            <TextField
              id="s-school"
              value={form.school}
              onChange={(event) => setForm({ ...form, school: event.target.value })}
            />
          </FormRow>
        </div>
      </Modal>

      <Modal
        open={created !== null}
        onClose={() => setCreated(null)}
        title={t('admin.stu.created')}
        size="sm"
      >
        {created && (
          <div className="space-y-3">
            <p className="text-sm">
              {t('admin.stu.canSignIn', {
                name: created.full_name ?? '',
                email: created.email ?? '',
              })}
            </p>
            {created.temporary_password && (
              <Alert tone="warning" title={t('admin.a.tempPassword')}>
                <code className="select-all font-mono text-base font-bold">
                  {created.temporary_password}
                </code>
                <p className="mt-1 text-xs">{t('admin.a.tempPasswordHint')}</p>
              </Alert>
            )}
            <Link href={href(`/admin/students/${created.id}`)}>
              <Button className="w-full">{t('admin.stu.openProfile')}</Button>
            </Link>
          </div>
        )}
      </Modal>
    </AdminShell>
  );
}
