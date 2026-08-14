import Link from 'next/link';
import {
  ArrowRight,
  Atom,
  BookOpen,
  CalendarClock,
  CheckCircle2,
  Flame,
  Infinity as InfinityIcon,
  LineChart,
  Quote,
  Sigma,
  Sparkles as SparklesIcon,
  Star,
  Target,
  Users,
  Video,
} from 'lucide-react';

import { isLocale } from '@hietedu/localization';
import {
  Badge,
  BlobField,
  Button,
  Card,
  Container,
  Eyebrow,
  ProgressBar,
  Section,
  Squiggle,
} from '@hietedu/ui';

import { MarketingShell } from '@/components/site/marketing-shell';
import {
  api,
  type SiteSectionContent,
  type SiteStats,
  type Testimonial,
  type TutoringProduct,
} from '@/lib/api';
import { getTranslator } from '@/lib/dictionaries';
import { safeAll } from '@/lib/server-api';

// The topic teasers on the two subject cards. Keys rather than copy, so /vi reads as Vietnamese;
// the order is the order they appear on the card.
const MATHS_TOPIC_KEYS = [
  'fractions',
  'ratios',
  'algebra',
  'functions',
  'pythagoras',
  'quadratics',
] as const;
const PHYSICS_TOPIC_KEYS = [
  'measurement',
  'motion',
  'forces',
  'energy',
  'electricity',
  'waves',
] as const;

export const dynamic = 'force-dynamic';

export default async function HomePage({ params }: { params: Promise<{ locale: string }> }) {
  const { locale: raw } = await params;
  const locale = isLocale(raw) ? raw : 'en';
  const t = getTranslator(locale);
  const href = (path: string) => `/${locale}${path}`;

  const { stats, testimonials, products, sections } = await safeAll(
    {
      stats: api.site.stats(),
      testimonials: api.site.testimonials(true, locale),
      products: api.tutoring.products({ locale }),
      sections: api.site.sections('home', locale),
    },
    {
      stats: null as SiteStats | null,
      testimonials: [] as Testimonial[],
      products: [] as TutoringProduct[],
      sections: {} as Record<string, SiteSectionContent>,
    },
  );

  /**
   * Read a field from an admin-published page section, falling back to the bundled translation.
   *
   * The fallback matters: an administrator who has not touched the CMS yet still gets the
   * original copy rather than a page full of blanks, and unpublishing a section degrades to the
   * default rather than to nothing.
   */
  const copy = (sectionKey: string, field: string, fallbackKey: string) => {
    const value = sections[sectionKey]?.[field];
    return typeof value === 'string' && value.trim() ? value : t(fallbackKey);
  };

  // Each parametric template generates thousands of distinct variants; we quote a deliberately
  // conservative 1,000 per template rather than an unfalsifiable "infinite".
  const variantEstimate = stats ? stats.questions * 1000 : 0;

  return (
    <MarketingShell locale={locale}>
      {/* ---------------------------------------------------------------- hero */}
      <section className="relative overflow-hidden bg-gradient-to-b from-lavender via-cream to-cream">
        <BlobField />
        <Container className="relative py-16 sm:py-20 lg:py-28">
          <div className="grid items-center gap-12 lg:grid-cols-[1.05fr_0.95fr] lg:gap-16">
            <div className="animate-fade-up">
              <Eyebrow tone="coral">
                <SparklesIcon className="h-3.5 w-3.5" aria-hidden="true" />
                {copy('hero', 'eyebrow', 'home.hero.eyebrow')}
              </Eyebrow>

              <h1 className="mt-6 font-display text-[2.6rem] leading-[1.05] sm:text-6xl lg:text-[4.25rem]">
                {copy('hero', 'title', 'home.hero.title')}
                <span className="relative mt-2 block text-brand-600">
                  {copy('hero', 'title_accent', 'home.hero.titleAccent')}
                  <Squiggle
                    className="absolute -bottom-3 left-0 h-3 w-56 sm:w-72"
                    tone="#FFC53D"
                  />
                </span>
              </h1>

              <p className="mt-8 max-w-xl text-lg leading-relaxed text-ink-600 sm:text-xl">
                {copy('hero', 'subtitle', 'home.hero.subtitle')}
              </p>

              <div className="mt-9 flex flex-col gap-3 sm:flex-row sm:items-center">
                <Link href={href('/register')}>
                  <Button size="lg" variant="coral" className="w-full sm:w-auto">
                    {copy('hero', 'cta_primary', 'home.hero.ctaPrimary')}
                    <ArrowRight className="h-5 w-5" aria-hidden="true" />
                  </Button>
                </Link>
                <Link href={href('/contact')}>
                  <Button size="lg" variant="outline" className="w-full sm:w-auto">
                    {copy('hero', 'cta_secondary', 'home.hero.ctaSecondary')}
                  </Button>
                </Link>
              </div>

              <p className="mt-5 flex items-center gap-2 text-sm font-semibold text-ink-500">
                <CheckCircle2 className="h-4 w-4 text-teal-500" aria-hidden="true" />
                {copy('hero', 'trust', 'home.hero.trust')}
              </p>
            </div>

            {/* An honest preview of the actual product, not a stock illustration. */}
            <div className="relative animate-pop-in">
              <div className="absolute -right-6 -top-6 hidden h-24 w-24 rotate-12 rounded-3xl border-2 border-ink-900 bg-sun-400 shadow-pop lg:block" />
              <Card className="relative border-ink-900 shadow-pop">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm font-semibold text-ink-500">
                      {t('dashboard.welcome', { name: 'An' })}
                    </p>
                    <p className="font-display text-2xl">{t('dashboard.yourProgress')}</p>
                  </div>
                  <Badge tone="sun">
                    <Flame className="h-3.5 w-3.5" aria-hidden="true" />6 {t('dashboard.streak')}
                  </Badge>
                </div>

                <div className="mt-6 space-y-5">
                  <ProgressBar
                    value={78}
                    label={t('dashboard.overallMastery')}
                    showValue
                    size="lg"
                  />
                  <ProgressBar value={84} label={t('nav.mathematics')} tone="brand" showValue />
                  <ProgressBar value={61} label={t('nav.physics')} tone="teal" showValue />
                </div>

                <div className="mt-6 rounded-2xl border-2 border-dashed border-brand-200 bg-brand-50 p-4">
                  <p className="text-xs font-bold uppercase tracking-widest text-brand-700">
                    {t('dashboard.recommended')}
                  </p>
                  <ul className="mt-3 space-y-2">
                    {['Adding fractions', 'Linear equations', "Newton's second law"].map(
                      (skill) => (
                        <li
                          key={skill}
                          className="flex items-center gap-2 text-sm font-semibold text-ink-800"
                        >
                          <ArrowRight className="h-4 w-4 text-brand-500" aria-hidden="true" />
                          {skill}
                        </li>
                      ),
                    )}
                  </ul>
                </div>
              </Card>
              <div className="absolute -bottom-5 -left-5 hidden h-16 w-16 -rotate-12 rounded-2xl border-2 border-ink-900 bg-teal-400 shadow-pop lg:block" />
            </div>
          </div>
        </Container>
      </section>

      {/* ---------------------------------------------------------------- stats */}
      {stats && (
        <section className="border-y-2 border-ink-100 bg-white">
          <Container className="py-10">
            <dl className="grid grid-cols-2 gap-6 text-center md:grid-cols-4">
              <StatItem value={stats.skills} label={t('home.stats.skills')} />
              <StatItem value={stats.questions} label={t('home.stats.questions')} />
              <StatItem
                value={variantEstimate}
                label={t('home.stats.variants')}
                approximate
              />
              <StatItem value={stats.teachers} label={t('home.stats.teachers')} />
            </dl>
          </Container>
        </section>
      )}

      {/* ---------------------------------------------------------------- why */}
      <Section>
        <Container>
          <div className="mx-auto max-w-3xl text-center">
            <Eyebrow>{t('home.why.eyebrow')}</Eyebrow>
            <h2 className="mt-5 text-3xl sm:text-4xl lg:text-5xl">{t('home.why.title')}</h2>
            <p className="mt-5 text-lg text-ink-600">{t('home.why.subtitle')}</p>
          </div>

          <div className="mt-14 grid gap-6 md:grid-cols-2 lg:grid-cols-4">
            {[
              {
                icon: Target,
                title: t('home.why.mastery.title'),
                body: t('home.why.mastery.body'),
                tone: 'bg-brand-100 text-brand-700',
              },
              {
                icon: LineChart,
                title: t('home.why.adaptive.title'),
                body: t('home.why.adaptive.body'),
                tone: 'bg-teal-100 text-teal-700',
              },
              {
                icon: InfinityIcon,
                title: t('home.why.infinite.title'),
                body: t('home.why.infinite.body'),
                tone: 'bg-coral-100 text-coral-700',
              },
              {
                icon: Users,
                title: t('home.why.teachers.title'),
                body: t('home.why.teachers.body'),
                tone: 'bg-sun-100 text-sun-800',
              },
            ].map(({ icon: Icon, title, body, tone }) => (
              <Card key={title} interactive className="h-full">
                <span
                  className={`inline-flex h-12 w-12 items-center justify-center rounded-2xl ${tone}`}
                >
                  <Icon className="h-6 w-6" aria-hidden="true" />
                </span>
                <h3 className="mt-5 font-display text-xl">{title}</h3>
                <p className="mt-2.5 text-sm leading-relaxed text-ink-600">{body}</p>
              </Card>
            ))}
          </div>
        </Container>
      </Section>

      {/* ---------------------------------------------------------------- subjects */}
      <Section className="bg-white">
        <Container>
          <div className="mx-auto max-w-2xl text-center">
            <Eyebrow tone="teal">{t('home.subjects.eyebrow')}</Eyebrow>
            <h2 className="mt-5 text-3xl sm:text-4xl">{t('home.subjects.title')}</h2>
          </div>

          <div className="mt-12 grid gap-6 lg:grid-cols-2">
            <SubjectCard
              href={href('/mathematics')}
              icon={<Sigma className="h-7 w-7" aria-hidden="true" />}
              title={t('subject.mathematics.title')}
              body={t('home.subjects.mathematics')}
              cta={t('home.subjects.explore')}
              accent="brand"
              topics={MATHS_TOPIC_KEYS.map((key) => t(`home.subjects.maths.${key}`))}
            />
            <SubjectCard
              href={href('/physics')}
              icon={<Atom className="h-7 w-7" aria-hidden="true" />}
              title={t('subject.physics.title')}
              body={t('home.subjects.physics')}
              cta={t('home.subjects.explore')}
              accent="teal"
              topics={PHYSICS_TOPIC_KEYS.map((key) => t(`home.subjects.physics.${key}`))}
            />
          </div>
        </Container>
      </Section>

      {/* ---------------------------------------------------------------- how it works */}
      <Section>
        <Container>
          <div className="mx-auto max-w-2xl text-center">
            <Eyebrow tone="sun">{t('home.how.eyebrow')}</Eyebrow>
            <h2 className="mt-5 text-3xl sm:text-4xl">{t('home.how.title')}</h2>
          </div>

          <ol className="mt-14 grid gap-6 md:grid-cols-2 lg:grid-cols-4">
            {[
              { title: t('home.how.step1.title'), body: t('home.how.step1.body') },
              { title: t('home.how.step2.title'), body: t('home.how.step2.body') },
              { title: t('home.how.step3.title'), body: t('home.how.step3.body') },
              { title: t('home.how.step4.title'), body: t('home.how.step4.body') },
            ].map((step, index) => (
              <li key={step.title} className="relative">
                <Card className="h-full">
                  <span className="inline-flex h-11 w-11 items-center justify-center rounded-2xl border-2 border-ink-900 bg-brand-500 font-display text-lg font-extrabold text-white shadow-pop-sm">
                    {index + 1}
                  </span>
                  <h3 className="mt-5 font-display text-lg">{step.title}</h3>
                  <p className="mt-2 text-sm leading-relaxed text-ink-600">{step.body}</p>
                </Card>
              </li>
            ))}
          </ol>
        </Container>
      </Section>

      {/* ---------------------------------------------------------------- formats */}
      {products.length > 0 && (
        <Section className="bg-white">
          <Container>
            <div className="mx-auto max-w-2xl text-center">
              <Eyebrow tone="coral">{t('home.formats.eyebrow')}</Eyebrow>
              <h2 className="mt-5 text-3xl sm:text-4xl">{t('home.formats.title')}</h2>
              <p className="mt-4 text-ink-600">{t('home.formats.subtitle')}</p>
            </div>

            <div className="mt-12 grid gap-6 md:grid-cols-2 lg:grid-cols-3">
              {products.slice(0, 6).map((product) => (
                <Card key={product.id} interactive className="flex h-full flex-col">
                  <div className="flex items-start justify-between gap-3">
                    <span className="inline-flex h-11 w-11 items-center justify-center rounded-2xl bg-brand-100 text-brand-700">
                      {product.format === 'recorded' ? (
                        <Video className="h-5 w-5" aria-hidden="true" />
                      ) : product.format === 'one_to_one' ? (
                        <Users className="h-5 w-5" aria-hidden="true" />
                      ) : (
                        <CalendarClock className="h-5 w-5" aria-hidden="true" />
                      )}
                    </span>
                    {product.is_featured && <Badge tone="coral">{t('pricing.mostPopular')}</Badge>}
                  </div>
                  <h3 className="mt-4 font-display text-lg">{product.name}</h3>
                  <p className="mt-1.5 text-sm text-ink-600">{product.tagline}</p>
                  <ul className="mt-4 flex-1 space-y-1.5">
                    {product.features.slice(0, 3).map((feature) => (
                      <li key={feature} className="flex items-start gap-2 text-sm text-ink-600">
                        <CheckCircle2
                          className="mt-0.5 h-4 w-4 shrink-0 text-teal-500"
                          aria-hidden="true"
                        />
                        {feature}
                      </li>
                    ))}
                  </ul>
                  <Link
                    href={href('/pricing')}
                    className="mt-5 inline-flex items-center gap-1.5 text-sm font-bold text-brand-700 hover:underline"
                  >
                    {t('common.learnMore')}
                    <ArrowRight className="h-4 w-4" aria-hidden="true" />
                  </Link>
                </Card>
              ))}
            </div>
          </Container>
        </Section>
      )}

      {/* ---------------------------------------------------------------- testimonials */}
      {testimonials.length > 0 && (
        <Section>
          <Container>
            <div className="mx-auto max-w-2xl text-center">
              <Eyebrow>{t('home.results.eyebrow')}</Eyebrow>
              <h2 className="mt-5 text-3xl sm:text-4xl">{t('home.results.title')}</h2>
            </div>

            <div className="mt-12 grid gap-6 md:grid-cols-2 lg:grid-cols-3">
              {testimonials.slice(0, 3).map((testimonial) => (
                <Card key={testimonial.id} className="flex h-full flex-col">
                  <Quote className="h-8 w-8 text-brand-200" aria-hidden="true" />
                  <blockquote className="mt-3 flex-1 text-sm leading-relaxed text-ink-700">
                    “{testimonial.quote}”
                  </blockquote>
                  <div className="mt-5 flex items-center gap-1" aria-label={t('a11y.ratingOutOf5', { rating: testimonial.rating })}>
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
                  <footer className="mt-3 border-t-2 border-ink-100 pt-3">
                    <p className="font-bold text-ink-900">{testimonial.author_name}</p>
                    <p className="text-xs text-ink-500">{testimonial.author_role}</p>
                  </footer>
                </Card>
              ))}
            </div>

            <div className="mt-10 text-center">
              <Link href={href('/testimonials')}>
                <Button variant="outline">{t('common.viewAll')}</Button>
              </Link>
            </div>
          </Container>
        </Section>
      )}

      {/* ---------------------------------------------------------------- CTA */}
      <section className="relative overflow-hidden bg-brand-600 py-20 text-white">
        <div aria-hidden="true" className="absolute inset-0 stripe-brand opacity-40" />
        <Container className="relative text-center">
          <h2 className="mx-auto max-w-2xl font-display text-3xl text-white sm:text-4xl lg:text-5xl">
            {t('home.cta.title')}
          </h2>
          <p className="mx-auto mt-5 max-w-xl text-lg text-brand-100">{t('home.cta.subtitle')}</p>
          <div className="mt-9 flex flex-col justify-center gap-3 sm:flex-row">
            <Link href={href('/contact')}>
              <Button size="lg" variant="secondary" className="w-full sm:w-auto">
                {t('home.cta.button')}
                <ArrowRight className="h-5 w-5" aria-hidden="true" />
              </Button>
            </Link>
            <Link href={href('/courses')}>
              <Button
                size="lg"
                variant="outline"
                className="w-full border-white bg-transparent text-white shadow-none hover:bg-white/10 sm:w-auto"
              >
                <BookOpen className="h-5 w-5" aria-hidden="true" />
                {t('nav.courses')}
              </Button>
            </Link>
          </div>
        </Container>
      </section>
    </MarketingShell>
  );
}

function StatItem({
  value,
  label,
  approximate,
}: {
  value: number;
  label: string;
  approximate?: boolean;
}) {
  const display =
    value >= 1_000_000
      ? `${Math.round(value / 1_000_000)}M`
      : value >= 1000
        ? `${Math.round(value / 1000)}k`
        : String(value);
  return (
    <div>
      <dt className="sr-only">{label}</dt>
      <dd>
        <span className="block font-display text-3xl text-brand-600 sm:text-4xl">
          {approximate && '~'}
          {display}
        </span>
        <span className="mt-1 block text-sm font-semibold text-ink-500">{label}</span>
      </dd>
    </div>
  );
}

function SubjectCard({
  href,
  icon,
  title,
  body,
  cta,
  accent,
  topics,
}: {
  href: string;
  icon: React.ReactNode;
  title: string;
  body: string;
  cta: string;
  accent: 'brand' | 'teal';
  topics: string[];
}) {
  const styles =
    accent === 'brand'
      ? { chip: 'bg-brand-100 text-brand-700', link: 'text-brand-700', dot: 'bg-brand-400' }
      : { chip: 'bg-teal-100 text-teal-700', link: 'text-teal-700', dot: 'bg-teal-400' };

  return (
    <Card interactive className="flex h-full flex-col">
      <span
        className={`inline-flex h-14 w-14 items-center justify-center rounded-3xl ${styles.chip}`}
      >
        {icon}
      </span>
      <h3 className="mt-5 font-display text-2xl">{title}</h3>
      <p className="mt-2 text-ink-600">{body}</p>
      <ul className="mt-5 grid flex-1 gap-2 sm:grid-cols-2">
        {topics.map((topic) => (
          <li key={topic} className="flex items-center gap-2 text-sm text-ink-700">
            <span className={`h-1.5 w-1.5 shrink-0 rounded-full ${styles.dot}`} aria-hidden="true" />
            {topic}
          </li>
        ))}
      </ul>
      <Link
        href={href}
        className={`mt-6 inline-flex items-center gap-1.5 font-bold ${styles.link} hover:underline`}
      >
        {cta}
        <ArrowRight className="h-4 w-4" aria-hidden="true" />
      </Link>
    </Card>
  );
}
