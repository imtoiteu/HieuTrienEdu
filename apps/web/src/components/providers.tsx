'use client';

import { useEffect, type ReactNode } from 'react';

import type { Dictionary, Locale } from '@hietedu/localization';

import { AuthProvider } from '@/lib/auth';
import { I18nProvider } from '@/lib/i18n';

export function Providers({
  locale,
  dictionary,
  fallback,
  children,
}: {
  locale: Locale;
  dictionary: Dictionary;
  fallback: Dictionary;
  children: ReactNode;
}) {
  // The <html lang> attribute lives above this layout in the tree, so it is set here.
  // Getting it right matters for screen-reader pronunciation and for browser translation.
  useEffect(() => {
    document.documentElement.lang = locale;
  }, [locale]);

  return (
    <I18nProvider locale={locale} dictionary={dictionary} fallback={fallback}>
      <AuthProvider>{children}</AuthProvider>
    </I18nProvider>
  );
}
