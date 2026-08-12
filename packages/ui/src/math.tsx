'use client';

import katex from 'katex';
import { useMemo } from 'react';

import { cn } from './cn';

/**
 * Mathematical notation rendering, backed by KaTeX.
 *
 * KaTeX rather than MathJax: it renders synchronously and roughly an order of magnitude faster,
 * which matters because a practice session re-renders notation on every question. KaTeX also has
 * no runtime dependency on a CDN once its stylesheet is bundled.
 *
 * `throwOnError: false` is deliberate. A malformed formula in one lesson should render as
 * highlighted source text, not blank the whole page.
 */

export function MathInline({ children, className }: { children: string; className?: string }) {
  const html = useMemo(
    () =>
      katex.renderToString(children, {
        displayMode: false,
        throwOnError: false,
        errorColor: '#DC2626',
        strict: false,
        trust: false,
      }),
    [children],
  );
  return (
    <span
      className={cn('katex-inline', className)}
      // KaTeX output is generated from author-controlled content with trust:false, which
      // disables \href and \includegraphics — the only injection vectors it exposes.
      dangerouslySetInnerHTML={{ __html: html }}
    />
  );
}

export function MathBlock({
  children,
  className,
  caption,
}: {
  children: string;
  className?: string;
  caption?: string;
}) {
  const html = useMemo(
    () =>
      katex.renderToString(children, {
        displayMode: true,
        throwOnError: false,
        errorColor: '#DC2626',
        strict: false,
        trust: false,
      }),
    [children],
  );
  return (
    <figure className={cn('my-6', className)}>
      <div
        className="scroll-x rounded-2xl bg-lavender px-5 py-4 text-center"
        dangerouslySetInnerHTML={{ __html: html }}
      />
      {caption && (
        <figcaption className="mt-2 text-center text-sm text-ink-500">{caption}</figcaption>
      )}
    </figure>
  );
}

/**
 * Render text that mixes prose with `$…$` inline maths and `$$…$$` display maths.
 *
 * Question prompts come from the database as plain strings that may contain either, so this is
 * the component the exercise player uses for every prompt, hint and solution step.
 */
export function MathText({ children, className }: { children: string; className?: string }) {
  const parts = useMemo(() => splitMath(children), [children]);

  return (
    <span className={className}>
      {parts.map((part, index) => {
        if (part.type === 'text') {
          return <span key={index}>{part.value}</span>;
        }
        if (part.type === 'block') {
          return <MathBlock key={index}>{part.value}</MathBlock>;
        }
        return <MathInline key={index}>{part.value}</MathInline>;
      })}
    </span>
  );
}

type MathPart = { type: 'text' | 'inline' | 'block'; value: string };

/**
 * Split a string into prose and maths segments.
 *
 * Written by hand rather than with one regex because `$$` must be matched before `$` — a single
 * alternation would tear a display block in half at its first dollar.
 */
export function splitMath(input: string): MathPart[] {
  const parts: MathPart[] = [];
  let buffer = '';
  let index = 0;

  const flush = () => {
    if (buffer) {
      parts.push({ type: 'text', value: buffer });
      buffer = '';
    }
  };

  while (index < input.length) {
    const isEscaped = index > 0 && input[index - 1] === '\\';

    if (input.startsWith('$$', index) && !isEscaped) {
      const end = input.indexOf('$$', index + 2);
      if (end !== -1) {
        flush();
        parts.push({ type: 'block', value: input.slice(index + 2, end).trim() });
        index = end + 2;
        continue;
      }
    }

    if (input[index] === '$' && !isEscaped) {
      const end = input.indexOf('$', index + 1);
      if (end !== -1) {
        flush();
        parts.push({ type: 'inline', value: input.slice(index + 1, end).trim() });
        index = end + 1;
        continue;
      }
    }

    buffer += input[index];
    index += 1;
  }

  flush();
  return parts;
}
