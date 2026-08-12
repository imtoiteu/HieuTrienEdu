import { isLocale } from '@hietedu/localization';

import { SubjectPage } from '@/components/site/subject-page';

export const dynamic = 'force-dynamic';
export const metadata = { title: 'Mathematics' };

export default async function MathematicsPage({
  params,
}: {
  params: Promise<{ locale: string }>;
}) {
  const { locale: raw } = await params;
  const locale = isLocale(raw) ? raw : 'en';

  return (
    <SubjectPage
      locale={locale}
      slug="mathematics"
      intro="From place value to quadratics and trigonometry — a complete grade 6 to 9 curriculum where every skill is built on the ones beneath it, and nothing is skipped."
      highlights={[
        {
          title: 'Fractions taught properly',
          body: 'The single biggest predictor of later algebra success. We separate equivalence, comparison and the four operations, and gate each on the one before.',
        },
        {
          title: 'Algebra without the cliff',
          body: 'Variables, then substitution, then one-step, two-step and multi-step equations. Students meet each idea only once the previous one is secure.',
        },
        {
          title: 'Practice that adapts',
          body: 'Question difficulty tracks the student. Too easy wastes time; too hard destroys confidence. The engine aims just above current mastery.',
        },
      ]}
    />
  );
}
