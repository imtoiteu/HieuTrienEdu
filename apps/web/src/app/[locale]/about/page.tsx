import Link from 'next/link';
import { Compass, Heart, MessageSquareQuote, Ruler, ShieldCheck, Sparkles } from 'lucide-react';

import { isLocale } from '@hietedu/localization';
import { Button, Card, Container, Section } from '@hietedu/ui';

import { PageHeader } from '@/components/site/page-header';
import { MarketingShell } from '@/components/site/marketing-shell';
import { getTranslator } from '@/lib/dictionaries';

/** The tab title is content too: a Vietnamese visitor should not see an English one. */
export async function generateMetadata({
  params,
}: {
  params: Promise<{ locale: string }>;
}) {
  const { locale: raw } = await params;
  const t = getTranslator(isLocale(raw) ? raw : 'en');
  return { title: t('nav.about') };
}

export default async function AboutPage({ params }: { params: Promise<{ locale: string }> }) {
  const { locale: raw } = await params;
  const locale = isLocale(raw) ? raw : 'en';
  const t = getTranslator(locale);

  // Icons stay in code; every word comes from the dictionary so /vi reads as Vietnamese.
  const beliefs = [
    { icon: Ruler, key: 'measure' },
    { icon: Compass, key: 'order' },
    { icon: ShieldCheck, key: 'honest' },
    { icon: Heart, key: 'confidence' },
  ] as const;

  const notList = ['worksheets', 'videos', 'predictor', 'replacement'] as const;

  return (
    <MarketingShell locale={locale}>
      <PageHeader eyebrow={t('nav.about')} title={t('about.title')} subtitle={t('about.subtitle')} />

      <Section className="pt-10">
        <Container>
          <div className="grid gap-12 lg:grid-cols-[1.15fr_0.85fr]">
            <div>
              <h2 className="font-display text-3xl">{t('about.story.title')}</h2>
              <div className="mt-5 space-y-5 text-lg leading-relaxed text-ink-700">
                <p>{t('about.story.p1')}</p>
                <p>{t('about.story.p2')}</p>
                <p>{t('about.story.p3')}</p>
              </div>

              <div className="mt-8 rounded-3xl border-2 border-brand-200 bg-brand-50 p-6">
                <MessageSquareQuote className="h-7 w-7 text-brand-500" aria-hidden="true" />
                <blockquote className="mt-3 text-lg font-semibold leading-relaxed text-ink-800">
                  {t('about.founderQuote')}
                </blockquote>
                <p className="mt-3 text-sm font-bold text-brand-800">{t('about.founderCaption')}</p>
              </div>
            </div>

            <aside className="space-y-4">
              <Card className="border-ink-900 shadow-pop">
                <Sparkles className="h-7 w-7 text-sun-500" aria-hidden="true" />
                <h3 className="mt-3 font-display text-xl">{t('about.notTitle')}</h3>
                <ul className="mt-3 space-y-2.5 text-sm text-ink-700">
                  {notList.map((key) => (
                    <li key={key} className="flex items-start gap-2.5">
                      <span
                        className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-coral-400"
                        aria-hidden="true"
                      />
                      {t(`about.not.${key}`)}
                    </li>
                  ))}
                </ul>
              </Card>

              <Card className="bg-teal-50">
                <h3 className="font-display text-xl">{t('about.whereTitle')}</h3>
                <p className="mt-2 text-sm text-ink-700">{t('about.whereBody')}</p>
                <Link href={`/${locale}/contact`} className="mt-4 inline-block">
                  <Button variant="outline">{t('nav.contact')}</Button>
                </Link>
              </Card>
            </aside>
          </div>
        </Container>
      </Section>

      <Section className="bg-white">
        <Container>
          <h2 className="text-center font-display text-3xl sm:text-4xl">
            {t('about.mission.title')}
          </h2>
          <div className="mt-12 grid gap-6 md:grid-cols-2">
            {beliefs.map((belief) => (
              <Card key={belief.key} className="flex gap-4">
                <span className="inline-flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl bg-brand-100 text-brand-700">
                  <belief.icon className="h-6 w-6" aria-hidden="true" />
                </span>
                <div>
                  <h3 className="font-display text-lg">{t(`about.belief.${belief.key}.title`)}</h3>
                  <p className="mt-1.5 text-sm leading-relaxed text-ink-600">
                    {t(`about.belief.${belief.key}.body`)}
                  </p>
                </div>
              </Card>
            ))}
          </div>
        </Container>
      </Section>
    </MarketingShell>
  );
}
