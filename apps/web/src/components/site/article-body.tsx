'use client';

import { MathText } from '@hietedu/ui';

/**
 * Renders a blog article's Markdown.
 *
 * Same deliberately-small subset as the lesson renderer: headings, bold, inline code, lists and
 * paragraphs. Articles are written by the centre's own staff through the admin dashboard, so the
 * value of a full Markdown engine does not justify its sanitisation surface — and nothing here
 * can emit raw HTML.
 */
export function ArticleBody({ markdown }: { markdown: string }) {
  const blocks = markdown.trim().split(/\n{2,}/);

  return (
    <div className="space-y-5">
      {blocks.map((block, index) => {
        const trimmed = block.trim();

        if (trimmed.startsWith('### ')) {
          return (
            <h3 key={index} className="mt-8 font-display text-xl">
              {trimmed.slice(4)}
            </h3>
          );
        }
        if (trimmed.startsWith('## ')) {
          return (
            <h2 key={index} className="mt-10 font-display text-2xl sm:text-3xl">
              {trimmed.slice(3)}
            </h2>
          );
        }

        const lines = trimmed.split('\n');
        if (lines.every((line) => /^[-*] /.test(line))) {
          return (
            <ul key={index} className="space-y-2.5">
              {lines.map((line, lineIndex) => (
                <li key={lineIndex} className="flex items-start gap-3">
                  <span
                    className="mt-2.5 h-1.5 w-1.5 shrink-0 rounded-full bg-brand-400"
                    aria-hidden="true"
                  />
                  <span className="text-lg leading-relaxed text-ink-700">
                    <Inline text={line.replace(/^[-*] /, '')} />
                  </span>
                </li>
              ))}
            </ul>
          );
        }

        return (
          <p key={index} className="text-lg leading-relaxed text-ink-700">
            <Inline text={trimmed} />
          </p>
        );
      })}
    </div>
  );
}

function Inline({ text }: { text: string }) {
  const parts = text.split(/(\*\*[^*]+\*\*|`[^`]+`)/g);
  return (
    <>
      {parts.map((part, index) => {
        if (part.startsWith('**') && part.endsWith('**')) {
          return (
            <strong key={index} className="font-bold text-ink-900">
              {part.slice(2, -2)}
            </strong>
          );
        }
        if (part.startsWith('`') && part.endsWith('`')) {
          return (
            <code
              key={index}
              className="rounded-md bg-ink-100 px-1.5 py-0.5 font-mono text-[0.9em] text-ink-800"
            >
              {part.slice(1, -1)}
            </code>
          );
        }
        return <MathText key={index}>{part}</MathText>;
      })}
    </>
  );
}
