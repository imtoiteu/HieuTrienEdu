import en from '@/messages/en.json';
import vi from '@/messages/vi.json';

import {
  DEFAULT_LOCALE,
  type Dictionary,
  type Locale,
  createTranslator,
  type Translator,
} from '@hietedu/localization';

const DICTIONARIES: Record<Locale, Dictionary> = {
  en: en as Dictionary,
  vi: vi as Dictionary,
};

export function getDictionary(locale: Locale): Dictionary {
  return DICTIONARIES[locale] ?? DICTIONARIES[DEFAULT_LOCALE];
}

export function getFallbackDictionary(): Dictionary {
  return DICTIONARIES[DEFAULT_LOCALE];
}

/**
 * Server-side translator, for use in server components and metadata generation.
 * Client components use `useTranslations()` from `@/lib/i18n` instead.
 */
export function getTranslator(locale: Locale): Translator {
  return createTranslator(getDictionary(locale), getFallbackDictionary());
}
