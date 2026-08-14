import { readFileSync, readdirSync, statSync } from 'node:fs';
import path from 'node:path';

import { describe, expect, it } from 'vitest';

import en from './en.json';
import vi from './vi.json';

/**
 * The dictionaries and the code that uses them, checked against each other.
 *
 * Both halves of this matter, and the second is the one that failed in practice. A localisation
 * pass added keys for the admin screens and never wired most of them up: 281 keys sat in both
 * dictionaries, fully translated, while the components next to them still rendered the English
 * literal. Nothing failed, nothing warned, and the admin stayed half-English for as long as
 * anybody looked at it.
 *
 * A key nobody reads is not harmless — it is a translation somebody wrote, believing it would
 * show up.
 */

const SRC = path.resolve(__dirname, '..');

function sourceFiles(dir: string, out: string[] = []): string[] {
  for (const entry of readdirSync(dir)) {
    const full = path.join(dir, entry);
    if (statSync(full).isDirectory()) {
      sourceFiles(full, out);
    } else if (/\.tsx?$/.test(entry) && !/\.test\.tsx?$/.test(entry)) {
      out.push(full);
    }
  }
  return out;
}

const source = sourceFiles(SRC)
  .map((file) => readFileSync(file, 'utf8'))
  .join('\n');

// Keys reached by name, and the prefixes of keys built at run time (`admin.st.${status}`).
const referenced = new Set(source.match(/[a-zA-Z0-9_]+(?:\.[a-zA-Z0-9_]+)+/g) ?? []);
const computedPrefixes = [...(source.match(/[`'"]([a-zA-Z0-9_.]+)\.\$\{/g) ?? [])].map((match) =>
  match.replace(/^[`'"]/, '').replace(/\.\$\{$/, ''),
);

describe('message dictionaries', () => {
  it('define the same keys in every language', () => {
    // `_meta.note` documents the file for translators and has no English counterpart.
    const enKeys = new Set(Object.keys(en));
    const viKeys = new Set(Object.keys(vi).filter((key) => key !== '_meta.note'));
    expect([...viKeys].filter((key) => !enKeys.has(key))).toEqual([]);
    expect([...enKeys].filter((key) => !viKeys.has(key))).toEqual([]);
  });

  it('take the same placeholders in every language', () => {
    const placeholders = (value: unknown) =>
      typeof value === 'string' ? [...value.matchAll(/\{(\w+)\}/g)].map((m) => m[1]).sort() : [];
    const mismatched = Object.keys(en).filter(
      (key) =>
        key in vi &&
        placeholders(en[key as keyof typeof en]).join() !==
          placeholders(vi[key as keyof typeof vi]).join(),
    );
    // A missing placeholder renders as a sentence with a hole in it, only in one language.
    expect(mismatched).toEqual([]);
  });

  it('are all actually used by a component', () => {
    const unused = Object.keys(en).filter(
      (key) =>
        !referenced.has(key) && !computedPrefixes.some((prefix) => key.startsWith(`${prefix}.`)),
    );
    expect(
      unused,
      'These keys are translated but nothing renders them. Either wire the key up where the ' +
        'English is still hardcoded, or delete it — a dictionary nobody reads stops being ' +
        'evidence that the interface is translated.',
    ).toEqual([]);
  });
});
