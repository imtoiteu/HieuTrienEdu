/**
 * Internationalisation for HieuTrienEducation.
 *
 * English is complete today; Vietnamese is the intended primary language and is scaffolded so it
 * can be finished by translating one dictionary file, with no component changes.
 *
 * The rule enforced across the codebase: **components never contain user-facing literals.** They
 * call `t('some.key')`. Missing keys fall back to the English string, then to the key itself, so
 * a partially-translated locale degrades to readable English rather than blank UI.
 */

export const LOCALES = ['en', 'vi'] as const;
export type Locale = (typeof LOCALES)[number];
export const DEFAULT_LOCALE: Locale = 'en';

export const LOCALE_NAMES: Record<Locale, string> = {
  en: 'English',
  vi: 'Tiếng Việt',
};

export const LOCALE_FLAGS: Record<Locale, string> = {
  en: '🇬🇧',
  vi: '🇻🇳',
};

export function isLocale(value: string): value is Locale {
  return (LOCALES as readonly string[]).includes(value);
}

export function resolveLocale(value: string | undefined | null): Locale {
  return value && isLocale(value) ? value : DEFAULT_LOCALE;
}

/** A translation dictionary is a flat map of dotted keys to strings. */
export type Dictionary = Record<string, string>;

export type Translator = (key: string, values?: Record<string, string | number>) => string;

/**
 * Build a translator over a dictionary, with a fallback dictionary behind it.
 *
 * Supports `{name}` interpolation, which covers every case in this product. Deliberately no
 * plural rules engine yet: English and Vietnamese pluralise very differently, and guessing at
 * an API before the Vietnamese copy exists would be the wrong call. Where a count is involved,
 * the key carries the phrasing.
 */
export function createTranslator(dictionary: Dictionary, fallback: Dictionary = {}): Translator {
  return (key, values) => {
    const template = dictionary[key] ?? fallback[key] ?? key;
    if (!values) return template;
    return template.replace(/\{(\w+)\}/g, (match, name: string) =>
      name in values ? String(values[name]) : match,
    );
  };
}

/** Locale-aware number formatting. */
export function formatNumber(value: number, locale: Locale = DEFAULT_LOCALE): string {
  return new Intl.NumberFormat(locale === 'vi' ? 'vi-VN' : 'en-GB').format(value);
}

/** Vietnamese đồng has no minor unit, so amounts are always whole numbers. */
export function formatCurrency(amountVnd: number, locale: Locale = DEFAULT_LOCALE): string {
  return new Intl.NumberFormat(locale === 'vi' ? 'vi-VN' : 'en-GB', {
    style: 'currency',
    currency: 'VND',
    maximumFractionDigits: 0,
  }).format(amountVnd);
}

export function formatDate(
  value: string | Date,
  locale: Locale = DEFAULT_LOCALE,
  options: Intl.DateTimeFormatOptions = { day: 'numeric', month: 'short', year: 'numeric' },
): string {
  const date = typeof value === 'string' ? new Date(value) : value;
  if (Number.isNaN(date.getTime())) return '';
  return new Intl.DateTimeFormat(locale === 'vi' ? 'vi-VN' : 'en-GB', options).format(date);
}

export function formatTime(value: string | Date, locale: Locale = DEFAULT_LOCALE): string {
  return formatDate(value, locale, { hour: '2-digit', minute: '2-digit' });
}

export function formatDateTime(value: string | Date, locale: Locale = DEFAULT_LOCALE): string {
  return formatDate(value, locale, {
    day: 'numeric',
    month: 'short',
    hour: '2-digit',
    minute: '2-digit',
  });
}

/** Relative day label used on dashboards ("Today", "Tomorrow", or a date). */
export function formatRelativeDay(
  value: string | Date,
  locale: Locale = DEFAULT_LOCALE,
  labels: { today: string; tomorrow: string } = { today: 'Today', tomorrow: 'Tomorrow' },
): string {
  const date = typeof value === 'string' ? new Date(value) : value;
  if (Number.isNaN(date.getTime())) return '';
  const startOfDay = (d: Date) => new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime();
  const days = Math.round((startOfDay(date) - startOfDay(new Date())) / 86_400_000);
  if (days === 0) return labels.today;
  if (days === 1) return labels.tomorrow;
  return formatDate(date, locale, { weekday: 'short', day: 'numeric', month: 'short' });
}
