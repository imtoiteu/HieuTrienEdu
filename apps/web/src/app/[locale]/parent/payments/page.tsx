'use client';

import { useEffect, useState } from 'react';

import { formatCurrency } from '@hietedu/localization';
import { Badge, Card, EmptyState, Spinner } from '@hietedu/ui';

import { AppShell } from '@/components/app/app-shell';
import { api } from '@/lib/api';
import { useRequireAuth } from '@/lib/auth';
import { useI18n } from '@/lib/i18n';

interface OrderRow {
  id: number;
  reference: string;
  status: string;
  total: number;
  currency: string;
  placed_at: string | null;
  items: { description: string; line_total: number; quantity: number }[];
  payments: { amount: number; status: string; paid_at: string | null; provider: string }[];
}

export default function ParentPaymentsPage({ params }: { params: Promise<{ locale: string }> }) {
  const { t, locale, formatDate } = useI18n();
  const { user, loading: authLoading } = useRequireAuth(locale, ['parent']);

  const [orders, setOrders] = useState<OrderRow[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!user) return;
    let cancelled = false;
    api.parent
      .payments()
      .then((rows) => !cancelled && setOrders(rows as unknown as OrderRow[]))
      .catch((caught) => !cancelled && setError((caught as Error).message));
    return () => {
      cancelled = true;
    };
  }, [user]);

  if (authLoading || !user) return <AppShell role="parent" loading />;

  return (
    <AppShell role="parent">
      <div className="mx-auto w-full max-w-4xl px-5 py-8 sm:px-8 lg:py-10">
        <h1 className="font-display text-3xl sm:text-4xl">{t('parent.payments')}</h1>

        {!orders && !error && (
          <div className="flex justify-center py-24">
            <Spinner className="h-8 w-8 text-brand-500" />
            <span className="sr-only">{t('common.loading')}</span>
          </div>
        )}

        {error && (
          <Card className="mt-6 border-red-200 bg-red-50">
            <p className="text-sm text-red-700">{error}</p>
          </Card>
        )}

        {orders && orders.length === 0 && (
          <EmptyState
            className="mt-8"
            title={t('common.emptyState')}
            description={t('parent.noOrders')}
          />
        )}

        {orders && orders.length > 0 && (
          <div className="mt-8 space-y-4">
            {orders.map((order) => (
              <Card key={order.id}>
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <p className="font-mono text-sm text-ink-500">{order.reference}</p>
                    <p className="mt-0.5 font-display text-xl">
                      {formatCurrency(order.total, locale)}
                    </p>
                  </div>
                  <Badge
                    tone={
                      order.status === 'paid'
                        ? 'teal'
                        : order.status === 'awaiting_payment'
                          ? 'sun'
                          : 'neutral'
                    }
                  >
                    {order.status.replace(/_/g, ' ')}
                  </Badge>
                </div>

                <ul className="mt-4 space-y-1.5 border-t-2 border-ink-100 pt-3 text-sm">
                  {order.items.map((item, index) => (
                    <li key={index} className="flex justify-between gap-4">
                      <span className="text-ink-700">{item.description}</span>
                      <span className="shrink-0 tabular-nums text-ink-600">
                        {formatCurrency(item.line_total, locale)}
                      </span>
                    </li>
                  ))}
                </ul>

                {order.payments.length > 0 && (
                  <ul className="mt-3 space-y-1 text-xs text-ink-500">
                    {order.payments.map((payment, index) => (
                      <li key={index}>
                        {payment.status} · {payment.provider}
                        {payment.paid_at ? ` · ${formatDate(payment.paid_at)}` : ''}
                      </li>
                    ))}
                  </ul>
                )}

                {order.status === 'awaiting_payment' && (
                  <p className="mt-4 rounded-2xl bg-sun-50 p-3 text-sm text-ink-700">
                    {t('parent.payments.transferHint', { reference: order.reference })}
                  </p>
                )}
              </Card>
            ))}
          </div>
        )}
      </div>
    </AppShell>
  );
}
