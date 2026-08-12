import Link from 'next/link';
import { Compass, Heart, MessageSquareQuote, Ruler, ShieldCheck, Sparkles } from 'lucide-react';

import { isLocale } from '@hietedu/localization';
import { Button, Card, Container, Section } from '@hietedu/ui';

import { PageHeader } from '@/components/site/page-header';
import { MarketingShell } from '@/components/site/marketing-shell';
import { getTranslator } from '@/lib/dictionaries';

export const metadata = { title: 'About' };

export default async function AboutPage({ params }: { params: Promise<{ locale: string }> }) {
  const { locale: raw } = await params;
  const locale = isLocale(raw) ? raw : 'en';
  const t = getTranslator(locale);

  const beliefs = [
    {
      icon: Ruler,
      title: 'Measure before you teach',
      body: 'A lesson aimed at the wrong gap is a wasted hour. We assess first, every time, and we keep measuring as the student works.',
    },
    {
      icon: Compass,
      title: 'Order matters more than effort',
      body: 'A student struggling with algebra is often really struggling with fractions. Our skill graph makes that visible instead of leaving it to be guessed at.',
    },
    {
      icon: ShieldCheck,
      title: 'Say what we actually know',
      body: 'When we say a skill is mastered, that is a specific claim from a specific model — not a percentage dressed up as insight.',
    },
    {
      icon: Heart,
      title: 'Confidence is the real subject',
      body: 'Most students who believe they are bad at maths have simply never been shown the missing step. Finding it changes more than a grade.',
    },
  ];

  return (
    <MarketingShell>
      <PageHeader eyebrow={t('nav.about')} title={t('about.title')} subtitle={t('about.subtitle')} />

      <Section className="pt-10">
        <Container>
          <div className="grid gap-12 lg:grid-cols-[1.15fr_0.85fr]">
            <div>
              <h2 className="font-display text-3xl">{t('about.story.title')}</h2>
              <div className="mt-5 space-y-5 text-lg leading-relaxed text-ink-700">
                <p>
                  HieuTrienEducation began as a small tutoring centre run by two teachers,{' '}
                  <strong className="text-ink-900">Thầy Hiếu</strong> and{' '}
                  <strong className="text-ink-900">Cô Triền</strong>. For years they did what every
                  good tutor does: sat with a student, worked through the homework, and tried to
                  spot the misunderstanding underneath the wrong answer.
                </p>
                <p>
                  It worked. It also did not scale, and it depended far too much on a teacher
                  noticing the right thing on the right day. A student could spend a whole term
                  practising quadratics when the real problem was that they were still counting on
                  their fingers to find a common denominator.
                </p>
                <p>
                  So we built the thing we actually wanted: a system that maps every skill and what
                  it depends on, measures a student against that map, and then spends their practice
                  time exactly where it will do the most good. The teaching is still done by
                  teachers. The platform just stops us guessing.
                </p>
              </div>

              <div className="mt-8 rounded-3xl border-2 border-brand-200 bg-brand-50 p-6">
                <MessageSquareQuote className="h-7 w-7 text-brand-500" aria-hidden="true" />
                <blockquote className="mt-3 text-lg font-semibold leading-relaxed text-ink-800">
                  “A student has never once told me they are bad at maths and turned out to be
                  right. They have simply been missing a step that nobody found.”
                </blockquote>
                <p className="mt-3 text-sm font-bold text-brand-800">Thầy Hiếu, co-founder</p>
              </div>
            </div>

            <aside className="space-y-4">
              <Card className="border-ink-900 shadow-pop">
                <Sparkles className="h-7 w-7 text-sun-500" aria-hidden="true" />
                <h3 className="mt-3 font-display text-xl">What we are not</h3>
                <ul className="mt-3 space-y-2.5 text-sm text-ink-700">
                  {[
                    'A worksheet mill. More questions is not a teaching strategy.',
                    'A video library. Watching is not the same as being able to.',
                    'A grade predictor. We report what a student can do, not a guessed score.',
                    'A replacement for teachers. It is a tool that makes them sharper.',
                  ].map((item) => (
                    <li key={item} className="flex items-start gap-2.5">
                      <span
                        className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-coral-400"
                        aria-hidden="true"
                      />
                      {item}
                    </li>
                  ))}
                </ul>
              </Card>

              <Card className="bg-teal-50">
                <h3 className="font-display text-xl">Where we are</h3>
                <p className="mt-2 text-sm text-ink-700">
                  Our centre is in Hà Nội, and our online classes reach students across Vietnam.
                  Lessons run in Vietnamese and English.
                </p>
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
              <Card key={belief.title} className="flex gap-4">
                <span className="inline-flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl bg-brand-100 text-brand-700">
                  <belief.icon className="h-6 w-6" aria-hidden="true" />
                </span>
                <div>
                  <h3 className="font-display text-lg">{belief.title}</h3>
                  <p className="mt-1.5 text-sm leading-relaxed text-ink-600">{belief.body}</p>
                </div>
              </Card>
            ))}
          </div>
        </Container>
      </Section>
    </MarketingShell>
  );
}
