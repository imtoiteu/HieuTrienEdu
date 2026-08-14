import Link from 'next/link';
import { notFound } from 'next/navigation';
import { CalendarClock, CheckCircle2, MapPin, Users, Video } from 'lucide-react';

import { formatCurrency, isLocale } from '@hietedu/localization';
import { Badge, Button, Card, Container, Section } from '@hietedu/ui';

import { TutoringEnquiryForm } from '@/components/site/tutoring-enquiry-form';
import { PageHeader } from '@/components/site/page-header';
import { MarketingShell } from '@/components/site/marketing-shell';
import { api, type ClassGroup, type TeacherCard, type TutoringProduct } from '@/lib/api';
import { getTranslator } from '@/lib/dictionaries';
import { safeAll } from '@/lib/server-api';

export const dynamic = 'force-dynamic';

/**
 * One route serves all five tutoring formats. Each differs in copy and in which API format
 * filter it applies; the structure is identical, so duplicating it five times would only create
 * five places to forget to update.
 */
const FORMATS = {
  'one-to-one': {
    apiFormat: 'one_to_one',
    titleKey: 'tutoring.oneToOne.title',
    subtitleKey: 'tutoring.oneToOne.subtitle',
    tone: 'lavender' as const,
    icon: Users,
    pointKeys: ['focus', 'data', 'choice', 'mode'],
  },
  group: {
    apiFormat: 'group',
    titleKey: 'tutoring.group.title',
    subtitleKey: 'tutoring.group.subtitle',
    tone: 'teal' as const,
    icon: Users,
    pointKeys: ['capped', 'ability', 'peer', 'report'],
  },
  online: {
    apiFormat: 'online_live',
    titleKey: 'tutoring.online.title',
    subtitleKey: 'tutoring.online.subtitle',
    tone: 'coral' as const,
    icon: Video,
    pointKeys: ['live', 'recorded', 'whiteboard', 'anywhere'],
  },
  live: {
    apiFormat: 'online_live',
    titleKey: 'tutoring.live.title',
    subtitleKey: 'tutoring.live.subtitle',
    tone: 'sun' as const,
    icon: CalendarClock,
    pointKeys: ['scheduled', 'questions', 'notes', 'attendance'],
  },
  recorded: {
    apiFormat: 'recorded',
    titleKey: 'tutoring.recorded.title',
    subtitleKey: 'tutoring.recorded.subtitle',
    tone: 'lavender' as const,
    icon: Video,
    pointKeys: ['pace', 'platform', 'lessons', 'price'],
  },
} as const;

export function generateStaticParams() {
  return Object.keys(FORMATS).map((format) => ({ format }));
}

export default async function TutoringFormatPage({
  params,
}: {
  params: Promise<{ locale: string; format: string }>;
}) {
  const { locale: raw, format } = await params;
  const locale = isLocale(raw) ? raw : 'en';
  const config = FORMATS[format as keyof typeof FORMATS];
  if (!config) notFound();

  const t = getTranslator(locale);
  const Icon = config.icon;

  const { products, classes, teachers } = await safeAll(
    {
      products: api.tutoring.products({ format: config.apiFormat, locale }),
      classes: api.tutoring.classes({ format: config.apiFormat, locale }),
      teachers: api.tutoring.teachers({ locale }),
    },
    {
      products: [] as TutoringProduct[],
      classes: [] as ClassGroup[],
      teachers: [] as TeacherCard[],
    },
  );

  return (
    <MarketingShell locale={locale}>
      <PageHeader
        eyebrow={t('nav.tutoring')}
        title={t(config.titleKey)}
        subtitle={t(config.subtitleKey)}
        tone={config.tone}
      />

      <Section className="pt-10">
        <Container>
          <div className="grid gap-10 lg:grid-cols-[1.1fr_0.9fr]">
            <div>
              <Card className="border-ink-900 shadow-pop">
                <span className="inline-flex h-12 w-12 items-center justify-center rounded-2xl bg-brand-100 text-brand-700">
                  <Icon className="h-6 w-6" aria-hidden="true" />
                </span>
                <h2 className="mt-4 font-display text-2xl">{t('tutoring.whatYouGet')}</h2>
                <ul className="mt-4 space-y-3">
                  {config.pointKeys.map((point) => (
                    <li key={point} className="flex items-start gap-3 text-ink-700">
                      <CheckCircle2
                        className="mt-0.5 h-5 w-5 shrink-0 text-teal-600"
                        aria-hidden="true"
                      />
                      {t(`tutoring.point.${format}.${point}`)}
                    </li>
                  ))}
                </ul>
              </Card>

              {products.length > 0 && (
                <div className="mt-8">
                  <h2 className="font-display text-2xl">{t('nav.pricing')}</h2>
                  <div className="mt-4 grid gap-4 sm:grid-cols-2">
                    {products.map((product) => (
                      <Card key={product.id}>
                        <h3 className="font-display text-lg">{product.name}</h3>
                        <p className="mt-3">
                          <span className="font-display text-2xl text-brand-700">
                            {formatCurrency(product.price_vnd, locale)}
                          </span>
                          <span className="ml-1.5 text-sm text-ink-500">
                            {product.price_unit === 'session'
                              ? t('tutoring.perSession')
                              : product.price_unit === 'month'
                                ? t('tutoring.perMonth')
                                : t('tutoring.perCourse')}
                          </span>
                        </p>
                        <ul className="mt-3 space-y-1.5">
                          {product.features.slice(0, 4).map((feature) => (
                            <li
                              key={feature}
                              className="flex items-start gap-2 text-sm text-ink-600"
                            >
                              <CheckCircle2
                                className="mt-0.5 h-3.5 w-3.5 shrink-0 text-teal-500"
                                aria-hidden="true"
                              />
                              {feature}
                            </li>
                          ))}
                        </ul>
                      </Card>
                    ))}
                  </div>
                </div>
              )}

              {classes.length > 0 && (
                <div className="mt-8">
                  <h2 className="font-display text-2xl">{t('tutoring.openClasses')}</h2>
                  <div className="mt-4 space-y-4">
                    {classes.map((group) => (
                      <Card key={group.id}>
                        <div className="flex flex-wrap items-start justify-between gap-3">
                          <div className="min-w-0">
                            <h3 className="font-display text-lg">{group.name}</h3>
                            {group.course_title && (
                              <p className="mt-0.5 text-sm text-ink-600">{group.course_title}</p>
                            )}
                          </div>
                          <Badge tone={group.seats_available > 0 ? 'teal' : 'neutral'}>
                            {group.seats_available > 0
                              ? t('tutoring.seatsLeft', { count: group.seats_available })
                              : t('tutoring.classFull')}
                          </Badge>
                        </div>

                        <dl className="mt-4 flex flex-wrap gap-x-6 gap-y-2 text-sm text-ink-600">
                          {group.teacher && (
                            <div className="flex items-center gap-1.5">
                              <Users className="h-4 w-4" aria-hidden="true" />
                              <dt className="sr-only">{t('nav.teachers')}</dt>
                              <dd>{group.teacher.full_name}</dd>
                            </div>
                          )}
                          {group.schedule.length > 0 && (
                            <div className="flex items-center gap-1.5">
                              <CalendarClock className="h-4 w-4" aria-hidden="true" />
                              <dt className="sr-only">{t('tutoring.chooseSchedule')}</dt>
                              <dd>
                                {group.schedule
                                  .map(
                                    (slot) =>
                                      `${t(`common.weekday.${slot.weekday % 7}`)} ${slot.start_time}–${slot.end_time}`,
                                  )
                                  .join(', ')}
                              </dd>
                            </div>
                          )}
                          {group.location && (
                            <div className="flex items-center gap-1.5">
                              <MapPin className="h-4 w-4" aria-hidden="true" />
                              <dt className="sr-only">{t('tutoring.location')}</dt>
                              <dd>{group.location}</dd>
                            </div>
                          )}
                        </dl>
                      </Card>
                    ))}
                  </div>
                </div>
              )}
            </div>

            <aside>
              <div className="lg:sticky lg:top-24">
                <TutoringEnquiryForm
                  defaultFormat={config.apiFormat}
                  teachers={teachers}
                  locale={locale}
                />
                <p className="mt-4 text-center text-sm text-ink-500">
                  {t('tutoring.preferToTalk')}{' '}
                  <Link
                    href={`/${locale}/contact`}
                    className="font-bold text-brand-700 hover:underline"
                  >
                    {t('nav.contact')}
                  </Link>
                </p>
              </div>
            </aside>
          </div>
        </Container>
      </Section>
    </MarketingShell>
  );
}
