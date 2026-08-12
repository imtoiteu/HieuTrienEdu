import { describe, expect, it } from 'vitest';

import { splitMath } from './math';

/**
 * `splitMath` is the parser behind every question prompt, hint and solution step, so its edge
 * cases matter more than its happy path — a mis-split prompt renders as raw LaTeX in front of a
 * student mid-question.
 */
describe('splitMath', () => {
  it('returns plain text unchanged', () => {
    expect(splitMath('What is the answer?')).toEqual([
      { type: 'text', value: 'What is the answer?' },
    ]);
  });

  it('extracts inline maths', () => {
    expect(splitMath('Solve $x + 1 = 5$ for x.')).toEqual([
      { type: 'text', value: 'Solve ' },
      { type: 'inline', value: 'x + 1 = 5' },
      { type: 'text', value: ' for x.' },
    ]);
  });

  it('extracts display maths', () => {
    expect(splitMath('Recall: $$a^2 + b^2 = c^2$$')).toEqual([
      { type: 'text', value: 'Recall: ' },
      { type: 'block', value: 'a^2 + b^2 = c^2' },
    ]);
  });

  it('matches $$ before $ so a display block is not torn in half', () => {
    // A single alternation would split "$$a$$" at its first dollar and produce nonsense.
    const parts = splitMath('$$\\frac{1}{2}$$');
    expect(parts).toHaveLength(1);
    expect(parts[0].type).toBe('block');
  });

  it('handles several segments in one string', () => {
    const parts = splitMath('First $a$ then $b$ done');
    expect(parts.map((part) => part.type)).toEqual([
      'text',
      'inline',
      'text',
      'inline',
      'text',
    ]);
  });

  it('leaves an unclosed delimiter as literal text rather than swallowing the rest', () => {
    expect(splitMath('Costs $5 to enter')).toEqual([
      { type: 'text', value: 'Costs $5 to enter' },
    ]);
  });

  it('ignores an escaped dollar sign', () => {
    const parts = splitMath('Price is \\$10 today');
    expect(parts).toHaveLength(1);
    expect(parts[0].type).toBe('text');
  });

  it('handles an empty string', () => {
    expect(splitMath('')).toEqual([]);
  });
});
