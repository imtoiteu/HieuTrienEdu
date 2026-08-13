import Link from 'next/link';
import { ArrowRight, Atom, BookOpen, Clock, Layers, Sigma, Target } from 'lucide-react';

import { isLocale } from '@hietedu/localization';
import { Badge, Card, Container, Eyebrow, Section } from '@hietedu/ui';

import { MarketingShell } from '@/components/site/marketing-shell';
import { api, type Subject } from '@/lib/api';
import { getTranslator } from '@/lib/dictionaries';
import { safe } from '@/lib/server-api';

export const dynamic = 'force-dynamic';

export default async function CoursesPage({ params }: { params: Promise<{ locale: string }> }) {
  const { locale: raw } = await params;
  const locale = isLocale(raw) ? raw : 'en';
  const t = getTranslator(locale);
  const href = (path: string) => `/${locale}${path}`;

  const subjects = await safe(api.curriculum.subjects(locale), [] as Subject[]);

  return (
    <MarketingShell locale={locale}>
      <Section className="bg-lavender pb-10 pt-14">
        <Container>
          <Eyebrow>{t('subject.curriculum')}</Eyebrow>
          <h1 className="mt-5 font-display text-4xl sm:text-5xl">{t('courses.title')}</h1>
          <p className="mt-4 max-w-2xl text-lg text-ink-600">{t('courses.subtitle')}</p>
        </Container>
      </Section>

      <Section className="pt-10">
        <Container>
          {subjects.length === 0 ? (
            <Card className="text-center">
              <p className="text-ink-600">{t('common.emptyState')}</p>
            </Card>
          ) : (
            <div className="space-y-16">
              {subjects.map((subject) => {
                const isPhysics = subject.slug === 'physics';
                return (
                  <section key={subject.id} aria-labelledby={`subject-${subject.slug}`}>
                    <div className="flex items-center gap-4">
                      <span
                        className={`inline-flex h-14 w-14 items-center justify-center rounded-3xl ${
                          isPhysics ? 'bg-teal-100 text-teal-700' : 'bg-brand-100 text-brand-700'
                        }`}
                      >
                        {isPhysics ? (
                          <Atom className="h-7 w-7" aria-hidden="true" />
                        ) : (
                          <Sigma className="h-7 w-7" aria-hidden="true" />
                        )}
                      </span>
                      <div>
                        <h2 id={`subject-${subject.slug}`} className="font-display text-3xl">
                          {subject.name}
                        </h2>
                        {subject.description && (
                          <p className="mt-1 max-w-2xl text-ink-600">{subject.description}</p>
                        )}
                      </div>
                    </div>

                    <div className="mt-8 grid gap-5 sm:grid-cols-2 lg:grid-cols-4">
                      {subject.courses.map((course) => (
                        <Link key={course.id} href={href(`/courses/${course.slug}`)}>
                          <Card interactive className="flex h-full flex-col">
                            <Badge tone={isPhysics ? 'teal' : 'brand'}>
                              {t('common.grade')} {course.grade}
                            </Badge>
                            <h3 className="mt-3 font-display text-xl">{course.title}</h3>
                            {course.summary && (
                              <p className="mt-2 flex-1 text-sm text-ink-600">{course.summary}</p>
                            )}

                            <dl className="mt-5 grid grid-cols-2 gap-x-3 gap-y-2 border-t-2 border-ink-100 pt-4 text-xs">
                              <div className="flex items-center gap-1.5 text-ink-600">
                                <Layers className="h-3.5 w-3.5" aria-hidden="true" />
                                <dt className="sr-only">{t('subject.units')}</dt>
                                <dd>
                                  {course.unit_count} {t('subject.units')}
                                </dd>
                              </div>
                              <div className="flex items-center gap-1.5 text-ink-600">
                                <Target className="h-3.5 w-3.5" aria-hidden="true" />
                                <dt className="sr-only">{t('subject.skills')}</dt>
                                <dd>
                                  {course.skill_count} {t('subject.skills')}
                                </dd>
                              </div>
                              <div className="flex items-center gap-1.5 text-ink-600">
                                <BookOpen className="h-3.5 w-3.5" aria-hidden="true" />
                                <dt className="sr-only">{t('subject.lessons')}</dt>
                                <dd>
                                  {course.lesson_count} {t('subject.lessons')}
                                </dd>
                              </div>
                              <div className="flex items-center gap-1.5 text-ink-600">
                                <Clock className="h-3.5 w-3.5" aria-hidden="true" />
                                <dt className="sr-only">{t('subject.hours')}</dt>
                                <dd>
                                  {course.estimated_hours} {t('subject.hours')}
                                </dd>
                              </div>
                            </dl>

                            <p
                              className={`mt-4 inline-flex items-center gap-1.5 text-sm font-bold ${
                                isPhysics ? 'text-teal-700' : 'text-brand-700'
                              }`}
                            >
                              {t('courses.viewCourse')}
                              <ArrowRight className="h-4 w-4" aria-hidden="true" />
                            </p>
                          </Card>
                        </Link>
                      ))}
                    </div>
                  </section>
                );
              })}
            </div>
          )}
        </Container>
      </Section>
    </MarketingShell>
  );
}
