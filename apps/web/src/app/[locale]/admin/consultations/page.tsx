'use client';

import Link from 'next/link';
import { useSearchParams } from 'next/navigation';
import { Phone } from 'lucide-react';
import { useCallback, useEffect, useState } from 'react';

import { Badge, Card } from '@hietedu/ui';

import { AdminShell } from '@/components/admin/admin-shell';
import { DataTable, type Column } from '@/components/admin/data-table';
import { StatusBadge, useEnumLabel } from '@/components/admin/form';
import { useToast } from '@/components/admin/toast';
import { adminApi, type LeadRow, type StaffMember } from '@/lib/admin-api';
import { useRequireAuth } from '@/lib/auth';
import { useI18n } from '@/lib/i18n';

const STATUSES = [
  'new',
  'contacted',
  'consulting',
  'interested',
  'enrolled',
  'completed',
  'rejected',
  'no_response',
];

export default function ConsultationsPage() {
  const { t, locale, formatDate } = useI18n();
  const enumLabel = useEnumLabel();
  const { user, loading: authLoading } = useRequireAuth(locale, ['admin']);
  const { notify } = useToast();
  const params = useSearchParams();

  const [rows, setRows] = useState<LeadRow[]>([]);
  const [meta, setMeta] = useState({ total: 0, page: 1, page_size: 25, pages: 0 });
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState('');
  const [sort, setSort] = useState('created_at');
  const [order, setOrder] = useState<'asc' | 'desc'>('desc');
  const [filters, setFilters] = useState<Record<string, string>>({});
  const [stats, setStats] = useState<{ by_status: Record<string, number>; open: number } | null>(
    null,
  );
  const [staff, setStaff] = useState<StaffMember[]>([]);

  const href = (path: string) => `/${locale}${path}`;

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [result, statResult] = await Promise.all([
        adminApi.leads.list({ page, search, sort, order, ...filters }),
        adminApi.leads.stats(),
      ]);
      setRows(result.items);
      setMeta({
        total: result.total,
        page: result.page,
        page_size: result.page_size,
        pages: result.pages,
      });
      setStats(statResult);
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
    if (user) adminApi.staff().then(setStaff).catch(() => undefined);
  }, [user]);

  useEffect(() => {
    const status = params.get('status');
    if (status) setFilters((current) => ({ ...current, status }));
  }, [params]);

  const columns: Column<LeadRow & { id: number }>[] = [
    {
      key: 'name',
      header: t('admin.con.contact'),
      sortKey: 'name',
      render: (row) => (
        <div className="min-w-0">
          <Link
            href={href(`/admin/consultations/${row.source}/${row.id}`)}
            className="block truncate font-bold text-ink-900 hover:text-brand-700 hover:underline"
          >
            {row.name}
          </Link>
          <p className="truncate text-xs text-ink-500">{row.email}</p>
        </div>
      ),
    },
    {
      key: 'phone',
      header: t('admin.a.phone'),
      hideOnMobile: true,
      render: (row) =>
        row.phone ? (
          <a
            href={`tel:${row.phone}`}
            className="inline-flex items-center gap-1 text-sm font-semibold text-brand-600 hover:underline"
          >
            <Phone className="h-3.5 w-3.5" aria-hidden="true" />
            {row.phone}
          </a>
        ) : (
          <span className="text-xs text-ink-400">—</span>
        ),
    },
    {
      key: 'interest',
      header: t('admin.con.interestedIn'),
      hideOnMobile: true,
      render: (row) => (
        <div className="min-w-0">
          <Badge tone="neutral">{enumLabel(row.interest)}</Badge>
          {row.grade && (
            <span className="ml-1 text-xs text-ink-500">
              {t('admin.a.gradeN', { n: row.grade })}
            </span>
          )}
        </div>
      ),
    },
    {
      key: 'source',
      header: t('admin.con.form'),
      render: (row) => (
        <Badge tone={row.source === 'tutoring' ? 'brand' : 'neutral'}>
          {row.source === 'tutoring' ? 'Tutoring request' : 'Contact form'}
        </Badge>
      ),
    },
    {
      key: 'assigned',
      header: t('admin.con.assignedTo'),
      hideOnMobile: true,
      render: (row) =>
        row.assigned_to_name ? (
          <span className="text-sm">{row.assigned_to_name}</span>
        ) : (
          <span className="text-xs font-semibold text-coral-600">{t('admin.con.unassigned')}</span>
        ),
    },
    {
      key: 'status',
      header: t('admin.a.status'),
      sortKey: 'status',
      render: (row) => <StatusBadge value={row.status} kind="lead" />,
    },
    {
      key: 'created',
      header: t('admin.con.received'),
      sortKey: 'created_at',
      render: (row) => <span className="text-xs text-ink-500">{formatDate(row.created_at)}</span>,
    },
  ];

  if (authLoading || !user) return <AdminShell loading />;

  return (
    <AdminShell
      title={t('admin.con.title')}
      description={t('admin.con.subtitle')}
      breadcrumbs={[{ label: t('admin.a.adminCrumb'), href: '/admin' }, { label: t('admin.con.title') }]}
    >
      {stats && (
        <Card className="mb-4 flex flex-wrap gap-2 p-3">
          <button
            type="button"
            onClick={() => setFilters((current) => ({ ...current, status: '' }))}
            className={`rounded-full border-2 px-3 py-1 text-xs font-bold ${
              !filters.status ? 'border-brand-500 bg-brand-500 text-white' : 'border-ink-200'
            }`}
          >
            All ({stats.by_status ? Object.values(stats.by_status).reduce((a, b) => a + b, 0) : 0})
          </button>
          {STATUSES.map((status) => {
            const count = stats.by_status?.[status] ?? 0;
            if (count === 0 && filters.status !== status) return null;
            return (
              <button
                key={status}
                type="button"
                onClick={() => setFilters((current) => ({ ...current, status }))}
                className={`rounded-full border-2 px-3 py-1 text-xs font-bold ${
                  filters.status === status
                    ? 'border-brand-500 bg-brand-500 text-white'
                    : 'border-ink-200'
                }`}
              >
                {enumLabel(status)} ({count})
              </button>
            );
          })}
        </Card>
      )}

      <DataTable
        columns={columns}
        rows={rows as (LeadRow & { id: number })[]}
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
            options: STATUSES.map((status) => ({ value: status, label: enumLabel(status) })),
          },
          {
            key: 'source',
            label: t('admin.con.form'),
            options: [
              { value: 'contact', label: t('admin.con.contactForm') },
              { value: 'tutoring', label: t('admin.con.tutoringRequest') },
            ],
          },
          {
            key: 'assigned_to_id',
            label: t('admin.con.assignedTo'),
            options: staff.map((member) => ({
              value: String(member.id),
              label: member.full_name,
            })),
          },
          {
            key: 'grade',
            label: t('admin.a.grade'),
            options: Array.from({ length: 12 }, (_, index) => ({
              value: String(index + 1),
              label: t('admin.a.gradeN', { n: index + 1 }),
            })),
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
        emptyTitle={t('admin.con.empty')}
        emptyBody={t('admin.con.emptyBody')}
      />
    </AdminShell>
  );
}
