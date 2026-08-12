import { clsx, type ClassValue } from 'clsx';
import { twMerge } from 'tailwind-merge';

/**
 * Merge Tailwind classes, with later classes winning conflicts.
 *
 * This lives in its own module with **no** `'use client'` directive on purpose. It is a plain
 * function used by both server and client components; if it were exported from a `'use client'`
 * module, calling it from a server component would fail at runtime with "attempted to call a
 * client function from the server".
 */
export function cn(...inputs: ClassValue[]): string {
  return twMerge(clsx(inputs));
}

export type { ClassValue };
