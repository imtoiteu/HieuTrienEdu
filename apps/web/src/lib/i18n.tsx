'use client';

import { createContext, useContext, useMemo, type ReactNode } from 'react';

import { setClientLocale } from './api';

import {
  DEFAULT_LOCALE,
  type Dictionary,
  type Locale,
  type Translator,
  createTranslator,
  formatCurrency,
  formatDate,
  formatDateTime,
  formatNumber,
  formatRelativeDay,
  formatTime,
} from '@hietedu/localization';

interface I18nContextValue {
  locale: Locale;
  t: Translator;
  formatNumber: (value: number) => string;
  formatCurrency: (value: number) => string;
  formatDate: (value: string | Date, options?: Intl.DateTimeFormatOptions) => string;
  formatTime: (value: string | Date) => string;
  formatDateTime: (value: string | Date) => string;
  formatRelativeDay: (value: string | Date) => string;
}

const I18nContext = createContext<I18nContextValue | null>(null);

export function I18nProvider({
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
  const value = useMemo<I18nContextValue>(() => {
    // Tell the API client which language to request content in. Done here rather than in an
    // effect so the very first client-side fetch already carries the right locale.
    setClientLocale(locale);
    const t = createTranslator(dictionary, fallback);
    return {
      locale,
      t,
      formatNumber: (value) => formatNumber(value, locale),
      formatCurrency: (value) => formatCurrency(value, locale),
      formatDate: (value, options) => formatDate(value, locale, options),
      formatTime: (value) => formatTime(value, locale),
      formatDateTime: (value) => formatDateTime(value, locale),
      formatRelativeDay: (value) =>
        formatRelativeDay(value, locale, {
          today: t('common.today'),
          tomorrow: t('common.tomorrow'),
        }),
    };
  }, [locale, dictionary, fallback]);

  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>;
}

export function useI18n(): I18nContextValue {
  const context = useContext(I18nContext);
  if (!context) {
    throw new Error('useI18n must be used inside an I18nProvider');
  }
  return context;
}

/** Convenience hook for the common case of only needing the translator. */
export function useTranslations(): Translator {
  return useI18n().t;
}

/** Prefix a path with the active locale, e.g. localeHref('en', '/courses') -> '/en/courses'. */
export function localeHref(locale: Locale | string, path: string): string {
  const normalised = path.startsWith('/') ? path : `/${path}`;
  return `/${locale ?? DEFAULT_LOCALE}${normalised === '/' ? '' : normalised}`;
}
