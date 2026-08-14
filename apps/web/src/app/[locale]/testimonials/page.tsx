import { Quote, Star } from 'lucide-react';

import { isLocale } from '@hietedu/localization';
import { Badge, Card, Container, Section } from '@hietedu/ui';

import { PageHeader } from '@/components/site/page-header';
import { MarketingShell } from '@/components/site/marketing-shell';
import { api, type Testimonial } from '@/lib/api';
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
  return { title: t('nav.testimonials') };
}

export default async function TestimonialsPage({
  params,
}: {
  params: Promise<{ locale: string }>;
}) {
  const { locale: raw } = await params;
  const locale = isLocale(raw) ? raw : 'en';
  const t = getTranslator(locale);

  const testimonials = await safe(api.site.testimonials(undefined, locale), [] as Testimonial[]);
  const average =
    testimonials.length > 0
      ? testimonials.reduce((total, item) => total + item.rating, 0) / testimonials.length
      : 0;

  return (
    <MarketingShell locale={locale}>
      <PageHeader
        eyebrow={t('nav.testimonials')}
        title={t('testimonials.title')}
        subtitle={t('testimonials.subtitle')}
        tone="sun"
      >
        {testimonials.length > 0 && (
          <p className="mt-6 flex items-center gap-2 text-lg font-bold text-ink-800">
            <span className="flex" aria-hidden="true">
              {Array.from({ length: 5 }, (_, index) => (
                <Star
                  key={index}
                  className={
                    index < Math.round(average)
                      ? 'h-5 w-5 fill-sun-500 text-sun-500'
                      : 'h-5 w-5 text-ink-300'
                  }
                />
              ))}
            </span>
            {average.toFixed(1)} / 5
            <span className="font-normal text-ink-500">
              ({testimonials.length} {testimonials.length === 1 ? 'review' : 'reviews'})
            </span>
          </p>
        )}
      </PageHeader>

      <Section className="pt-10">
        <Container>
          {testimonials.length === 0 ? (
            <Card className="text-center">
              <p className="text-ink-600">{t('common.emptyState')}</p>
            </Card>
          ) : (
            <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
              {testimonials.map((testimonial) => (
                <Card key={testimonial.id} className="flex h-full flex-col">
                  <Quote className="h-8 w-8 text-brand-200" aria-hidden="true" />
                  <blockquote className="mt-3 flex-1 leading-relaxed text-ink-700">
                    “{testimonial.quote}”
                  </blockquote>
                  <div
                    className="mt-5 flex items-center gap-1"
                    aria-label={t('a11y.ratingOutOf5', { rating: testimonial.rating })}
                  >
                    {Array.from({ length: 5 }, (_, index) => (
                      <Star
                        key={index}
                        className={
                          index < testimonial.rating
                            ? 'h-4 w-4 fill-sun-400 text-sun-400'
                            : 'h-4 w-4 text-ink-200'
                        }
                        aria-hidden="true"
                      />
                    ))}
                  </div>
                  <footer className="mt-4 flex items-center justify-between gap-3 border-t-2 border-ink-100 pt-4">
                    <div>
                      <p className="font-bold text-ink-900">{testimonial.author_name}</p>
                      <p className="text-xs text-ink-500">{testimonial.author_role}</p>
                    </div>
                    {testimonial.subject_slug && (
                      <Badge tone={testimonial.subject_slug === 'physics' ? 'teal' : 'brand'}>
                        {t(`subject.${testimonial.subject_slug}.title`)}
                        {testimonial.grade ? ` · ${testimonial.grade}` : ''}
                      </Badge>
                    )}
                  </footer>
                </Card>
              ))}
            </div>
          )}
        </Container>
      </Section>
    </MarketingShell>
  );
}
