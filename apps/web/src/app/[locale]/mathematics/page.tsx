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
  return { title: t('nav.mathematics') };
}

export default async function MathematicsPage({
  params,
}: {
  params: Promise<{ locale: string }>;
}) {
  const { locale: raw } = await params;
  const locale = isLocale(raw) ? raw : 'en';
  const t = getTranslator(locale);

  return (
    <SubjectPage
      locale={locale}
      slug="mathematics"
      intro={t('subject.mathematics.intro')}
      highlights={[
        { title: t('subject.mathematics.h1.title'), body: t('subject.mathematics.h1.body') },
        { title: t('subject.mathematics.h2.title'), body: t('subject.mathematics.h2.body') },
        { title: t('subject.mathematics.h3.title'), body: t('subject.mathematics.h3.body') },
      ]}
    />
  );
}
