import Link from 'next/link';
import { CheckCircle2, Sparkles } from 'lucide-react';

import { formatCurrency, isLocale } from '@hietedu/localization';
import { Badge, Button, Card, Container, Section } from '@hietedu/ui';

import { PageHeader } from '@/components/site/page-header';
import { MarketingShell } from '@/components/site/marketing-shell';
import { api, type TutoringProduct } from '@/lib/api';
import { getTranslator } from '@/lib/dictionaries';
import { safe } from '@/lib/server-api';

export const dynamic = 'force-dynamic';
/** The tab title is content too: a Vietnamese visitor should not see an English one. */
export async function generateMetadata({
  params,
}: {
  params: Promise<{ locale: string }>;
}) {
  const { locale: raw } = await params;
  const t = getTranslator(isLocale(raw) ? raw : 'en');
  return { title: t('nav.pricing') };
}

export default async function PricingPage({ params }: { params: Promise<{ locale: string }> }) {
  const { locale: raw } = await params;
  const locale = isLocale(raw) ? raw : 'en';
  const t = getTranslator(locale);
  const href = (path: string) => `/${locale}${path}`;

  const products = await safe(api.tutoring.products({ locale }), [] as TutoringProduct[]);

  const unitLabel = (unit: string) =>
    unit === 'session'
      ? t('tutoring.perSession')
      : unit === 'month'
        ? t('tutoring.perMonth')
        : t('tutoring.perCourse');

  return (
    <MarketingShell locale={locale}>
      <PageHeader
        eyebrow={t('nav.pricing')}
        title={t('pricing.title')}
        subtitle={t('pricing.subtitle')}
        tone="sun"
      />

      <Section className="pt-10">
        <Container>
          {/* The free tier comes first deliberately: it is a real product, not a teaser. */}
          <Card className="border-ink-900 bg-brand-50 shadow-pop">
            <div className="flex flex-wrap items-center justify-between gap-6">
              <div className="max-w-xl">
                <Badge tone="teal">
                  <Sparkles className="h-3.5 w-3.5" aria-hidden="true" />
                  {t('pricing.free.price')}
                </Badge>
                <h2 className="mt-3 font-display text-3xl">{t('pricing.free.title')}</h2>
                <p className="mt-2 text-ink-700">{t('pricing.free.body')}</p>
                <ul className="mt-4 grid gap-2 sm:grid-cols-2">
                  {(['practice', 'lessons', 'mastery', 'noCard'] as const).map((feature) => (
                    <li key={feature} className="flex items-start gap-2 text-sm text-ink-700">
                      <CheckCircle2
                        className="mt-0.5 h-4 w-4 shrink-0 text-teal-600"
                        aria-hidden="true"
                      />
                      {t(`pricing.free.feature.${feature}`)}
                    </li>
                  ))}
                </ul>
              </div>
              <Link href={href('/register')}>
                <Button size="lg" variant="coral">
                  {t('common.getStarted')}
                </Button>
              </Link>
            </div>
          </Card>

          <h2 className="mt-16 font-display text-3xl">{t('home.formats.title')}</h2>
          <p className="mt-2 text-ink-600">{t('home.formats.subtitle')}</p>

          {products.length === 0 ? (
            <Card className="mt-8 text-center">
              <p className="text-ink-600">{t('common.emptyState')}</p>
            </Card>
          ) : (
            <div className="mt-8 grid gap-6 md:grid-cols-2 lg:grid-cols-3">
              {products.map((product) => (
                <Card
                  key={product.id}
                  className={`flex h-full flex-col ${
                    product.is_featured ? 'border-brand-400 shadow-lift' : ''
                  }`}
                >
                  {product.is_featured && (
                    <Badge tone="coral" className="self-start">
                      {t('pricing.mostPopular')}
                    </Badge>
                  )}
                  <h3 className="mt-3 font-display text-xl">{product.name}</h3>
                  {product.tagline && (
                    <p className="mt-1 text-sm text-ink-600">{product.tagline}</p>
                  )}

                  <p className="mt-5">
                    <span className="font-display text-3xl text-brand-700">
                      {formatCurrency(product.price_vnd, locale)}
                    </span>
                    <span className="ml-1.5 text-sm text-ink-500">
                      {unitLabel(product.price_unit)}
                    </span>
                  </p>

                  <ul className="mt-3 space-y-1 text-xs text-ink-500">
                    {product.sessions_included > 0 && (
                      <li>{t('tutoring.sessions', { count: product.sessions_included })}</li>
                    )}
                    {product.session_minutes > 0 && (
                      <li>{t('tutoring.minutes', { count: product.session_minutes })}</li>
                    )}
                    {product.capacity > 1 && product.capacity < 100 && (
                      <li>{t('tutoring.maxStudents', { count: product.capacity })}</li>
                    )}
                  </ul>

                  <ul className="mt-5 flex-1 space-y-2 border-t-2 border-ink-100 pt-4">
                    {product.features.map((feature) => (
                      <li key={feature} className="flex items-start gap-2 text-sm text-ink-700">
                        <CheckCircle2
                          className="mt-0.5 h-4 w-4 shrink-0 text-teal-500"
                          aria-hidden="true"
                        />
                        {feature}
                      </li>
                    ))}
                  </ul>

                  <Link href={href(`/contact?product=${product.slug}`)} className="mt-6">
                    <Button fullWidth variant={product.is_featured ? 'coral' : 'outline'}>
                      {t('pricing.choose')}
                    </Button>
                  </Link>
                </Card>
              ))}
            </div>
          )}

          <Card className="mt-12 bg-white">
            <h2 className="font-display text-xl">{t('pricing.paymentTitle')}</h2>
            <p className="mt-2 text-sm leading-relaxed text-ink-600">
              {t('pricing.paymentBody')}
            </p>
          </Card>
        </Container>
      </Section>
    </MarketingShell>
  );
}
