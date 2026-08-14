import Link from 'next/link';
import { Brain, GitBranch, Infinity as InfinityIcon, LineChart, Repeat, ShieldCheck } from 'lucide-react';

import { isLocale } from '@hietedu/localization';
import { Button, Card, Container, MathBlock, Section } from '@hietedu/ui';

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
  return { title: t('nav.methods') };
}

export default async function LearningMethodsPage({
  params,
}: {
  params: Promise<{ locale: string }>;
}) {
  const { locale: raw } = await params;
  const locale = isLocale(raw) ? raw : 'en';
  const t = getTranslator(locale);

  const methods = [
    { icon: GitBranch, title: t('methods.item1.title'), body: t('methods.item1.body') },
    { icon: Brain, title: t('methods.item2.title'), body: t('methods.item2.body') },
    { icon: InfinityIcon, title: t('methods.item3.title'), body: t('methods.item3.body') },
    { icon: Repeat, title: t('methods.item4.title'), body: t('methods.item4.body') },
    { icon: LineChart, title: t('methods.item5.title'), body: t('methods.item5.body') },
    { icon: ShieldCheck, title: t('methods.item6.title'), body: t('methods.item6.body') },
  ];

  return (
    <MarketingShell locale={locale}>
      <PageHeader
        eyebrow={t('nav.methods')}
        title={t('methods.title')}
        subtitle={t('methods.subtitle')}
      />

      <Section className="pt-10">
        <Container>
          <div className="grid gap-6 md:grid-cols-2">
            {methods.map((method) => (
              <Card key={method.title} className="h-full">
                <span className="inline-flex h-12 w-12 items-center justify-center rounded-2xl bg-brand-100 text-brand-700">
                  <method.icon className="h-6 w-6" aria-hidden="true" />
                </span>
                <h2 className="mt-4 font-display text-xl">{method.title}</h2>
                <p className="mt-2 leading-relaxed text-ink-600">{method.body}</p>
              </Card>
            ))}
          </div>
        </Container>
      </Section>

      <Section className="bg-white">
        <Container>
          <div className="mx-auto max-w-3xl">
            <h2 className="font-display text-3xl">{t('methods.modelTitle')}</h2>
            <p className="mt-4 text-lg leading-relaxed text-ink-700">{t('methods.modelIntro')}</p>

            <MathBlock caption={t('methods.modelCaption1')}>
              {String.raw`P(L \mid \text{correct}) = \frac{L(1 - P_{\text{slip}})}{L(1 - P_{\text{slip}}) + (1 - L)P_{\text{guess}}}`}
            </MathBlock>

            <MathBlock caption={t('methods.modelCaption2')}>
              {String.raw`P(L_{t+1}) = P(L \mid \text{obs}) + \bigl(1 - P(L \mid \text{obs})\bigr)P_{\text{transit}}`}
            </MathBlock>

            <p className="mt-6 text-lg leading-relaxed text-ink-700">{t('methods.modelOutro')}</p>

            <div className="mt-8 flex flex-wrap gap-3">
              <Link href={`/${locale}/register`}>
                <Button variant="coral" size="lg">
                  {t('home.hero.ctaPrimary')}
                </Button>
              </Link>
              <Link href={`/${locale}/blog/what-mastery-actually-means`}>
                <Button variant="outline" size="lg">
                  {t('common.readMore')}
                </Button>
              </Link>
            </div>
          </div>
        </Container>
      </Section>
    </MarketingShell>
  );
}
