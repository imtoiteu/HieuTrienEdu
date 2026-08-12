import { describe, expect, it } from 'vitest';

import {
  DEFAULT_LOCALE,
  createTranslator,
  formatCurrency,
  isLocale,
  resolveLocale,
} from './index';

describe('createTranslator', () => {
  const dictionary = {
    'common.login': 'Log in',
    'dashboard.welcome': 'Welcome back, {name}',
    'exercise.questionOf': 'Question {current} of {total}',
  };

  it('returns the translation for a known key', () => {
    expect(createTranslator(dictionary)('common.login')).toBe('Log in');
  });

  it('interpolates named values', () => {
    expect(createTranslator(dictionary)('dashboard.welcome', { name: 'An' })).toBe(
      'Welcome back, An',
    );
  });

  it('interpolates several values, including numbers', () => {
    expect(
      createTranslator(dictionary)('exercise.questionOf', { current: 2, total: 5 }),
    ).toBe('Question 2 of 5');
  });

  it('falls back to the fallback dictionary for a missing key', () => {
    // This is what makes a partially translated Vietnamese locale usable rather than broken.
    const vietnamese = createTranslator({ 'common.login': 'Đăng nhập' }, dictionary);
    expect(vietnamese('common.login')).toBe('Đăng nhập');
    expect(vietnamese('dashboard.welcome', { name: 'An' })).toBe('Welcome back, An');
  });

  it('returns the key itself when it is in neither dictionary', () => {
    // Visible and greppable, rather than rendering blank.
    expect(createTranslator(dictionary)('totally.unknown.key')).toBe('totally.unknown.key');
  });

  it('leaves an unmatched placeholder in place rather than printing undefined', () => {
    expect(createTranslator(dictionary)('dashboard.welcome', { other: 'x' })).toBe(
      'Welcome back, {name}',
    );
  });
});

describe('locale resolution', () => {
  it('recognises supported locales', () => {
    expect(isLocale('en')).toBe(true);
    expect(isLocale('vi')).toBe(true);
    expect(isLocale('fr')).toBe(false);
  });

  it('falls back to the default for anything unrecognised', () => {
    expect(resolveLocale('vi')).toBe('vi');
    expect(resolveLocale('klingon')).toBe(DEFAULT_LOCALE);
    expect(resolveLocale(undefined)).toBe(DEFAULT_LOCALE);
    expect(resolveLocale(null)).toBe(DEFAULT_LOCALE);
  });
});

describe('formatCurrency', () => {
  it('formats VND without a decimal part', () => {
    // The đồng has no minor unit, so "450.000,00 ₫" would be wrong — but note that Vietnamese
    // uses "." as the *thousands* separator, so the check has to be on the digits themselves
    // rather than on punctuation.
    const formatted = formatCurrency(450000, 'vi');
    expect(formatted.replace(/\D/g, '')).toBe('450000');
  });

  it('formats the same amount in both locales', () => {
    expect(formatCurrency(2800000, 'en')).toBeTruthy();
    expect(formatCurrency(2800000, 'vi')).toBeTruthy();
  });
});
