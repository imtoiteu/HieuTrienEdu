import Link from 'next/link';
import { Award, Globe, GraduationCap, Star } from 'lucide-react';

import { isLocale } from '@hietedu/localization';
import { Avatar, Badge, Button, Card, Container, Section } from '@hietedu/ui';

import { PageHeader } from '@/components/site/page-header';
import { MarketingShell } from '@/components/site/marketing-shell';
import { api, type TeacherCard, type TeacherProfileSummary } from '@/lib/api';
import { getTranslator } from '@/lib/dictionaries';
import { safe } from '@/lib/server-api';

export const dynamic = 'force-dynamic';
export const metadata = { title: 'Teachers' };

const WEEKDAYS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];

export default async function TeachersPage({ params }: { params: Promise<{ locale: string }> }) {
  const { locale: raw } = await params;
  const locale = isLocale(raw) ? raw : 'en';
  const t = getTranslator(locale);

  // Published profiles are the source of truth for the public roster. Fall back to the older
  // endpoint so the page still lists teachers on a database where nobody has been published yet.
  const profiles = await safe(api.tutoring.profiles(), [] as TeacherProfileSummary[]);
  const slugById = new Map(profiles.map((profile) => [profile.id, profile.slug]));
  const teachers = await safe(api.tutoring.teachers(), [] as TeacherCard[]);
  const featured = teachers.filter((teacher) => teacher.is_featured);
  const others = teachers.filter((teacher) => !teacher.is_featured);

  return (
    <MarketingShell>
      <PageHeader
        eyebrow={t('nav.teachers')}
        title={t('teachers.title')}
        subtitle={t('teachers.subtitle')}
      />

      <Section className="pt-10">
        <Container>
          {teachers.length === 0 ? (
            <Card className="text-center">
              <p className="text-ink-600">{t('common.emptyState')}</p>
            </Card>
          ) : (
            <>
              {featured.length > 0 && (
                <div className="grid gap-6 lg:grid-cols-2">
                  {featured.map((teacher) => (
                    <TeacherProfileCard
                      key={teacher.id}
                      teacher={teacher}
                      slug={slugById.get(teacher.id) ?? null}
                      locale={locale}
                      t={t}
                      featured
                    />
                  ))}
                </div>
              )}

              {others.length > 0 && (
                <div className="mt-8 grid gap-6 md:grid-cols-2 lg:grid-cols-3">
                  {others.map((teacher) => (
                    <TeacherProfileCard
                      key={teacher.id}
                      teacher={teacher}
                      slug={slugById.get(teacher.id) ?? null}
                      locale={locale}
                      t={t}
                    />
                  ))}
                </div>
              )}
            </>
          )}
        </Container>
      </Section>
    </MarketingShell>
  );
}

function TeacherProfileCard({
  teacher,
  slug,
  locale,
  t,
  featured,
}: {
  teacher: TeacherCard;
  /** Present only when the administrator has published this teacher's profile page. */
  slug: string | null;
  locale: string;
  t: (key: string, values?: Record<string, string | number>) => string;
  featured?: boolean;
}) {
  return (
    <Card className={featured ? 'border-ink-900 shadow-pop' : undefined}>
      <div className="flex items-start gap-4">
        <Avatar name={teacher.full_name} src={teacher.avatar_url} size={featured ? 'xl' : 'lg'} />
        <div className="min-w-0 flex-1">
          <h2 className="font-display text-xl">
            {slug ? (
              <Link
                href={`/${locale}/teachers/${slug}`}
                className="hover:text-brand-700 hover:underline"
              >
                {teacher.full_name}
              </Link>
            ) : (
              teacher.full_name
            )}
          </h2>
          {teacher.headline && (
            <p className="mt-0.5 text-sm font-semibold text-brand-700">{teacher.headline}</p>
          )}
          <div className="mt-2 flex flex-wrap items-center gap-2">
            {teacher.rating > 0 && (
              <span className="flex items-center gap-1 text-sm font-bold text-ink-700">
                <Star className="h-4 w-4 fill-sun-400 text-sun-400" aria-hidden="true" />
                {teacher.rating.toFixed(1)}
                <span className="font-normal text-ink-500">({teacher.rating_count})</span>
              </span>
            )}
            <Badge tone="neutral">
              {t('teachers.experience', { years: teacher.years_experience })}
            </Badge>
          </div>
        </div>
      </div>

      {teacher.bio && <p className="mt-4 text-sm leading-relaxed text-ink-600">{teacher.bio}</p>}

      <dl className="mt-5 space-y-3 border-t-2 border-ink-100 pt-4 text-sm">
        <div className="flex flex-wrap items-baseline gap-2">
          <dt className="font-bold text-ink-800">{t('teachers.subjects')}:</dt>
          <dd className="flex flex-wrap gap-1.5">
            {teacher.subjects.map((subject) => (
              <Badge key={subject} tone={subject === 'physics' ? 'teal' : 'brand'}>
                {t(`subject.${subject}.title`)}
              </Badge>
            ))}
          </dd>
        </div>
        <div className="flex flex-wrap items-baseline gap-2">
          <dt className="font-bold text-ink-800">{t('teachers.grades')}:</dt>
          <dd className="text-ink-600">{teacher.grades.join(', ')}</dd>
        </div>
        {teacher.languages.length > 0 && (
          <div className="flex flex-wrap items-baseline gap-2">
            <dt className="flex items-center gap-1.5 font-bold text-ink-800">
              <Globe className="h-3.5 w-3.5" aria-hidden="true" />
              {t('teachers.languages')}:
            </dt>
            <dd className="text-ink-600">{teacher.languages.join(', ')}</dd>
          </div>
        )}
        {teacher.qualifications.length > 0 && (
          <div>
            <dt className="flex items-center gap-1.5 font-bold text-ink-800">
              <GraduationCap className="h-3.5 w-3.5" aria-hidden="true" />
              {t('teachers.qualifications')}
            </dt>
            <dd className="mt-1.5">
              <ul className="space-y-1">
                {teacher.qualifications.map((qualification) => (
                  <li key={qualification} className="flex items-start gap-2 text-ink-600">
                    <Award className="mt-0.5 h-3.5 w-3.5 shrink-0 text-sun-500" aria-hidden="true" />
                    {qualification}
                  </li>
                ))}
              </ul>
            </dd>
          </div>
        )}
        {teacher.availability.length > 0 && (
          <div className="flex flex-wrap items-baseline gap-2">
            <dt className="font-bold text-ink-800">{t('teachers.availability')}:</dt>
            <dd className="flex flex-wrap gap-1.5">
              {teacher.availability.map((slot, index) => (
                <span
                  key={index}
                  className="rounded-lg bg-ink-100 px-2 py-1 text-xs font-semibold text-ink-700"
                >
                  {WEEKDAYS[slot.weekday % 7]} {slot.start}–{slot.end}
                </span>
              ))}
            </dd>
          </div>
        )}
      </dl>

      <div className="mt-5 flex flex-wrap gap-2">
        {slug && (
          <Link href={`/${locale}/teachers/${slug}`}>
            <Button variant="outline">{t('common.viewAll')}</Button>
          </Link>
        )}
        {teacher.accepts_one_to_one && (
          <Link href={`/${locale}/contact?teacher=${teacher.id}`}>
            <Button variant="coral">{t('teachers.bookLesson')}</Button>
          </Link>
        )}
      </div>
    </Card>
  );
}
