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

  return (
    <SubjectPage
      locale={locale}
      slug="physics"
      intro="Measurement, motion, forces, energy, electricity, waves and the atom — physics taught as a measuring science, where every idea ends in a calculation a student can actually do."
      highlights={[
        {
          title: 'Every idea has a number',
          body: 'Concepts are anchored to a formula students can apply and rearrange. Understanding you can calculate with is understanding you can rely on.',
        },
        {
          title: 'The maths is never the blocker',
          body: 'Physics skills carry prerequisites into the mathematics curriculum. If rearranging equations is the real problem, we send the student there first.',
        },
        {
          title: 'Misconceptions targeted directly',
          body: 'Wrong answers in our multiple choice are the mistakes students actually make, so which option they pick tells a teacher what they believe.',
        },
      ]}
    />
  );
}
