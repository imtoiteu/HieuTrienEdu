'use client';

import { useId, useMemo } from 'react';

import { cn } from './cn';

/**
 * Dependency-free interactive figures.
 *
 * These exist because GeoGebra — the obvious choice for interactive maths — requires a
 * commercial licence for a platform that charges course fees (see docs/OPEN_SOURCE_RESEARCH.md).
 * Rather than make lessons depend on an integration we may not be licensed to ship, interactive
 * content is built on plain SVG here, and GeoGebra is an optional enhancement.
 *
 * Everything renders server-side, works without JavaScript, and scales cleanly on a phone.
 */

/* --------------------------------------------------------------------------------------
 * Function plot
 * ------------------------------------------------------------------------------------ */

export interface PlotFunction {
  /** A JavaScript-ish arithmetic expression in `x`, e.g. "2*x + 1". */
  expression: string;
  label?: string;
  color?: 'primary' | 'accent' | 'teal' | 'muted';
}

const PLOT_COLORS: Record<string, string> = {
  primary: '#6D4AFF',
  accent: '#FF7A45',
  teal: '#00B8A9',
  muted: '#8B82A8',
};

/**
 * Evaluate a plotting expression safely.
 *
 * Only arithmetic over `x` plus a small function whitelist is permitted; anything else returns
 * NaN and simply does not plot. Lesson content is authored by us, but it arrives through the
 * database, and `new Function` on database content would be a straightforward XSS.
 */
function compile(expression: string): (x: number) => number {
  const tokens = expression.match(/[a-zA-Z_]+/g) ?? [];
  const allowed = new Set(['x', 'sin', 'cos', 'tan', 'sqrt', 'abs', 'pow', 'exp', 'log', 'PI', 'E']);
  if (tokens.some((token) => !allowed.has(token))) {
    return () => Number.NaN;
  }
  if (/[^0-9a-zA-Z_+\-*/%.,()^\s]/.test(expression)) {
    return () => Number.NaN;
  }

  const body = expression.replace(/\^/g, '**');
  try {
    // eslint-disable-next-line no-new-func -- input is whitelisted character-by-character above
    const fn = new Function(
      'x',
      'sin', 'cos', 'tan', 'sqrt', 'abs', 'pow', 'exp', 'log', 'PI', 'E',
      `"use strict"; return (${body});`,
    ) as (...args: unknown[]) => number;
    return (x: number) => {
      try {
        const value = fn(
          x, Math.sin, Math.cos, Math.tan, Math.sqrt, Math.abs, Math.pow, Math.exp, Math.log,
          Math.PI, Math.E,
        );
        return typeof value === 'number' ? value : Number.NaN;
      } catch {
        return Number.NaN;
      }
    };
  } catch {
    return () => Number.NaN;
  }
}

export function FunctionPlot({
  functions,
  xRange = [-6, 6],
  yRange = [-6, 6],
  axisLabels,
  caption,
  className,
}: {
  functions: PlotFunction[];
  xRange?: [number, number];
  yRange?: [number, number];
  axisLabels?: { x?: string; y?: string };
  caption?: string;
  className?: string;
}) {
  const width = 480;
  const height = 320;
  const [xMin, xMax] = xRange;
  const [yMin, yMax] = yRange;

  const toSvgX = (x: number) => ((x - xMin) / (xMax - xMin)) * width;
  const toSvgY = (y: number) => height - ((y - yMin) / (yMax - yMin)) * height;

  const paths = useMemo(
    () =>
      functions.map((fn) => {
        const evaluate = compile(fn.expression);
        const steps = 240;
        const segments: string[] = [];
        let current: string[] = [];

        for (let index = 0; index <= steps; index += 1) {
          const x = xMin + ((xMax - xMin) * index) / steps;
          const y = evaluate(x);
          // Break the path at discontinuities and off-screen excursions rather than drawing a
          // vertical line across the whole chart, which is what a naive plotter does at an
          // asymptote.
          if (!Number.isFinite(y) || y < yMin - (yMax - yMin) || y > yMax + (yMax - yMin)) {
            if (current.length > 1) segments.push(current.join(' '));
            current = [];
            continue;
          }
          current.push(
            `${current.length === 0 ? 'M' : 'L'} ${toSvgX(x).toFixed(2)} ${toSvgY(y).toFixed(2)}`,
          );
        }
        if (current.length > 1) segments.push(current.join(' '));

        return { ...fn, d: segments.join(' ') };
      }),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [functions, xMin, xMax, yMin, yMax],
  );

  const xTicks = useMemo(() => niceTicks(xMin, xMax), [xMin, xMax]);
  const yTicks = useMemo(() => niceTicks(yMin, yMax), [yMin, yMax]);

  const description = functions.map((fn) => fn.label ?? fn.expression).join(', ');

  return (
    <figure className={cn('my-6', className)}>
      <div className="scroll-x rounded-3xl border-2 border-ink-100 bg-white p-4">
        <svg
          viewBox={`0 0 ${width} ${height}`}
          className="h-auto w-full min-w-[320px]"
          role="img"
          aria-label={`Graph showing ${description}`}
        >
          {/* grid */}
          {xTicks.map((tick) => (
            <line
              key={`gx-${tick}`}
              x1={toSvgX(tick)}
              y1={0}
              x2={toSvgX(tick)}
              y2={height}
              stroke="#EDEBF3"
              strokeWidth={1}
            />
          ))}
          {yTicks.map((tick) => (
            <line
              key={`gy-${tick}`}
              x1={0}
              y1={toSvgY(tick)}
              x2={width}
              y2={toSvgY(tick)}
              stroke="#EDEBF3"
              strokeWidth={1}
            />
          ))}

          {/* axes */}
          {yMin <= 0 && yMax >= 0 && (
            <line x1={0} y1={toSvgY(0)} x2={width} y2={toSvgY(0)} stroke="#B5AECB" strokeWidth={2} />
          )}
          {xMin <= 0 && xMax >= 0 && (
            <line x1={toSvgX(0)} y1={0} x2={toSvgX(0)} y2={height} stroke="#B5AECB" strokeWidth={2} />
          )}

          {/* tick labels */}
          {xTicks.filter((t) => t !== 0).map((tick) => (
            <text
              key={`tx-${tick}`}
              x={toSvgX(tick)}
              y={Math.min(height - 4, toSvgY(0) + 14)}
              textAnchor="middle"
              className="fill-ink-400"
              fontSize={11}
            >
              {tick}
            </text>
          ))}
          {yTicks.filter((t) => t !== 0).map((tick) => (
            <text
              key={`ty-${tick}`}
              x={Math.max(4, toSvgX(0) - 6)}
              y={toSvgY(tick) + 4}
              textAnchor="end"
              className="fill-ink-400"
              fontSize={11}
            >
              {tick}
            </text>
          ))}

          {paths.map((path, index) => (
            <path
              key={index}
              d={path.d}
              fill="none"
              stroke={PLOT_COLORS[path.color ?? 'primary'] ?? PLOT_COLORS.primary}
              strokeWidth={3}
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          ))}

          {axisLabels?.x && (
            <text x={width - 6} y={toSvgY(0) - 8} textAnchor="end" className="fill-ink-500" fontSize={12}>
              {axisLabels.x}
            </text>
          )}
          {axisLabels?.y && (
            <text x={toSvgX(0) + 8} y={14} className="fill-ink-500" fontSize={12}>
              {axisLabels.y}
            </text>
          )}
        </svg>

        {functions.some((fn) => fn.label) && (
          <ul className="mt-3 flex flex-wrap justify-center gap-x-5 gap-y-2">
            {functions.map((fn, index) => (
              <li key={index} className="flex items-center gap-2 text-sm font-semibold text-ink-700">
                <span
                  className="h-1 w-6 rounded-full"
                  style={{ background: PLOT_COLORS[fn.color ?? 'primary'] }}
                  aria-hidden="true"
                />
                {fn.label ?? fn.expression}
              </li>
            ))}
          </ul>
        )}
      </div>
      {caption && <figcaption className="mt-2 text-sm text-ink-500">{caption}</figcaption>}
    </figure>
  );
}

function niceTicks(min: number, max: number): number[] {
  const span = max - min;
  const step = span <= 12 ? 1 : span <= 30 ? 5 : span <= 120 ? 20 : Math.ceil(span / 8);
  const ticks: number[] = [];
  for (let value = Math.ceil(min / step) * step; value <= max; value += step) {
    ticks.push(Number(value.toFixed(4)));
  }
  return ticks;
}

/* --------------------------------------------------------------------------------------
 * Fraction bars
 * ------------------------------------------------------------------------------------ */

export function FractionBars({
  fractions,
  target,
  caption,
  className,
}: {
  /** Pairs of [numerator, denominator]. */
  fractions: [number, number][];
  /** Optional result bar, e.g. the sum. */
  target?: [number, number];
  caption?: string;
  className?: string;
}) {
  const rows = target ? [...fractions, target] : fractions;
  const colors = ['bg-brand-400', 'bg-coral-400', 'bg-teal-400', 'bg-sun-400'];

  return (
    <figure className={cn('my-6', className)}>
      <div className="space-y-4 rounded-3xl border-2 border-ink-100 bg-white p-5">
        {rows.map(([numerator, denominator], rowIndex) => {
          const isTarget = target && rowIndex === rows.length - 1;
          return (
            <div key={rowIndex} className={cn(isTarget && 'border-t-2 border-dashed border-ink-200 pt-4')}>
              <div className="mb-1.5 flex items-center gap-2 text-sm font-bold text-ink-700">
                <span>
                  {numerator}/{denominator}
                </span>
                {isTarget && <span className="text-ink-400">= the result</span>}
              </div>
              <div
                className="flex gap-1"
                role="img"
                aria-label={`${numerator} out of ${denominator} parts shaded`}
              >
                {Array.from({ length: denominator }, (_, index) => (
                  <div
                    key={index}
                    className={cn(
                      'h-9 flex-1 rounded-lg border-2 border-ink-900/15',
                      index < numerator
                        ? colors[rowIndex % colors.length]
                        : 'bg-ink-50',
                    )}
                  />
                ))}
              </div>
            </div>
          );
        })}
      </div>
      {caption && <figcaption className="mt-2 text-sm text-ink-500">{caption}</figcaption>}
    </figure>
  );
}

/* --------------------------------------------------------------------------------------
 * Geometry figure
 * ------------------------------------------------------------------------------------ */

export function RightTriangleFigure({
  base,
  height: triangleHeight,
  labels,
  caption,
  className,
}: {
  base: number;
  height: number;
  labels?: { base?: string; height?: string; hypotenuse?: string };
  caption?: string;
  className?: string;
}) {
  const id = useId();
  const scale = 46;
  const padding = 44;
  const w = base * scale + padding * 2;
  const h = triangleHeight * scale + padding * 2;
  const originX = padding;
  const originY = h - padding;

  return (
    <figure className={cn('my-6', className)}>
      <div className="scroll-x rounded-3xl border-2 border-ink-100 bg-white p-4">
        <svg
          viewBox={`0 0 ${w} ${h}`}
          className="h-auto w-full max-w-md"
          role="img"
          aria-label={`Right-angled triangle with base ${base} and height ${triangleHeight}`}
        >
          <polygon
            points={`${originX},${originY} ${originX + base * scale},${originY} ${originX},${originY - triangleHeight * scale}`}
            fill="#F3F0FF"
            stroke="#6D4AFF"
            strokeWidth={3}
            strokeLinejoin="round"
          />
          {/* right-angle marker */}
          <path
            d={`M ${originX} ${originY - 16} L ${originX + 16} ${originY - 16} L ${originX + 16} ${originY}`}
            fill="none"
            stroke="#6D4AFF"
            strokeWidth={2}
          />
          <text
            x={originX + (base * scale) / 2}
            y={originY + 24}
            textAnchor="middle"
            className="fill-ink-700"
            fontSize={14}
            fontWeight={700}
          >
            {labels?.base ?? base}
          </text>
          <text
            x={originX - 10}
            y={originY - (triangleHeight * scale) / 2}
            textAnchor="end"
            className="fill-ink-700"
            fontSize={14}
            fontWeight={700}
          >
            {labels?.height ?? triangleHeight}
          </text>
          <text
            x={originX + (base * scale) / 2 + 14}
            y={originY - (triangleHeight * scale) / 2 - 8}
            className="fill-brand-700"
            fontSize={14}
            fontWeight={700}
            key={id}
          >
            {labels?.hypotenuse ?? ''}
          </text>
        </svg>
      </div>
      {caption && <figcaption className="mt-2 text-sm text-ink-500">{caption}</figcaption>}
    </figure>
  );
}

/* --------------------------------------------------------------------------------------
 * Number line
 * ------------------------------------------------------------------------------------ */

export function NumberLine({
  min = -10,
  max = 10,
  marks = [],
  caption,
  className,
}: {
  min?: number;
  max?: number;
  marks?: { value: number; label?: string; tone?: 'brand' | 'coral' | 'teal' }[];
  caption?: string;
  className?: string;
}) {
  const width = 520;
  const height = 90;
  const toX = (value: number) => 24 + ((value - min) / (max - min)) * (width - 48);
  const tones = { brand: '#6D4AFF', coral: '#FF7A45', teal: '#00B8A9' };

  const ticks: number[] = [];
  const step = max - min <= 20 ? 1 : Math.ceil((max - min) / 20);
  for (let value = min; value <= max; value += step) ticks.push(value);

  return (
    <figure className={cn('my-6', className)}>
      <div className="scroll-x rounded-3xl border-2 border-ink-100 bg-white p-4">
        <svg viewBox={`0 0 ${width} ${height}`} className="h-auto w-full min-w-[320px]" role="img"
          aria-label={`Number line from ${min} to ${max}`}>
          <line x1={16} y1={44} x2={width - 16} y2={44} stroke="#3E3853" strokeWidth={3} />
          {ticks.map((tick) => (
            <g key={tick}>
              <line x1={toX(tick)} y1={38} x2={toX(tick)} y2={50} stroke="#8B82A8" strokeWidth={2} />
              <text x={toX(tick)} y={68} textAnchor="middle" className="fill-ink-500" fontSize={11}>
                {tick}
              </text>
            </g>
          ))}
          {marks.map((mark, index) => (
            <g key={index}>
              <circle cx={toX(mark.value)} cy={44} r={9} fill={tones[mark.tone ?? 'brand']}
                stroke="#1A1633" strokeWidth={2} />
              {mark.label && (
                <text x={toX(mark.value)} y={24} textAnchor="middle" className="fill-ink-800"
                  fontSize={13} fontWeight={700}>
                  {mark.label}
                </text>
              )}
            </g>
          ))}
        </svg>
      </div>
      {caption && <figcaption className="mt-2 text-sm text-ink-500">{caption}</figcaption>}
    </figure>
  );
}
