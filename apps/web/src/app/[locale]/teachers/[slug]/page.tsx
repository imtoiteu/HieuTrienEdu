import Link from 'next/link';
import { notFound } from 'next/navigation';
import {
  Award,
  BookOpen,
  CalendarDays,
  GraduationCap,
  Globe,
  Mail,
  Phone,
  Sparkles,
  Star,
  Trophy,
} from 'lucide-react';

import { formatCurrency, isLocale } from '@hietedu/localization';
import { Avatar, Badge, Button, Card, Container, Eyebrow, Section } from '@hietedu/ui';

import { MarketingShell } from '@/components/site/marketing-shell';
import { api, type TeacherCredentialPublic, type TeacherProfileDetail } from '@/lib/api';
import { getTranslator } from '@/lib/dictionaries';

export const dynamic = 'force-dynamic';



/**
 * A teacher's public page, generated entirely from admin-managed data.
 *
 * Every section below is driven by rows an administrator can edit — the biography, the structured
 * education and awards, the courses taught, the formats offered. Nothing about an individual
 * teacher is written in this file, which is the point: adding a teacher or an award never needs a
 * developer.
 */
export async function generateMetadata({
  params,
}: {
  params: Promise<{ locale: string; slug: string }>;
}) {
  const { locale, slug } = await params;
  try {
    const teacher = await api.tutoring.profile(slug, locale);
    return {
      title: teacher.full_name,
      description: teacher.headline ?? undefined,
    };
  } catch {
    return { title: 'Teacher' };
  }
}

export default async function TeacherProfilePage({
  params,
}: {
  params: Promise<{ locale: string; slug: string }>;
}) {
  const { locale: raw, slug } = await params;
  const locale = isLocale(raw) ? raw : 'en';
  const t = getTranslator(locale);
  const href = (path: string) => `/${locale}${path}`;

  let teacher: TeacherProfileDetail;
  try {
    teacher = await api.tutoring.profile(slug, locale);
  } catch {
    // A missing or unpublished profile is a 404, not an error page: unpublishing a teacher must
    // not leave a broken-looking page behind.
    notFound();
  }

  const credentialSections: { kind: string; label: string; icon: typeof Award }[] = [
    { kind: 'education', label: t('admin.tp.education'), icon: GraduationCap },
    { kind: 'experience', label: t('admin.tp.experience'), icon: BookOpen },
    { kind: 'award', label: t('admin.tp.awards'), icon: Trophy },
    { kind: 'competition', label: t('admin.tp.competitions'), icon: Trophy },
    { kind: 'certification', label: t('admin.tp.certifications'), icon: Award },
    { kind: 'publication', label: t('admin.tp.publications'), icon: BookOpen },
  ];

  return (
    <MarketingShell locale={locale}>
      {/* ---------------------------------------------------------------- header */}
      <Section className="bg-gradient-to-b from-lavender via-cream to-cream pt-12">
        <Container>
          <div className="grid items-start gap-8 lg:grid-cols-[auto_1fr]">
            <Avatar name={teacher.full_name} src={teacher.photo_url} size="xl" />
            <div className="min-w-0">
              {teacher.is_featured && (
                <Eyebrow tone="coral">
                  <Sparkles className="h-3.5 w-3.5" aria-hidden="true" />{t('admin.tp.featured')}</Eyebrow>
              )}
              <h1 className="mt-3 font-display text-4xl sm:text-5xl">{teacher.full_name}</h1>
              {teacher.headline && (
                <p className="mt-3 max-w-2xl text-lg text-ink-600">{teacher.headline}</p>
              )}

              <div className="mt-5 flex flex-wrap items-center gap-2">
                {teacher.subjects.map((subject) => (
                  <Badge key={subject} tone="brand">
                    {subject}
                  </Badge>
                ))}
                {teacher.grades.length > 0 && (
                  <Badge tone="neutral">Grades {teacher.grades.join(', ')}</Badge>
                )}
                {teacher.years_experience > 0 && (
                  <Badge tone="teal">{teacher.years_experience} years teaching</Badge>
                )}
                {teacher.rating_count > 0 && (
                  <span className="inline-flex items-center gap-1 text-sm font-bold text-ink-700">
                    <Star className="h-4 w-4 fill-sun-400 text-sun-500" aria-hidden="true" />
                    {teacher.rating.toFixed(1)}
                    <span className="font-normal text-ink-500">
                      ({teacher.rating_count} reviews)
                    </span>
                  </span>
                )}
              </div>

              <div className="mt-7 flex flex-col gap-3 sm:flex-row">
                <Link href={href('/contact')}>
                  <Button size="lg" variant="coral" className="w-full sm:w-auto">{t('admin.tp.requestConsultation')}</Button>
                </Link>
                {teacher.accepts_one_to_one && (
                  <Link href={href('/tutoring/one-to-one')}>
                    <Button size="lg" variant="outline" className="w-full sm:w-auto">{t('admin.tp.bookOneToOne')}</Button>
                  </Link>
                )}
              </div>
            </div>
          </div>
        </Container>
      </Section>

      <Section className="pt-10">
        <Container>
          <div className="grid gap-8 lg:grid-cols-[1fr_20rem]">
            <div className="min-w-0 space-y-8">
              {/* about */}
              {teacher.bio && (
                <section aria-labelledby="about-heading">
                  <h2 id="about-heading" className="font-display text-2xl">
                    About {teacher.full_name}
                  </h2>
                  <div className="mt-3 space-y-3 leading-relaxed text-ink-700">
                    {teacher.bio.split(/\n{2,}/).map((paragraph, index) => (
                      <p key={index}>{paragraph}</p>
                    ))}
                  </div>
                </section>
              )}

              {/* video */}
              {teacher.video_intro_url && (
                <section aria-labelledby="video-heading">
                  <h2 id="video-heading" className="font-display text-2xl">{t('admin.tp.introduction')}</h2>
                  <div className="mt-3 aspect-video overflow-hidden rounded-3xl border-2 border-ink-900">
                    <iframe
                      src={teacher.video_intro_url}
                      title={`Introduction from ${teacher.full_name}`}
                      className="h-full w-full"
                      allow="accelerometer; autoplay; clipboard-write; encrypted-media; picture-in-picture"
                      allowFullScreen
                    />
                  </div>
                </section>
              )}

              {/* structured background */}
              {credentialSections
                .filter((section) => (teacher.credentials[section.kind] ?? []).length > 0)
                .map((section) => (
                  <section key={section.kind} aria-labelledby={`${section.kind}-heading`}>
                    <h2
                      id={`${section.kind}-heading`}
                      className="flex items-center gap-2 font-display text-2xl"
                    >
                      <section.icon className="h-5 w-5 text-brand-500" aria-hidden="true" />
                      {section.label}
                    </h2>
                    <ul className="mt-3 space-y-3">
                      {teacher.credentials[section.kind].map(
                        (entry: TeacherCredentialPublic) => (
                          <li key={entry.id}>
                            <Card>
                              <div className="flex flex-wrap items-baseline justify-between gap-2">
                                <p className="font-bold text-ink-900">{entry.title}</p>
                                {(entry.year_start || entry.year_end) && (
                                  <span className="text-sm font-semibold text-ink-500">
                                    {entry.year_start}
                                    {entry.year_end ? `–${entry.year_end}` : ''}
                                  </span>
                                )}
                              </div>
                              {entry.organisation && (
                                <p className="text-sm text-ink-600">{entry.organisation}</p>
                              )}
                              {entry.description && (
                                <p className="mt-2 text-sm text-ink-700">{entry.description}</p>
                              )}
                              {entry.url && (
                                <a
                                  href={entry.url}
                                  target="_blank"
                                  rel="noreferrer"
                                  className="mt-2 inline-block text-sm font-bold text-brand-600 hover:underline"
                                >{t('admin.tp.readMore')}</a>
                              )}
                            </Card>
                          </li>
                        ),
                      )}
                    </ul>
                  </section>
                ))}

              {/* teaching approach */}
              {(teacher.teaching_philosophy || teacher.teaching_style) && (
                <section aria-labelledby="approach-heading">
                  <h2 id="approach-heading" className="font-display text-2xl">{t('admin.tp.approach')}</h2>
                  <div className="mt-3 grid gap-4 sm:grid-cols-2">
                    {teacher.teaching_philosophy && (
                      <Card>
                        <p className="text-xs font-extrabold uppercase tracking-widest text-brand-700">{t('admin.tp.philosophy')}</p>
                        <p className="mt-2 leading-relaxed text-ink-700">
                          {teacher.teaching_philosophy}
                        </p>
                      </Card>
                    )}
                    {teacher.teaching_style && (
                      <Card>
                        <p className="text-xs font-extrabold uppercase tracking-widest text-brand-700">{t('admin.tp.style')}</p>
                        <p className="mt-2 leading-relaxed text-ink-700">
                          {teacher.teaching_style}
                        </p>
                      </Card>
                    )}
                  </div>
                </section>
              )}

              {/* courses */}
              {teacher.courses.length > 0 && (
                <section aria-labelledby="courses-heading">
                  <h2 id="courses-heading" className="font-display text-2xl">{t('admin.tp.coursesTaught')}</h2>
                  <ul className="mt-3 grid gap-3 sm:grid-cols-2">
                    {teacher.courses.map((course) => (
                      <li key={course.id}>
                        <Link href={href(`/courses/${course.slug}`)}>
                          <Card className="h-full transition-shadow hover:shadow-pop-sm">
                            <p className="font-bold text-ink-900">{course.title}</p>
                            <p className="text-sm text-ink-500">Grade {course.grade}</p>
                          </Card>
                        </Link>
                      </li>
                    ))}
                  </ul>
                </section>
              )}

              {/* open classes */}
              {teacher.classes.length > 0 && (
                <section aria-labelledby="classes-heading">
                  <h2 id="classes-heading" className="font-display text-2xl">{t('admin.tp.openClasses')}</h2>
                  <ul className="mt-3 space-y-2">
                    {teacher.classes.map((group) => (
                      <li key={group.id}>
                        <Card className="flex flex-wrap items-center gap-3">
                          <CalendarDays
                            className="h-5 w-5 shrink-0 text-brand-500"
                            aria-hidden="true"
                          />
                          <div className="min-w-0 flex-1">
                            <p className="truncate font-bold text-ink-900">{group.name}</p>
                            <p className="text-sm text-ink-500">
                              {group.format.replace(/_/g, ' ')} ·{' '}
                              {group.delivery_mode.replace(/_/g, ' ')}
                            </p>
                          </div>
                          <Link href={href('/contact')}>
                            <Button size="sm" variant="outline">{t('admin.tp.enquire')}</Button>
                          </Link>
                        </Card>
                      </li>
                    ))}
                  </ul>
                </section>
              )}

              {/* gallery */}
              {teacher.gallery.length > 0 && (
                <section aria-labelledby="gallery-heading">
                  <h2 id="gallery-heading" className="font-display text-2xl">{t('admin.tp.gallery')}</h2>
                  <ul className="mt-3 grid gap-3 sm:grid-cols-3">
                    {teacher.gallery.map((item, index) => (
                      <li key={index}>
                        {/* eslint-disable-next-line @next/next/no-img-element */}
                        <img
                          src={item.url}
                          alt={item.caption ?? ''}
                          className="h-40 w-full rounded-2xl border-2 border-ink-100 object-cover"
                        />
                        {item.caption && (
                          <p className="mt-1 text-xs text-ink-500">{item.caption}</p>
                        )}
                      </li>
                    ))}
                  </ul>
                </section>
              )}
            </div>

            {/* ------------------------------------------------------------ sidebar */}
            <aside className="space-y-4">
              {teacher.programs.length > 0 && (
                <Card>
                  <h2 className="font-display text-lg">{t('admin.tp.learningFormats')}</h2>
                  <ul className="mt-3 space-y-3">
                    {teacher.programs.map((program) => (
                      <li key={program.id} className="border-b border-ink-100 pb-3 last:border-0">
                        <p className="font-bold text-ink-900">{program.name}</p>
                        <p className="text-xs text-ink-500">
                          {program.format.replace(/_/g, ' ')} ·{' '}
                          {program.delivery_mode.replace(/_/g, ' ')}
                        </p>
                        <p className="mt-1 font-display text-lg text-brand-700">
                          {formatCurrency(program.price_vnd, locale)}
                          <span className="text-xs font-normal text-ink-500">
                            /{program.price_unit}
                          </span>
                        </p>
                      </li>
                    ))}
                  </ul>
                </Card>
              )}

              {teacher.learning_formats.length > 0 && (
                <Card>
                  <h2 className="font-display text-lg">{t('admin.tp.availableFormats')}</h2>
                  <ul className="mt-3 flex flex-wrap gap-1.5">
                    {teacher.learning_formats.map((format) => (
                      <li key={format}>
                        <Badge tone="brand">{format.replace(/_/g, ' ')}</Badge>
                      </li>
                    ))}
                  </ul>
                </Card>
              )}

              {teacher.specializations.length > 0 && (
                <Card>
                  <h2 className="font-display text-lg">{t('admin.tp.specialisations')}</h2>
                  <ul className="mt-3 flex flex-wrap gap-1.5">
                    {teacher.specializations.map((item) => (
                      <li key={item}>
                        <Badge tone="neutral">{item}</Badge>
                      </li>
                    ))}
                  </ul>
                </Card>
              )}

              {teacher.availability.length > 0 && (
                <Card>
                  <h2 className="font-display text-lg">{t('admin.tp.availability')}</h2>
                  <ul className="mt-3 space-y-1 text-sm">
                    {teacher.availability.map((slot, index) => (
                      <li key={index}>
                        <span className="font-semibold">{t(`common.weekdayShort.${Number(slot.weekday) % 7}`)}</span>{' '}
                        {slot.start}–{slot.end}
                      </li>
                    ))}
                  </ul>
                </Card>
              )}

              {teacher.languages.length > 0 && (
                <Card>
                  <h2 className="flex items-center gap-2 font-display text-lg">
                    <Globe className="h-4 w-4 text-brand-500" aria-hidden="true" />{t('admin.tp.languages')}</h2>
                  <p className="mt-2 text-sm text-ink-700">{teacher.languages.join(', ')}</p>
                </Card>
              )}

              <Card className="border-ink-900 shadow-pop">
                <h2 className="font-display text-lg">{t('admin.tp.getInTouch')}</h2>
                <p className="mt-1 text-sm text-ink-600">{t('admin.tp.getInTouchBody')}</p>
                <div className="mt-4 space-y-2">
                  <Link href={href('/contact')} className="block">
                    <Button variant="coral" className="w-full">{t('admin.tp.requestConsultation')}</Button>
                  </Link>
                  {teacher.contact.email && (
                    <a href={`mailto:${teacher.contact.email}`} className="block">
                      <Button variant="outline" className="w-full justify-start">
                        <Mail className="h-4 w-4" aria-hidden="true" />
                        {teacher.contact.email}
                      </Button>
                    </a>
                  )}
                  {teacher.contact.phone && (
                    <a href={`tel:${teacher.contact.phone}`} className="block">
                      <Button variant="outline" className="w-full justify-start">
                        <Phone className="h-4 w-4" aria-hidden="true" />
                        {teacher.contact.phone}
                      </Button>
                    </a>
                  )}
                </div>
                {Object.keys(teacher.social_links).length > 0 && (
                  <div className="mt-4 flex flex-wrap gap-2">
                    {Object.entries(teacher.social_links).map(([name, url]) => (
                      <a
                        key={name}
                        href={url}
                        target="_blank"
                        rel="noreferrer"
                        className="text-sm font-bold capitalize text-brand-600 hover:underline"
                      >
                        {name}
                      </a>
                    ))}
                  </div>
                )}
              </Card>

              <p className="text-center text-xs text-ink-400">{t('brand.name')}</p>
            </aside>
          </div>
        </Container>
      </Section>
    </MarketingShell>
  );
}
