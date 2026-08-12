'use client';

import { BookOpen, ClipboardList, GraduationCap, Mail, Users, Wallet } from 'lucide-react';
import { useCallback, useEffect, useState } from 'react';

import { formatCurrency } from '@hietedu/localization';
import { Alert, Badge, Button, Card, EmptyState, Spinner } from '@hietedu/ui';

import { AppShell } from '@/components/app/app-shell';
import { api } from '@/lib/api';
import { useRequireAuth } from '@/lib/auth';
import { useI18n } from '@/lib/i18n';

interface Overview {
  students: number;
  parents: number;
  teachers: number;
  classes: number;
  active_enrollments: number;
  questions: number;
  published_questions: number;
  pending_review_questions: number;
  courses: number;
  new_leads: number;
  new_tutoring_requests: number;
  orders_awaiting_payment: number;
  revenue_vnd: number;
}

interface OrderRow {
  id: number;
  reference: string;
  status: string;
  total: number;
  currency: string;
  customer: string | null;
  customer_email: string | null;
  placed_at: string | null;
  items: { description: string; line_total: number }[];
}

export default function AdminPage({ params }: { params: Promise<{ locale: string }> }) {
  const { t, locale, formatDate } = useI18n();
  const { user, loading: authLoading } = useRequireAuth(locale, ['admin']);

  const [overview, setOverview] = useState<Overview | null>(null);
  const [orders, setOrders] = useState<OrderRow[] | null>(null);
  const [leads, setLeads] = useState<Record<string, unknown>[] | null>(null);
  const [requests, setRequests] = useState<Record<string, unknown>[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busyOrder, setBusyOrder] = useState<number | null>(null);

  const load = useCallback(async () => {
    const [overviewResult, orderRows, leadRows, requestRows] = await Promise.all([
      api.admin.overview(),
      api.admin.orders(),
      api.admin.leads(),
      api.admin.tutoringRequests(),
    ]);
    setOverview(overviewResult as unknown as Overview);
    setOrders(orderRows as unknown as OrderRow[]);
    setLeads(leadRows);
    setRequests(requestRows);
  }, []);

  useEffect(() => {
    if (!user) return;
    load().catch((caught) => setError((caught as Error).message));
  }, [user, load]);

  async function markPaid(orderId: number) {
    setBusyOrder(orderId);
    try {
      await api.admin.markPaid(orderId);
      await load();
    } catch (caught) {
      setError((caught as Error).message);
    } finally {
      setBusyOrder(null);
    }
  }

  if (authLoading || !user) return <AppShell role="admin" loading />;

  return (
    <AppShell role="admin">
      <div className="mx-auto w-full max-w-6xl px-5 py-8 sm:px-8 lg:py-10">
        <h1 className="font-display text-3xl sm:text-4xl">{t('admin.title')}</h1>

        {error && (
          <Alert tone="error" className="mt-5">
            {error}
          </Alert>
        )}

        {!overview && !error && (
          <div className="flex justify-center py-24">
            <Spinner className="h-8 w-8 text-brand-500" />
            <span className="sr-only">{t('common.loading')}</span>
          </div>
        )}

        {overview && (
          <>
            <dl className="mt-8 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
              {[
                { icon: Users, label: t('teacher.students'), value: overview.students },
                { icon: GraduationCap, label: t('nav.teachers'), value: overview.teachers },
                { icon: BookOpen, label: t('nav.courses'), value: overview.courses },
                {
                  icon: ClipboardList,
                  label: t('teacher.questionBank'),
                  value: overview.published_questions,
                },
                { icon: Users, label: t('parent.title'), value: overview.parents },
                { icon: Mail, label: t('admin.leads'), value: overview.new_leads },
                {
                  icon: ClipboardList,
                  label: t('nav.oneToOne'),
                  value: overview.new_tutoring_requests,
                },
                {
                  icon: Wallet,
                  label: t('admin.revenue'),
                  value: formatCurrency(overview.revenue_vnd, locale),
                },
              ].map((stat) => (
                <Card key={stat.label} className="flex items-center gap-4">
                  <span className="inline-flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl bg-brand-100 text-brand-700">
                    <stat.icon className="h-5 w-5" aria-hidden="true" />
                  </span>
                  <div className="min-w-0">
                    <dt className="truncate text-xs font-semibold text-ink-500">{stat.label}</dt>
                    <dd className="truncate font-display text-xl">{stat.value}</dd>
                  </div>
                </Card>
              ))}
            </dl>

            {overview.pending_review_questions > 0 && (
              <Alert tone="warning" className="mt-6" title={t('admin.pendingReview')}>
                {overview.pending_review_questions} questions are awaiting teacher review before
                students can be served them.
              </Alert>
            )}
          </>
        )}

        {/* orders */}
        {orders && (
          <section className="mt-10">
            <h2 className="font-display text-2xl">{t('admin.orders')}</h2>
            {orders.length === 0 ? (
              <EmptyState className="mt-5" title={t('common.emptyState')} />
            ) : (
              <Card className="mt-5 p-0">
                <div className="scroll-x">
                  <table className="w-full min-w-[46rem] text-left text-sm">
                    <thead className="bg-ink-50">
                      <tr>
                        {['Reference', 'Customer', 'Items', 'Total', 'Status', ''].map(
                          (heading, index) => (
                            <th key={index} scope="col" className="px-4 py-3 font-display">
                              {heading}
                            </th>
                          ),
                        )}
                      </tr>
                    </thead>
                    <tbody>
                      {orders.map((order) => (
                        <tr key={order.id} className="border-t border-ink-100">
                          <td className="px-4 py-3 font-mono text-xs">{order.reference}</td>
                          <td className="px-4 py-3">
                            <span className="block font-semibold text-ink-900">
                              {order.customer ?? '—'}
                            </span>
                            <span className="block text-xs text-ink-500">
                              {order.customer_email}
                            </span>
                          </td>
                          <td className="max-w-xs px-4 py-3 text-xs text-ink-600">
                            {order.items.map((item) => item.description).join(', ')}
                          </td>
                          <td className="px-4 py-3 font-bold tabular-nums">
                            {formatCurrency(order.total, locale)}
                          </td>
                          <td className="px-4 py-3">
                            <Badge
                              tone={
                                order.status === 'paid'
                                  ? 'teal'
                                  : order.status === 'awaiting_payment'
                                    ? 'sun'
                                    : 'neutral'
                              }
                            >
                              {order.status.replace('_', ' ')}
                            </Badge>
                          </td>
                          <td className="px-4 py-3">
                            {order.status !== 'paid' && (
                              <Button
                                size="sm"
                                variant="outline"
                                loading={busyOrder === order.id}
                                onClick={() => markPaid(order.id)}
                              >
                                {t('admin.markPaid')}
                              </Button>
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </Card>
            )}
          </section>
        )}

        {/* tutoring requests */}
        {requests && requests.length > 0 && (
          <section className="mt-10">
            <h2 className="font-display text-2xl">{t('nav.tutoring')}</h2>
            <div className="mt-5 grid gap-4 md:grid-cols-2">
              {requests.slice(0, 8).map((request) => (
                <Card key={String(request.id)}>
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <p className="font-bold text-ink-900">{String(request.contact_name)}</p>
                      <p className="truncate text-xs text-ink-500">
                        {String(request.contact_email)}
                      </p>
                    </div>
                    <Badge tone={request.status === 'new' ? 'coral' : 'neutral'}>
                      {String(request.status)}
                    </Badge>
                  </div>
                  <dl className="mt-3 flex flex-wrap gap-x-4 gap-y-1 text-xs text-ink-600">
                    <div>
                      <dt className="sr-only">{t('common.subject')}</dt>
                      <dd>{String(request.subject_slug)}</dd>
                    </div>
                    <div>
                      <dt className="sr-only">{t('common.grade')}</dt>
                      <dd>
                        {t('common.grade')} {String(request.grade)}
                      </dd>
                    </div>
                    <div>
                      <dt className="sr-only">Format</dt>
                      <dd>{String(request.format).replace(/_/g, ' ')}</dd>
                    </div>
                  </dl>
                  {Boolean(request.goals) && (
                    <p className="mt-2 text-sm text-ink-600">{String(request.goals)}</p>
                  )}
                </Card>
              ))}
            </div>
          </section>
        )}

        {/* leads */}
        {leads && leads.length > 0 && (
          <section className="mt-10">
            <h2 className="font-display text-2xl">{t('admin.leads')}</h2>
            <Card className="mt-5 p-0">
              <ul className="divide-y divide-ink-100">
                {leads.slice(0, 10).map((lead) => (
                  <li key={String(lead.id)} className="flex flex-wrap items-center gap-3 px-4 py-3">
                    <div className="min-w-0 flex-1">
                      <p className="font-semibold text-ink-900">{String(lead.name)}</p>
                      <p className="truncate text-xs text-ink-500">{String(lead.email)}</p>
                    </div>
                    <Badge tone="neutral">{String(lead.interest).replace(/_/g, ' ')}</Badge>
                    <span className="text-xs text-ink-500">
                      {lead.created_at ? formatDate(String(lead.created_at)) : ''}
                    </span>
                  </li>
                ))}
              </ul>
            </Card>
          </section>
        )}
      </div>
    </AppShell>
  );
}
