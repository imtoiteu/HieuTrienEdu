import type { ReactNode } from 'react';

import { Container, Eyebrow, Section } from '@hietedu/ui';

/** Shared hero band for interior marketing pages. */
export function PageHeader({
  eyebrow,
  title,
  subtitle,
  tone = 'lavender',
  children,
}: {
  eyebrow?: string;
  title: string;
  subtitle?: string;
  tone?: 'lavender' | 'teal' | 'coral' | 'sun';
  children?: ReactNode;
}) {
  const tones = {
    lavender: 'bg-lavender',
    teal: 'bg-teal-50',
    coral: 'bg-coral-50',
    sun: 'bg-sun-50',
  };
  const eyebrowTone = {
    lavender: 'brand',
    teal: 'teal',
    coral: 'coral',
    sun: 'sun',
  } as const;

  return (
    <Section className={`${tones[tone]} pb-10 pt-14`}>
      <Container>
        {eyebrow && <Eyebrow tone={eyebrowTone[tone]}>{eyebrow}</Eyebrow>}
        <h1 className="mt-5 font-display text-4xl sm:text-5xl lg:text-6xl">{title}</h1>
        {subtitle && <p className="mt-5 max-w-2xl text-lg text-ink-600 sm:text-xl">{subtitle}</p>}
        {children}
      </Container>
    </Section>
  );
}
