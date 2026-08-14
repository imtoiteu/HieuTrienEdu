import { describe, expect, it } from 'vitest';

import { contentLabel, isUntranslated } from './content-label';

/**
 * The admin is the one screen that has to choose between an English column and its translation.
 *
 * The public API makes that choice server-side, but an admin form *edits* the English column, so
 * the row must carry both — and the screen decides which to show. Getting this wrong in either
 * direction is a real bug: showing English to a Vietnamese administrator (what shipped), or
 * showing the Vietnamese in the field they are about to save over.
 */
describe('contentLabel', () => {
  const course = {
    title: 'Mathematics — Grade 6',
    summary: 'Whole numbers and operations',
    translations: { vi: { title: 'Toán học — Lớp 6' } },
  };

  it('shows the translation in the language being worked in', () => {
    expect(contentLabel(course, 'title', 'vi')).toBe('Toán học — Lớp 6');
  });

  it('leaves English alone', () => {
    expect(contentLabel(course, 'title', 'en')).toBe('Mathematics — Grade 6');
  });

  it('falls back to the English column rather than rendering nothing', () => {
    expect(contentLabel(course, 'summary', 'vi')).toBe('Whole numbers and operations');
  });

  it('treats an empty translation as "not translated yet", matching the API', () => {
    const row = { title: 'Fractions', translations: { vi: { title: '   ' } } };
    expect(contentLabel(row, 'title', 'vi')).toBe('Fractions');
  });

  it('survives a row with no translations at all', () => {
    const untranslatedRow = { title: 'Fractions' };
    expect(contentLabel(untranslatedRow, 'title', 'vi')).toBe('Fractions');
    expect(contentLabel<typeof untranslatedRow>(null, 'title', 'vi')).toBe('');
  });

  it('reports the fallback, because English on a Vietnamese screen is otherwise ambiguous', () => {
    expect(isUntranslated(course, 'title', 'vi')).toBe(false);
    expect(isUntranslated(course, 'summary', 'vi')).toBe(true);
    // Nothing is "untranslated" in the language the content is authored in.
    expect(isUntranslated(course, 'summary', 'en')).toBe(false);
  });
});
