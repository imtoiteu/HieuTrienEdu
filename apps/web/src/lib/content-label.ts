'use client';

import { useCallback } from 'react';

import type { Translations } from './admin-api';
import { useI18n } from './i18n';

/**
 * Reading admin-managed content in the administrator's own language.
 *
 * The public site never needs this: the API localises content for whoever asks. The admin is the
 * one place that cannot, because the English column is the field the form *edits* — sending the
 * Vietnamese title in `title` would make the next save overwrite the English with it. So the admin
 * API returns both, and the screen decides which to show:
 *
 * * a **row's own fields** — course title, lesson title, skill name — come as the English column
 *   plus a `translations` blob, and are displayed through this helper;
 * * a **parent's name** borrowed for display — `subject_name`, `topic_title`, `breadcrumb` — is
 *   already localised by the API, because there is no form field to round-trip.
 *
 * Without this the admin showed "Mathematics — Grade 6 · Whole Numbers and Operations" to someone
 * working entirely in Vietnamese, on content that had a perfectly good Vietnamese title sitting in
 * the same response.
 */

/**
 * `translations` is optional on purpose: the constraint is "a content row", and rows that have
 * no translations at all are exactly the fallback case this helper exists to handle.
 */
function bucket(row: object, locale: string): Record<string, unknown> {
  return ((row as { translations?: Translations | null }).translations?.[locale] ?? {}) as Record<
    string,
    unknown
  >;
}

/** The value of `field` in `locale`, or the English column when there is no translation. */
export function contentLabel<T extends object>(
  row: T | null | undefined,
  field: keyof T & string,
  locale: string,
): string {
  if (!row) return '';
  const source = row[field];
  const english = typeof source === 'string' ? source : '';
  const translated = bucket(row, locale)[field];
  // An empty string in the blob means "not translated yet", not "deliberately blank" — the same
  // rule the API's `localise` applies, so both sides agree on what counts as translated.
  if (typeof translated === 'string' && translated.trim()) return translated;
  return english;
}

/**
 * Whether `field` has no translation in `locale` and is therefore falling back to English.
 *
 * Worth surfacing rather than hiding: an administrator working in Vietnamese who sees an English
 * title needs to know whether that is the content or the fallback, and the fallback is silent.
 */
export function isUntranslated<T extends object>(
  row: T | null | undefined,
  field: keyof T & string,
  locale: string,
): boolean {
  if (!row || locale === 'en') return false;
  const translated = bucket(row, locale)[field];
  return !(typeof translated === 'string' && translated.trim());
}

/** `contentLabel` bound to the locale the administrator is working in. */
export function useContentLabel() {
  const { locale } = useI18n();
  return useCallback(
    <T extends object>(row: T | null | undefined, field: keyof T & string) =>
      contentLabel(row, field, locale),
    [locale],
  );
}

/** `isUntranslated` bound to the locale the administrator is working in. */
export function useIsUntranslated() {
  const { locale } = useI18n();
  return useCallback(
    <T extends object>(row: T | null | undefined, field: keyof T & string) =>
      isUntranslated(row, field, locale),
    [locale],
  );
}
