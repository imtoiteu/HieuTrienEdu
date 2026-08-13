import Link from 'next/link';
import { Brain, GitBranch, Infinity as InfinityIcon, LineChart, Repeat, ShieldCheck } from 'lucide-react';

import { isLocale } from '@hietedu/localization';
import { Button, Card, Container, MathBlock, Section } from '@hietedu/ui';

import { PageHeader } from '@/components/site/page-header';
import { MarketingShell } from '@/components/site/marketing-shell';
import { getTranslator } from '@/lib/dictionaries';

export const metadata = { title: 'Learning methods' };

export default async function LearningMethodsPage({
  params,
}: {
  params: Promise<{ locale: string }>;
}) {
  const { locale: raw } = await params;
  const locale = isLocale(raw) ? raw : 'en';
  const t = getTranslator(locale);

  const methods = [
    {
      icon: GitBranch,
      title: 'A skill graph, not a syllabus list',
      body: 'Every skill records what it depends on. "Adding fractions" requires "common denominators", which requires "equivalent fractions" and "lowest common multiple". The platform will not send a student to a skill whose foundations it can see are missing — it sends them to the foundation instead.',
    },
    {
      icon: Brain,
      title: 'Bayesian Knowledge Tracing',
      body: 'Rather than counting right answers, we maintain the probability that a student genuinely knows each skill, and update it after every attempt. A four-option multiple choice is guessable one time in four; a numeric answer is not, and the model accounts for that difference.',
    },
    {
      icon: InfinityIcon,
      title: 'Parametric questions',
      body: 'Questions are templates, not fixed items. Each is drawn fresh with new numbers, checked against constraints so the arithmetic always works out sensibly. A student cannot memorise the answer, so the only way through is the method.',
    },
    {
      icon: Repeat,
      title: 'Spacing and forgetting',
      body: 'Standard knowledge tracing assumes that once learned, always learned. That is not how memory works. Mastery decays on an exponential half-life, so a skill untouched for months resurfaces for review before an exam finds the gap first.',
    },
    {
      icon: LineChart,
      title: 'Difficulty just above current ability',
      body: 'Question difficulty is chosen from the student’s current mastery, targeting the level just above where they are. Too easy and the time is wasted; too hard and confidence goes instead of understanding.',
    },
    {
      icon: ShieldCheck,
      title: 'Diagnostic wrong answers',
      body: 'Distractors encode the mistakes students actually make — inverting a formula, forgetting to halve, slipping a decimal place. Which wrong option a student picks tells their teacher what they believe, not merely that they were wrong.',
    },
  ];

  return (
    <MarketingShell>
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
            <p className="mt-4 text-lg leading-relaxed text-ink-700">
              We think a platform that makes claims about a student&apos;s understanding owes you
              the method behind them. After each answer, the probability that the student knows the
              skill is updated by Bayes&apos; rule and then adjusted for the chance they learned it
              from the attempt itself:
            </p>

            <MathBlock caption="Conditioning on a correct answer, where L is the prior probability of knowing the skill.">
              {String.raw`P(L \mid \text{correct}) = \frac{L(1 - P_{\text{slip}})}{L(1 - P_{\text{slip}}) + (1 - L)P_{\text{guess}}}`}
            </MathBlock>

            <MathBlock caption="Then accounting for learning during the attempt.">
              {String.raw`P(L_{t+1}) = P(L \mid \text{obs}) + \bigl(1 - P(L \mid \text{obs})\bigr)P_{\text{transit}}`}
            </MathBlock>

            <p className="mt-6 text-lg leading-relaxed text-ink-700">
              A skill is marked mastered when that probability passes 95%, which from a cold start
              usually takes about five correct answers — more if hints were used, because a hinted
              answer is weaker evidence of independent understanding.
            </p>

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
