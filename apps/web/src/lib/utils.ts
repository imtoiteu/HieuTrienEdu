import { clsx, type ClassValue } from 'clsx';
import { twMerge } from 'tailwind-merge';

/** Merge Tailwind classes, with later classes winning conflicts. */
export function cn(...inputs: ClassValue[]): string {
  return twMerge(clsx(inputs));
}

/** Colour tokens for a subject, so every surface uses the same mapping. */
export const SUBJECT_THEME: Record<
  string,
  { bg: string; text: string; border: string; bar: string; soft: string; ring: string }
> = {
  mathematics: {
    bg: 'bg-brand-500',
    text: 'text-brand-700',
    border: 'border-brand-200',
    bar: 'bg-brand-500',
    soft: 'bg-brand-50',
    ring: 'ring-brand-500/30',
  },
  physics: {
    bg: 'bg-teal-500',
    text: 'text-teal-700',
    border: 'border-teal-200',
    bar: 'bg-teal-500',
    soft: 'bg-teal-50',
    ring: 'ring-teal-500/30',
  },
};

export function subjectTheme(slug: string | null | undefined) {
  return SUBJECT_THEME[slug ?? ''] ?? SUBJECT_THEME.mathematics;
}

export function masteryPercent(value: number): number {
  return Math.round(Math.max(0, Math.min(1, value)) * 100);
}

/** Difficulty 1-5 rendered as a short human label. */
export const DIFFICULTY_LABELS = [
  'Foundation',
  'Foundation',
  'Developing',
  'Secure',
  'Advanced',
  'Challenge',
];

export function difficultyLabel(level: number): string {
  return DIFFICULTY_LABELS[Math.max(1, Math.min(5, level))] ?? 'Developing';
}

/** Split a numeric range into an array — used for star ratings and skeleton lists. */
export function range(length: number): number[] {
  return Array.from({ length }, (_, index) => index);
}

export function initials(name: string): string {
  return name
    .trim()
    .split(/\s+/)
    .slice(-2)
    .map((part) => part[0]?.toUpperCase() ?? '')
    .join('');
}

/**
 * Deterministic pastel background for an avatar, derived from the name.
 * Same name always gets the same colour, so a teacher looks consistent across pages.
 */
export function avatarColor(name: string): string {
  const palette = [
    'bg-brand-200 text-brand-800',
    'bg-teal-200 text-teal-800',
    'bg-coral-200 text-coral-800',
    'bg-sun-200 text-sun-800',
    'bg-ink-200 text-ink-800',
  ];
  let hash = 0;
  for (let index = 0; index < name.length; index += 1) {
    hash = (hash * 31 + name.charCodeAt(index)) >>> 0;
  }
  return palette[hash % palette.length];
}
