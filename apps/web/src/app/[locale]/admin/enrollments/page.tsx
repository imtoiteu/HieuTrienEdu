'use client';

import Link from 'next/link';
import { useSearchParams } from 'next/navigation';
import { Check, Plus, Wallet, X } from 'lucide-react';
import { useCallback, useEffect, useState } from 'react';

import { Badge, Button } from '@hietedu/ui';

import { AdminShell } from '@/components/admin/admin-shell';
import { DataTable, type Column } from '@/components/admin/data-table';
import { ConfirmDialog, Modal } from '@/components/admin/dialog';
import { FormRow, SelectField, StatusBadge, TextAreaField, humanise } from '@/components/admin/form';
import { useToast } from '@/components/admin/toast';
import { adminApi, type AdminClass, type AdminEnrollment, type AdminStudent } from '@/lib/admin-api';
import { useRequireAuth } from '@/lib/auth';
import { useI18n } from '@/lib/i18n';

export default function EnrollmentsPage() {
  const { t, locale, formatDate } = useI18n();
  const { user, loading: authLoading } = useRequireAuth(locale, ['admin']);
  const { run, notify } = useToast();
  const params = useSearchParams();

  const [rows, setRows] = useState<AdminEnrollment[]>([]);
  const [meta, setMeta] = useState({ total: 0, page: 1, page_size: 25, pages: 0 });
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState('');
  const [filters, setFilters] = useState<Record<string, string>>({});
  const [rejecting, setRejecting] = useState<AdminEnrollment | null>(null);
  const [creating, setCreating] = useState(false);
  const [students, setStudents] = useState<AdminStudent[]>([]);
  const [classes, setClasses] = useState<AdminClass[]>([]);
  const [form, setForm] = useState({
    student_id: 0,
    class_group_id: 0,
    status: 'confirmed',
    notes: '',
  });

  const href = (path: string) => `/${locale}${path}`;

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const result = await adminApi.enrollments.list({ page, search, ...filters });
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
    adminApi.students.list({ page_size: 200 }).then((p) => setStudents(p.items)).catch(() => undefined);
    adminApi.classes.list({ page_size: 100 }).then((p) => setClasses(p.items)).catch(() => undefined);
  }, [user]);

  useEffect(() => {
    const status = params.get('status');
    if (status) setFilters((current) => ({ ...current, status }));
  }, [params]);

  const columns: Column<AdminEnrollment>[] = [
    {
      key: 'student',
      header: t('admin.a.student'),
      render: (row) => (
        <div className="min-w-0">
          <Link
            href={href(`/admin/students/${row.student_id}`)}
            className="block truncate font-bold text-ink-900 hover:text-brand-700 hover:underline"
          >
            {row.student_name ?? `Student #${row.student_id}`}
          </Link>
          <p className="truncate text-xs text-ink-500">{row.student_email}</p>
        </div>
      ),
    },
    {
      key: 'class',
      header: t('admin.a.class'),
      render: (row) => (
        <div className="min-w-0">
          <Link
            href={href(`/admin/classes/${row.class_group_id}`)}
            className="block truncate font-semibold text-ink-800 hover:underline"
          >
            {row.class_name}
          </Link>
          <p className="truncate text-xs text-ink-500">
            {humanise(row.format ?? '')} · {row.teacher_name ?? 'No teacher'}
          </p>
        </div>
      ),
    },
    {
      key: 'schedule',
      header: t('admin.enr.requested'),
      hideOnMobile: true,
      render: (row) => (
        <span className="text-xs text-ink-600">
          {row.preferred_schedule || row.requested_format || '—'}
        </span>
      ),
    },
    {
      key: 'status',
      header: t('admin.a.status'),
      sortKey: 'status',
      render: (row) => <StatusBadge value={row.status} kind="enrollment" />,
    },
    {
      key: 'payment',
      header: t('admin.enr.payment'),
      sortKey: 'payment',
      render: (row) => <StatusBadge value={row.payment_status} kind="payment" />,
    },
    {
      key: 'created',
      header: t('admin.enr.requestedOn'),
      sortKey: 'created_at',
      hideOnMobile: true,
      render: (row) => <span className="text-xs text-ink-500">{formatDate(row.created_at)}</span>,
    },
    {
      key: 'actions',
      header: '',
      className: 'text-right',
      render: (row) => (
        <div className="flex flex-wrap justify-end gap-1">
          {row.status === 'pending' && (
            <Button
              size="sm"
              onClick={async () => {
                const ok = await run(
                  () => adminApi.enrollments.approve(row.id),
                  t('admin.enr.approved'),
                );
                if (ok) await load();
              }}
            >
              <Check className="h-4 w-4" aria-hidden="true" />{t('admin.a.approve')}</Button>
          )}
          {row.status === 'confirmed' && (
            <Button
              size="sm"
              variant="outline"
              onClick={async () => {
                const ok = await run(
                  () => adminApi.enrollments.activate(row.id),
                  t('admin.enr.activated'),
                );
                if (ok) await load();
              }}
            >{t('admin.a.activate')}</Button>
          )}
          {row.payment_status !== 'paid' && (
            <button
              type="button"
              aria-label={t('admin.enr.markPaid')}
              onClick={async () => {
                const ok = await run(
                  () => adminApi.enrollments.markPaid(row.id),
                  t('admin.enr.markedPaid'),
                );
                if (ok) await load();
              }}
              className="rounded-lg p-2 text-teal-600 hover:bg-teal-50"
            >
              <Wallet className="h-4 w-4" aria-hidden="true" />
            </button>
          )}
          {row.status !== 'cancelled' && row.status !== 'completed' && (
            <button
              type="button"
              aria-label={t('admin.enr.reject')}
              onClick={() => setRejecting(row)}
              className="rounded-lg p-2 text-coral-600 hover:bg-coral-50"
            >
              <X className="h-4 w-4" aria-hidden="true" />
            </button>
          )}
        </div>
      ),
    },
  ];

  if (authLoading || !user) return <AdminShell loading />;

  return (
    <AdminShell
      title={t('admin.enr.title')}
      description={t('admin.enr.subtitle')}
      breadcrumbs={[{ label: t('admin.a.adminCrumb'), href: '/admin' }, { label: t('admin.enr.title') }]}
      actions={
        <Button onClick={() => setCreating(true)}>
          <Plus className="h-4 w-4" aria-hidden="true" />{t('admin.enr.add')}</Button>
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
            key: 'status',
            label: t('admin.a.status'),
            options: ['pending', 'confirmed', 'active', 'completed', 'cancelled'].map((s) => ({
              value: s,
              label: humanise(s),
            })),
          },
          {
            key: 'payment_status',
            label: t('admin.enr.payment'),
            options: ['unpaid', 'partial', 'paid', 'refunded', 'waived'].map((s) => ({
              value: s,
              label: humanise(s),
            })),
          },
          {
            key: 'class_group_id',
            label: t('admin.cls.class'),
            options: classes.map((c) => ({ value: String(c.id), label: c.name })),
          },
        ]}
        filterValues={filters}
        onFilterChange={(key, value) => {
          setFilters((current) => ({ ...current, [key]: value }));
          setPage(1);
        }}
        emptyTitle={t('admin.enr.empty')}
        emptyBody={t('admin.enr.emptyBody')}
      />

      <Modal
        open={creating}
        onClose={() => setCreating(false)}
        title={t('admin.enr.add')}
        footer={
          <>
            <Button variant="ghost" onClick={() => setCreating(false)}>{t('admin.a.cancel')}</Button>
            <Button
              onClick={async () => {
                if (!form.student_id || !form.class_group_id) {
                  notify(t('admin.enr.chooseBoth'), 'error');
                  return;
                }
                const ok = await run(
                  () =>
                    adminApi.enrollments.create({
                      ...form,
                      notes: form.notes || null,
                    }),
                  t('admin.enr.enrolled'),
                );
                if (ok) {
                  setCreating(false);
                  await load();
                }
              }}
            >{t('admin.enr.enrol')}</Button>
          </>
        }
      >
        <div className="space-y-4">
          <FormRow label={t('admin.a.student')} required htmlFor="en-student">
            <SelectField
              id="en-student"
              value={form.student_id}
              onChange={(e) => setForm({ ...form, student_id: Number(e.target.value) })}
            >
              <option value={0}>{t('admin.enr.chooseStudent')}</option>
              {students.map((student) => (
                <option key={student.id} value={student.id}>
                  {student.full_name} (Grade {student.grade})
                </option>
              ))}
            </SelectField>
          </FormRow>
          <FormRow label={t('admin.a.class')} required htmlFor="en-class">
            <SelectField
              id="en-class"
              value={form.class_group_id}
              onChange={(e) => setForm({ ...form, class_group_id: Number(e.target.value) })}
            >
              <option value={0}>{t('admin.enr.chooseClass')}</option>
              {classes.map((group) => (
                <option key={group.id} value={group.id} disabled={group.seats_available === 0}>
                  {group.name} —{' '}
                  {group.seats_available === 0
                    ? 'full'
                    : `${group.seats_available} place(s) left`}
                </option>
              ))}
            </SelectField>
          </FormRow>
          <FormRow label={t('admin.a.status')} htmlFor="en-status">
            <SelectField
              id="en-status"
              value={form.status}
              onChange={(e) => setForm({ ...form, status: e.target.value })}
            >
              <option value="pending">{t('admin.st.pending')}</option>
              <option value="confirmed">{t('admin.st.confirmed')}</option>
              <option value="active">{t('admin.st.active')}</option>
            </SelectField>
          </FormRow>
          <FormRow label={t('admin.a.notes')} htmlFor="en-notes">
            <TextAreaField
              id="en-notes"
              value={form.notes}
              onChange={(e) => setForm({ ...form, notes: e.target.value })}
            />
          </FormRow>
        </div>
      </Modal>

      <ConfirmDialog
        open={rejecting !== null}
        onClose={() => setRejecting(null)}
        title={t('admin.enr.cancelQ')}
        confirmLabel={t('admin.enr.cancelLabel')}
        message={
          <>
            <strong>{rejecting?.student_name}</strong> will lose their place in{' '}
            <strong>{rejecting?.class_name}</strong>. The record is kept, so this can be reversed.
          </>
        }
        onConfirm={async () => {
          if (!rejecting) return;
          const ok = await run(
            () => adminApi.enrollments.reject(rejecting.id),
            t('admin.enr.cancelled'),
          );
          if (ok) await load();
        }}
      />
    </AdminShell>
  );
}
