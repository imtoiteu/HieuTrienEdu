import { notFound } from 'next/navigation';
import type { ReactNode } from 'react';

import { LOCALES, isLocale } from '@hietedu/localization';

import { Providers } from '@/components/providers';
import { getDictionary, getFallbackDictionary, getTranslator } from '@/lib/dictionaries';

export function generateStaticParams() {
  return LOCALES.map((locale) => ({ locale }));
}

export async function generateMetadata({ params }: { params: Promise<{ locale: string }> }) {
  const { locale } = await params;
  if (!isLocale(locale)) return {};
  const t = getTranslator(locale);
  return {
    title: {
      default: `${t('brand.name')} — ${t('brand.tagline')}`,
      template: `%s · ${t('brand.name')}`,
    },
    description: t('home.hero.subtitle'),
    alternates: {
      languages: Object.fromEntries(LOCALES.map((code) => [code, `/${code}`])),
    },
  };
}

export default async function LocaleLayout({
  children,
  params,
}: {
  children: ReactNode;
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params;
  if (!isLocale(locale)) {
    notFound();
  }

  return (
    <Providers
      locale={locale}
      dictionary={getDictionary(locale)}
      fallback={getFallbackDictionary()}
    >
      {children}
    </Providers>
  );
}
