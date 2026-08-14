import Link from 'next/link';
import { ArrowRight, BookOpen, Layers, Sparkles, Target } from 'lucide-react';

import type { Locale } from '@hietedu/localization';
import { Badge, Button, Card, Container, Section } from '@hietedu/ui';

import { PageHeader } from '@/components/site/page-header';
import { MarketingShell } from '@/components/site/marketing-shell';
import { api, type CourseDetail, type Subject } from '@/lib/api';
import { getTranslator } from '@/lib/dictionaries';
import { safe } from '@/lib/server-api';

/**
 * Shared implementation of the Mathematics and Physics landing pages.
 *
 * Both have identical structure and differ only in accent colour and copy, so they share one
 * component rather than being copy-pasted and drifting apart.
 */
export async function SubjectPage({
  locale,
  slug,
  intro,
  highlights,
}: {
  locale: Locale;
  slug: 'mathematics' | 'physics';
  intro: string;
  highlights: { title: string; body: string }[];
}) {
  const t = getTranslator(locale);
  const href = (path: string) => `/${locale}${path}`;
  const isPhysics = slug === 'physics';

  const subjects = await safe(api.curriculum.subjects(locale), [] as Subject[]);
  const subject = subjects.find((entry) => entry.slug === slug) ?? null;

  // Load each grade's unit list so the page shows the real curriculum, not a summary of it.
  const loaded = await Promise.all(
    (subject?.courses ?? []).map((course) =>
      safe(api.curriculum.course(course.slug, locale), null as CourseDetail | null),
    ),
  );
  const courses = loaded.filter((course): course is CourseDetail => course !== null);

  return (
    <MarketingShell locale={locale}>
      <PageHeader
        eyebrow={`${t('common.grade')} 6–12`}
        title={t(`subject.${slug}.title`)}
        subtitle={intro}
        tone={isPhysics ? 'teal' : 'lavender'}
      >
        <div className="mt-8 flex flex-wrap gap-3">
          <Link href={href('/register')}>
            <Button variant="coral" size="lg">
              {t('home.hero.ctaPrimary')}
              <ArrowRight className="h-5 w-5" aria-hidden="true" />
            </Button>
          </Link>
          <Link href={href('/courses')}>
            <Button variant="outline" size="lg">
              {t('courses.title')}
            </Button>
          </Link>
        </div>
      </PageHeader>

      <Section className="pt-12">
        <Container>
          <div className="grid gap-6 md:grid-cols-3">
            {highlights.map((highlight) => (
              <Card key={highlight.title}>
                <span
                  className={`inline-flex h-11 w-11 items-center justify-center rounded-2xl ${
                    isPhysics ? 'bg-teal-100 text-teal-700' : 'bg-brand-100 text-brand-700'
                  }`}
                >
                  <Sparkles className="h-5 w-5" aria-hidden="true" />
                </span>
                <h2 className="mt-4 font-display text-lg">{highlight.title}</h2>
                <p className="mt-2 text-sm leading-relaxed text-ink-600">{highlight.body}</p>
              </Card>
            ))}
          </div>
        </Container>
      </Section>

      <Section className="bg-white pt-4">
        <Container>
          <h2 className="font-display text-3xl sm:text-4xl">{t('subject.curriculum')}</h2>
          <p className="mt-3 max-w-2xl text-ink-600">{t('subject.curriculumIntro')}</p>

          {courses.length === 0 ? (
            <Card className="mt-8 text-center">
              <p className="text-ink-600">{t('common.emptyState')}</p>
            </Card>
          ) : (
            <div className="mt-10 space-y-10">
              {courses.map((course) => (
                <section key={course.id} aria-labelledby={`course-${course.slug}`}>
                  <div className="flex flex-wrap items-center justify-between gap-3">
                    <div className="flex items-center gap-3">
                      <Badge tone={isPhysics ? 'teal' : 'brand'}>
                        {t('common.grade')} {course.grade}
                      </Badge>
                      <h3 id={`course-${course.slug}`} className="font-display text-2xl">
                        {course.title}
                      </h3>
                    </div>
                    <Link
                      href={href(`/courses/${course.slug}`)}
                      className={`inline-flex items-center gap-1.5 text-sm font-bold ${
                        isPhysics ? 'text-teal-700' : 'text-brand-700'
                      } hover:underline`}
                    >
                      {t('courses.viewCourse')}
                      <ArrowRight className="h-4 w-4" aria-hidden="true" />
                    </Link>
                  </div>

                  {course.summary && <p className="mt-2 text-ink-600">{course.summary}</p>}

                  <div className="mt-5 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                    {course.units.map((unit) => {
                      const skillCount = unit.topics.reduce(
                        (total, topic) => total + topic.skills.length,
                        0,
                      );
                      return (
                        <Card key={unit.id} className="h-full">
                          <h4 className="font-display text-lg">{unit.title}</h4>
                          {unit.summary && (
                            <p className="mt-1.5 text-sm text-ink-600">{unit.summary}</p>
                          )}
                          <dl className="mt-4 flex gap-4 text-xs text-ink-500">
                            <div className="flex items-center gap-1.5">
                              <Layers className="h-3.5 w-3.5" aria-hidden="true" />
                              <dt className="sr-only">{t('subject.topics')}</dt>
                              <dd>
                                {unit.topics.length} {t('subject.topics')}
                              </dd>
                            </div>
                            <div className="flex items-center gap-1.5">
                              <Target className="h-3.5 w-3.5" aria-hidden="true" />
                              <dt className="sr-only">{t('subject.skills')}</dt>
                              <dd>
                                {skillCount} {t('subject.skills')}
                              </dd>
                            </div>
                          </dl>
                        </Card>
                      );
                    })}
                  </div>
                </section>
              ))}
            </div>
          )}
        </Container>
      </Section>

      <Section>
        <Container>
          <Card className={`border-ink-900 shadow-pop ${isPhysics ? 'bg-teal-50' : 'bg-brand-50'}`}>
            <div className="flex flex-wrap items-center justify-between gap-6">
              <div>
                <h2 className="font-display text-2xl sm:text-3xl">{t('home.cta.title')}</h2>
                <p className="mt-2 max-w-xl text-ink-600">{t('home.cta.subtitle')}</p>
              </div>
              <div className="flex flex-wrap gap-3">
                <Link href={href('/contact')}>
                  <Button size="lg" variant="coral">
                    {t('home.cta.button')}
                  </Button>
                </Link>
                <Link href={href('/pricing')}>
                  <Button size="lg" variant="outline">
                    <BookOpen className="h-5 w-5" aria-hidden="true" />
                    {t('nav.pricing')}
                  </Button>
                </Link>
              </div>
            </div>
          </Card>
        </Container>
      </Section>
    </MarketingShell>
  );
}
