'use client';

import Link from 'next/link';
import { AlertTriangle, CheckCircle2, Info, Lightbulb, Play } from 'lucide-react';

import {
  Button,
  Card,
  FractionBars,
  FunctionPlot,
  GeoGebraEmbed,
  MathBlock,
  MathText,
  NumberLine,
  RightTriangleFigure,
  cn,
  type PlotFunction,
} from '@hietedu/ui';

import type { LessonBlock } from '@/lib/api';
import { useI18n } from '@/lib/i18n';

/**
 * Render a lesson's typed content blocks.
 *
 * Unknown block types render nothing rather than crashing the lesson — content is data, and a
 * future block type deployed before the frontend that understands it must degrade quietly.
 */
export function LessonBlocks({ blocks, locale }: { blocks: LessonBlock[]; locale: string }) {
  return (
    <div className="space-y-1">
      {blocks.map((block, index) => (
        <LessonBlockView key={index} block={block} locale={locale} />
      ))}
    </div>
  );
}

function LessonBlockView({ block, locale }: { block: LessonBlock; locale: string }) {
  const { t } = useI18n();

  switch (block.type) {
    case 'text':
      return <Markdown source={String(block.markdown ?? '')} />;

    case 'math':
      return (
        <MathBlock caption={block.caption ? String(block.caption) : undefined}>
          {String(block.latex ?? '')}
        </MathBlock>
      );

    case 'callout': {
      const variant = String(block.variant ?? 'note') as 'tip' | 'warning' | 'note';
      const styles = {
        tip: { box: 'border-teal-300 bg-teal-50', icon: Lightbulb, tone: 'text-teal-700' },
        warning: { box: 'border-coral-300 bg-coral-50', icon: AlertTriangle, tone: 'text-coral-700' },
        note: { box: 'border-brand-200 bg-brand-50', icon: Info, tone: 'text-brand-700' },
      }[variant] ?? { box: 'border-brand-200 bg-brand-50', icon: Info, tone: 'text-brand-700' };
      const Icon = styles.icon;

      return (
        <aside className={cn('my-6 rounded-3xl border-2 p-5', styles.box)}>
          <div className="flex items-start gap-3">
            <Icon className={cn('mt-0.5 h-5 w-5 shrink-0', styles.tone)} aria-hidden="true" />
            <div className="min-w-0">
              <p className="font-display text-lg">
                {block.title
                  ? String(block.title)
                  : t(
                      variant === 'tip'
                        ? 'lesson.tip'
                        : variant === 'warning'
                          ? 'lesson.warning'
                          : 'lesson.note',
                    )}
              </p>
              <p className="mt-1 leading-relaxed text-ink-700">
                <MathText>{String(block.text ?? '')}</MathText>
              </p>
            </div>
          </div>
        </aside>
      );
    }

    case 'example': {
      const steps = (block.steps as { text?: string; math?: string }[] | undefined) ?? [];
      return (
        <Card className="my-6 border-ink-900 shadow-pop-sm">
          <p className="text-xs font-bold uppercase tracking-widest text-brand-700">
            {t('lesson.example')}
          </p>
          {Boolean(block.title) && (
            <h3 className="mt-1.5 font-display text-xl">{String(block.title)}</h3>
          )}
          <ol className="mt-4 space-y-4">
            {steps.map((step, index) => (
              <li key={index} className="flex gap-3">
                <span className="inline-flex h-7 w-7 shrink-0 items-center justify-center rounded-xl bg-brand-100 text-xs font-extrabold text-brand-700">
                  {index + 1}
                </span>
                <div className="min-w-0 flex-1">
                  {step.text && (
                    <p className="text-ink-800">
                      <MathText>{step.text}</MathText>
                    </p>
                  )}
                  {step.math && <MathBlock>{step.math}</MathBlock>}
                </div>
              </li>
            ))}
          </ol>
        </Card>
      );
    }

    case 'table': {
      const headers = (block.headers as string[] | undefined) ?? [];
      const rows = (block.rows as string[][] | undefined) ?? [];
      return (
        <div className="scroll-x my-6 rounded-3xl border-2 border-ink-100">
          <table className="w-full min-w-[32rem] border-collapse text-left text-sm">
            <thead className="bg-ink-50">
              <tr>
                {headers.map((header) => (
                  <th
                    key={header}
                    scope="col"
                    className="border-b-2 border-ink-100 px-4 py-3 font-display text-ink-900"
                  >
                    {header}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map((row, rowIndex) => (
                <tr key={rowIndex} className={rowIndex % 2 ? 'bg-ink-50/40' : undefined}>
                  {row.map((cell, cellIndex) => (
                    <td key={cellIndex} className="border-b border-ink-100 px-4 py-3 text-ink-700">
                      <MathText>{cell}</MathText>
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      );
    }

    case 'interactive': {
      const widget = String(block.widget ?? '');
      const config = (block.config ?? {}) as Record<string, unknown>;

      if (widget === 'function-plot') {
        return (
          <FunctionPlot
            functions={(config.functions ?? []) as PlotFunction[]}
            xRange={config.xRange as [number, number] | undefined}
            yRange={config.yRange as [number, number] | undefined}
            axisLabels={config.axisLabels as { x?: string; y?: string } | undefined}
            caption={config.caption ? String(config.caption) : undefined}
          />
        );
      }
      if (widget === 'fraction-bars') {
        return (
          <FractionBars
            fractions={(config.fractions ?? []) as [number, number][]}
            target={config.target as [number, number] | undefined}
            caption={config.caption ? String(config.caption) : undefined}
          />
        );
      }
      if (widget === 'number-line') {
        return (
          <NumberLine
            min={config.min as number | undefined}
            max={config.max as number | undefined}
            marks={
              (config.marks ?? []) as {
                value: number;
                label?: string;
                tone?: 'brand' | 'coral' | 'teal';
              }[]
            }
            caption={config.caption ? String(config.caption) : undefined}
          />
        );
      }
      if (widget === 'geogebra') {
        return (
          <GeoGebraEmbed
            materialId={config.materialId ? String(config.materialId) : undefined}
            caption={config.caption ? String(config.caption) : undefined}
          />
        );
      }
      return (
        <p className="my-6 rounded-2xl bg-ink-50 p-4 text-sm text-ink-500">
          {t('lesson.interactiveUnavailable')}
        </p>
      );
    }

    case 'figure': {
      const shape = String(block.shape ?? '');
      const config = (block.config ?? {}) as Record<string, unknown>;
      if (shape === 'right-triangle') {
        return (
          <RightTriangleFigure
            base={Number(config.base ?? 4)}
            height={Number(config.height ?? 3)}
            labels={config.labels as { base?: string; height?: string; hypotenuse?: string }}
            caption={config.caption ? String(config.caption) : undefined}
          />
        );
      }
      return null;
    }

    case 'practice': {
      const skill = block.skill ? String(block.skill) : null;
      if (!skill) return null;
      return (
        <Card className="my-6 border-brand-300 bg-brand-50">
          <div className="flex flex-wrap items-center justify-between gap-4">
            <div>
              <p className="font-display text-lg">{t('lesson.practice')}</p>
              {Boolean(block.prompt) && (
                <p className="mt-1 text-sm text-ink-600">{String(block.prompt)}</p>
              )}
            </div>
            <Link href={`/${locale}/practice/${skill}`}>
              <Button variant="coral">
                <Play className="h-4 w-4" aria-hidden="true" />
                {t('dashboard.startPractice')}
              </Button>
            </Link>
          </div>
        </Card>
      );
    }

    case 'summary': {
      const points = (block.points as string[] | undefined) ?? [];
      return (
        <Card className="my-6 border-teal-200 bg-teal-50">
          <p className="font-display text-lg">{t('lesson.summary')}</p>
          <ul className="mt-3 space-y-2">
            {points.map((point, index) => (
              <li key={index} className="flex items-start gap-2.5">
                <CheckCircle2
                  className="mt-0.5 h-4 w-4 shrink-0 text-teal-600"
                  aria-hidden="true"
                />
                <span className="text-sm text-ink-800">
                  <MathText>{point}</MathText>
                </span>
              </li>
            ))}
          </ul>
        </Card>
      );
    }

    default:
      return null;
  }
}

/**
 * A deliberately small Markdown subset: headings, bold, inline code, lists and paragraphs,
 * with `$…$` maths handled by MathText.
 *
 * A full Markdown library would be a larger dependency and a much larger sanitisation surface,
 * for content we author ourselves. Nothing here ever produces raw HTML.
 */
function Markdown({ source }: { source: string }) {
  const blocks = source.trim().split(/\n{2,}/);

  return (
    <div className="space-y-4">
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
            <h2 key={index} className="mt-10 font-display text-2xl">
              {trimmed.slice(3)}
            </h2>
          );
        }

        if (/^[-*] /m.test(trimmed) && trimmed.split('\n').every((line) => /^[-*] /.test(line))) {
          return (
            <ul key={index} className="space-y-2 pl-1">
              {trimmed.split('\n').map((line, lineIndex) => (
                <li key={lineIndex} className="flex items-start gap-2.5">
                  <span
                    className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-brand-400"
                    aria-hidden="true"
                  />
                  <span className="text-ink-700">
                    <Inline text={line.replace(/^[-*] /, '')} />
                  </span>
                </li>
              ))}
            </ul>
          );
        }

        return (
          <p key={index} className="leading-relaxed text-ink-700">
            <Inline text={trimmed} />
          </p>
        );
      })}
    </div>
  );
}

/** Bold, inline code and inline maths within a line of text. */
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
