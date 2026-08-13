'use client';

import Link from 'next/link';
import { Bell, CheckCheck, Trash2 } from 'lucide-react';
import { useCallback, useEffect, useState } from 'react';

import { Badge, Button, Card, EmptyState } from '@hietedu/ui';

import { AdminShell } from '@/components/admin/admin-shell';
import { humanise } from '@/components/admin/form';
import { useToast } from '@/components/admin/toast';
import { adminApi, type NotificationRow } from '@/lib/admin-api';
import { useRequireAuth } from '@/lib/auth';
import { useI18n } from '@/lib/i18n';

export default function NotificationsPage() {
  const { t, locale, formatDateTime } = useI18n();
  const { user, loading: authLoading } = useRequireAuth(locale, ['admin']);
  const { run, notify } = useToast();

  const [rows, setRows] = useState<NotificationRow[]>([]);
  const [unread, setUnread] = useState(0);
  const [loading, setLoading] = useState(true);
  const [unreadOnly, setUnreadOnly] = useState(false);
  const [page, setPage] = useState(1);
  const [pages, setPages] = useState(0);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const result = await adminApi.notifications.list({ page, unread_only: unreadOnly });
      setRows(result.items);
      setUnread(result.unread);
      setPages(result.pages);
    } catch (caught) {
      notify((caught as Error).message, 'error');
    } finally {
      setLoading(false);
    }
  }, [page, unreadOnly, notify]);

  useEffect(() => {
    if (user) void load();
  }, [user, load]);

  if (authLoading || !user) return <AdminShell loading />;

  return (
    <AdminShell
      title={t('admin.not.title')}
      description={t('admin.not.subtitle')}
      breadcrumbs={[{ label: t('admin.a.adminCrumb'), href: '/admin' }, { label: t('admin.not.title') }]}
      actions={
        unread > 0 && (
          <Button
            variant="outline"
            onClick={async () => {
              const ok = await run(
                () => adminApi.notifications.markAllRead(),
                t('admin.not.allMarked'),
              );
              if (ok) await load();
            }}
          >
            <CheckCheck className="h-4 w-4" aria-hidden="true" />{t('admin.not.markAllRead')}</Button>
        )
      }
    >
      <div className="mb-4 flex flex-wrap items-center gap-2">
        <Button
          size="sm"
          variant={unreadOnly ? 'outline' : 'primary'}
          onClick={() => {
            setUnreadOnly(false);
            setPage(1);
          }}
        >{t('admin.a.all')}</Button>
        <Button
          size="sm"
          variant={unreadOnly ? 'primary' : 'outline'}
          onClick={() => {
            setUnreadOnly(true);
            setPage(1);
          }}
        >
          Unread ({unread})
        </Button>
      </div>

      <Card className="p-0">
        {loading ? (
          <p className="p-8 text-center text-sm text-ink-500">{t('admin.a.loading')}</p>
        ) : rows.length === 0 ? (
          <EmptyState
            className="border-0"
            icon={<Bell className="h-8 w-8" />}
            title={unreadOnly ? 'Nothing unread' : 'No notifications yet'}
            description={t('admin.not.emptyBody')}
          />
        ) : (
          <ul className="divide-y divide-ink-100">
            {rows.map((row) => (
              <li
                key={row.id}
                className={`flex flex-wrap items-start gap-3 px-4 py-3 ${
                  row.is_read ? '' : 'bg-brand-50/40'
                }`}
              >
                <span
                  className={`mt-1.5 h-2 w-2 shrink-0 rounded-full ${
                    row.is_read ? 'bg-ink-200' : 'bg-coral-500'
                  }`}
                  aria-hidden="true"
                />
                <div className="min-w-0 flex-1">
                  {row.link_url ? (
                    <Link
                      href={`/${locale}${row.link_url}`}
                      onClick={() => void adminApi.notifications.markRead(row.id)}
                      className="font-bold text-ink-900 hover:text-brand-700 hover:underline"
                    >
                      {row.title}
                    </Link>
                  ) : (
                    <p className="font-bold text-ink-900">{row.title}</p>
                  )}
                  {row.body && <p className="mt-0.5 text-sm text-ink-600">{row.body}</p>}
                  <p className="mt-1 text-xs text-ink-400">{formatDateTime(row.created_at)}</p>
                </div>
                <Badge tone="neutral">{humanise(row.kind)}</Badge>
                {!row.is_read && (
                  <button
                    type="button"
                    aria-label={`Mark "${row.title}" as read`}
                    onClick={async () => {
                      const ok = await run(() => adminApi.notifications.markRead(row.id));
                      if (ok) await load();
                    }}
                    className="rounded-lg p-1.5 text-ink-500 hover:bg-ink-100"
                  >
                    <CheckCheck className="h-4 w-4" aria-hidden="true" />
                  </button>
                )}
                <button
                  type="button"
                  aria-label={`Delete "${row.title}"`}
                  onClick={async () => {
                    const ok = await run(() => adminApi.notifications.remove(row.id));
                    if (ok !== undefined) await load();
                  }}
                  className="rounded-lg p-1.5 text-coral-500 hover:bg-coral-50"
                >
                  <Trash2 className="h-4 w-4" aria-hidden="true" />
                </button>
              </li>
            ))}
          </ul>
        )}
      </Card>

      {pages > 1 && (
        <div className="mt-4 flex items-center justify-center gap-3">
          <Button size="sm" variant="outline" disabled={page <= 1} onClick={() => setPage(page - 1)}>{t('admin.a.previous')}</Button>
          <span className="text-xs font-semibold">
            Page {page} of {pages}
          </span>
          <Button
            size="sm"
            variant="outline"
            disabled={page >= pages}
            onClick={() => setPage(page + 1)}
          >{t('admin.a.next')}</Button>
        </div>
      )}
    </AdminShell>
  );
}
