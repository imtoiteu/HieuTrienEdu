import Link from 'next/link';
import { notFound } from 'next/navigation';
import { BookOpen, Clock, Layers, Target } from 'lucide-react';

import { isLocale } from '@hietedu/localization';
import { Badge, Card, Container, Section } from '@hietedu/ui';

import { LearningPath } from '@/components/app/learning-path';
import { MarketingShell } from '@/components/site/marketing-shell';
import { api } from '@/lib/api';
import { getTranslator } from '@/lib/dictionaries';

export const dynamic = 'force-dynamic';

export default async function CourseDetailPage({
  params,
}: {
  params: Promise<{ locale: string; slug: string }>;
}) {
  const { locale: raw, slug } = await params;
  const locale = isLocale(raw) ? raw : 'en';
  const t = getTranslator(locale);

  let course;
  try {
    course = await api.curriculum.course(slug, locale);
  } catch {
    notFound();
  }

  const isPhysics = course.subject_slug === 'physics';

  return (
    <MarketingShell locale={locale}>
      <Section className={`${isPhysics ? 'bg-teal-50' : 'bg-lavender'} pb-10 pt-12`}>
        <Container>
          <Link
            href={`/${locale}/courses`}
            className="text-sm font-bold text-ink-600 hover:text-brand-700"
          >
            ← {t('courses.title')}
          </Link>
          <div className="mt-5 flex flex-wrap items-center gap-3">
            <Badge tone={isPhysics ? 'teal' : 'brand'}>
              {t('common.grade')} {course.grade}
            </Badge>
            <Badge tone="neutral">{course.subject_name}</Badge>
          </div>
          <h1 className="mt-4 font-display text-4xl sm:text-5xl">{course.title}</h1>
          {course.description && (
            <p className="mt-4 max-w-3xl text-lg text-ink-600">{course.description}</p>
          )}

          <dl className="mt-7 flex flex-wrap gap-x-8 gap-y-3">
            {[
              { icon: Layers, value: course.unit_count, label: t('subject.units') },
              { icon: Target, value: course.skill_count, label: t('subject.skills') },
              { icon: BookOpen, value: course.lesson_count, label: t('subject.lessons') },
              { icon: Clock, value: course.estimated_hours, label: t('subject.hours') },
            ].map((stat) => (
              <div key={stat.label} className="flex items-center gap-2">
                <stat.icon className="h-4 w-4 text-ink-500" aria-hidden="true" />
                <dt className="sr-only">{stat.label}</dt>
                <dd className="text-sm font-bold text-ink-800">
                  {stat.value} <span className="font-medium text-ink-500">{stat.label}</span>
                </dd>
              </div>
            ))}
          </dl>
        </Container>
      </Section>

      <Section className="pt-10">
        <Container>
          <div className="space-y-12">
            {course.units.map((unit, unitIndex) => (
              <section key={unit.id} aria-labelledby={`unit-${unit.slug}`}>
                <div className="flex items-start gap-4">
                  <span className="inline-flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl border-2 border-ink-900 bg-white font-display text-lg font-extrabold shadow-pop-sm">
                    {unitIndex + 1}
                  </span>
                  <div className="min-w-0">
                    <h2 id={`unit-${unit.slug}`} className="font-display text-2xl">
                      {unit.title}
                    </h2>
                    {unit.summary && <p className="mt-1 text-ink-600">{unit.summary}</p>}
                  </div>
                </div>

                {/* Signed-in students see their real path here; everyone else sees the outline. */}
                <LearningPath
                  unitSlug={unit.slug}
                  locale={locale}
                  fallback={
                    <div className="mt-6 grid gap-4 md:grid-cols-2">
                      {unit.topics.map((topic) => (
                        <Card key={topic.id}>
                          <h3 className="font-display text-lg">{topic.title}</h3>
                          {topic.summary && (
                            <p className="mt-1 text-sm text-ink-600">{topic.summary}</p>
                          )}
                          <ul className="mt-3 space-y-1.5">
                            {topic.skills.map((skill) => (
                              <li
                                key={skill.id}
                                className="flex items-start gap-2 text-sm text-ink-700"
                              >
                                <span
                                  className={`mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full ${
                                    isPhysics ? 'bg-teal-400' : 'bg-brand-400'
                                  }`}
                                  aria-hidden="true"
                                />
                                {skill.name}
                              </li>
                            ))}
                          </ul>
                        </Card>
                      ))}
                    </div>
                  }
                />
              </section>
            ))}
          </div>
        </Container>
      </Section>
    </MarketingShell>
  );
}
