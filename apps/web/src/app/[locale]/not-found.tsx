'use client';

import Link from 'next/link';

import { Button, Container, Squiggle } from '@hietedu/ui';

import { MarketingShell } from '@/components/site/marketing-shell';
import { useI18n } from '@/lib/i18n';

export default function NotFound() {
  const { t, locale } = useI18n();

  return (
    <MarketingShell>
      <Container className="flex min-h-[60vh] flex-col items-center justify-center py-20 text-center">
        <p className="font-display text-8xl text-brand-300">404</p>
        <Squiggle className="mt-2 h-4 w-40" tone="#FFC53D" />
        <h1 className="mt-6 font-display text-3xl sm:text-4xl">{t('error.404.title')}</h1>
        <p className="mt-3 max-w-md text-ink-600">{t('error.404.body')}</p>
        <div className="mt-8 flex flex-wrap justify-center gap-3">
          <Link href={`/${locale}`}>
            <Button size="lg">{t('error.404.home')}</Button>
          </Link>
          <Link href={`/${locale}/courses`}>
            <Button size="lg" variant="outline">
              {t('nav.courses')}
            </Button>
          </Link>
        </div>
      </Container>
    </MarketingShell>
  );
}
