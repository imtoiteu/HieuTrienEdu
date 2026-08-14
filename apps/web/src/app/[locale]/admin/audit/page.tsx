'use client';

import { useCallback, useEffect, useState } from 'react';

import { Badge } from '@hietedu/ui';

import { AdminShell } from '@/components/admin/admin-shell';
import { DataTable, type Column } from '@/components/admin/data-table';
import { useEnumLabel } from '@/components/admin/form';
import { useToast } from '@/components/admin/toast';
import { adminApi, type AuditRow } from '@/lib/admin-api';
import { useRequireAuth } from '@/lib/auth';
import { useI18n } from '@/lib/i18n';

const ACTION_TONES: Record<string, 'brand' | 'coral' | 'teal' | 'sun' | 'neutral'> = {
  create: 'teal',
  update: 'brand',
  delete: 'coral',
  publish: 'teal',
  unpublish: 'sun',
  archive: 'neutral',
  reset_password: 'coral',
  convert: 'brand',
};

export default function AuditPage() {
  const { t, locale, formatDateTime } = useI18n();
  const enumLabel = useEnumLabel();
  const { user, loading: authLoading } = useRequireAuth(locale, ['admin']);
  const { notify } = useToast();

  const [rows, setRows] = useState<AuditRow[]>([]);
  const [meta, setMeta] = useState({ total: 0, page: 1, page_size: 50, pages: 0 });
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState('');
  const [filters, setFilters] = useState<Record<string, string>>({});

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const result = await adminApi.audit.list({ page, search, ...filters });
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

  const columns: Column<AuditRow>[] = [
    {
      key: 'action',
      header: t('admin.aud.action'),
      render: (row) => (
        <Badge tone={ACTION_TONES[row.action] ?? 'neutral'}>{enumLabel(row.action)}</Badge>
      ),
    },
    {
      key: 'summary',
      header: t('admin.aud.what'),
      render: (row) => (
        <div className="min-w-0">
          <p className="truncate text-sm text-ink-800">{row.summary}</p>
          {Object.keys(row.changes ?? {}).length > 0 && (
            <details className="mt-0.5">
              <summary className="cursor-pointer text-xs text-brand-600">{t('admin.a.details')}</summary>
              <pre className="mt-1 max-h-40 overflow-auto rounded-lg bg-ink-50 p-2 text-[0.7rem]">
                {JSON.stringify(row.changes, null, 2)}
              </pre>
            </details>
          )}
        </div>
      ),
    },
    {
      key: 'entity',
      header: t('admin.aud.record'),
      hideOnMobile: true,
      render: (row) => (
        <span className="text-xs text-ink-500">
          {enumLabel(row.entity_type)}
          {row.entity_id ? ` #${row.entity_id}` : ''}
        </span>
      ),
    },
    {
      key: 'actor',
      header: t('admin.aud.by'),
      render: (row) => <span className="text-xs text-ink-600">{row.actor_email ?? t('admin.aud.system')}</span>,
    },
    {
      key: 'when',
      header: t('admin.aud.when'),
      render: (row) => (
        <span className="whitespace-nowrap text-xs text-ink-500">
          {formatDateTime(row.created_at)}
        </span>
      ),
    },
  ];

  if (authLoading || !user) return <AdminShell loading />;

  return (
    <AdminShell
      title={t('admin.aud.title')}
      description={t('admin.aud.subtitle')}
      breadcrumbs={[{ label: t('admin.a.adminCrumb'), href: '/admin' }, { label: t('admin.aud.title') }]}
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
            key: 'action',
            label: t('admin.aud.action'),
            options: [
              'create',
              'update',
              'delete',
              'publish',
              'unpublish',
              'archive',
              'convert',
              'reset_password',
            ].map((action) => ({ value: action, label: enumLabel(action) })),
          },
          {
            key: 'entity_type',
            label: t('admin.aud.recordType'),
            options: [
              'course',
              'lesson',
              'question',
              'student',
              'teacher',
              'class',
              'enrollment',
              'category',
              'site_section',
              'media',
            ].map((type) => ({ value: type, label: enumLabel(type) })),
          },
        ]}
        filterValues={filters}
        onFilterChange={(key, value) => {
          setFilters((current) => ({ ...current, [key]: value }));
          setPage(1);
        }}
        emptyTitle={t('admin.aud.empty')}
        emptyBody={t('admin.aud.emptyBody')}
      />
    </AdminShell>
  );
}
