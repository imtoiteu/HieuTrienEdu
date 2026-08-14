import { isLocale } from '@hietedu/localization';

import { SubjectPage } from '@/components/site/subject-page';
import { getTranslator } from '@/lib/dictionaries';

export const dynamic = 'force-dynamic';
/** The tab title is content too: a Vietnamese visitor should not see an English one. */
export async function generateMetadata({
  params,
}: {
  params: Promise<{ locale: string }>;
}) {
  const { locale: raw } = await params;
  const t = getTranslator(isLocale(raw) ? raw : 'en');
  return { title: t('nav.physics') };
}

export default async function PhysicsPage({ params }: { params: Promise<{ locale: string }> }) {
  const { locale: raw } = await params;
  const locale = isLocale(raw) ? raw : 'en';
  const t = getTranslator(locale);

  return (
    <SubjectPage
      locale={locale}
      slug="physics"
      intro={t('subject.physics.intro')}
      highlights={[
        { title: t('subject.physics.h1.title'), body: t('subject.physics.h1.body') },
        { title: t('subject.physics.h2.title'), body: t('subject.physics.h2.body') },
        { title: t('subject.physics.h3.title'), body: t('subject.physics.h3.body') },
      ]}
    />
  );
}
