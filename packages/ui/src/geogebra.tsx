'use client';

import { useEffect, useRef, useState } from 'react';

import { cn } from './cn';

/**
 * Optional GeoGebra embed — **disabled by default**.
 *
 * GeoGebra's licence permits use of its materials for non-commercial purposes only; any
 * commercial use "is subject to and requires a special license" (https://www.geogebra.org/license).
 * HieuTrienEducation charges course fees, so shipping GeoGebra to paying students would require
 * a License and Collaboration Agreement with GeoGebra first.
 *
 * This component therefore loads nothing unless `NEXT_PUBLIC_GEOGEBRA_ENABLED` is explicitly
 * `true`. With the flag off it renders an honest notice rather than an empty box, so the
 * licensing decision stays visible instead of quietly turning into a broken lesson.
 *
 * Nothing in the seeded curriculum depends on this component — interactive maths is served by
 * the dependency-free SVG widgets in `interactive.tsx`.
 */

export const GEOGEBRA_ENABLED = process.env.NEXT_PUBLIC_GEOGEBRA_ENABLED === 'true';

const DEPLOY_SCRIPT_URL = 'https://www.geogebra.org/apps/deployggb.js';

declare global {
  interface Window {
    GGBApplet?: new (params: Record<string, unknown>, html5: boolean) => {
      inject: (containerId: string) => void;
    };
  }
}

export interface GeoGebraEmbedProps {
  /** A material id from geogebra.org, e.g. "sHFRWkyV". */
  materialId?: string;
  /** Or a raw base64 ggb file. */
  ggbBase64?: string;
  appName?: 'graphing' | 'geometry' | 'classic' | 'suite' | '3d' | 'scientific';
  width?: number;
  height?: number;
  caption?: string;
  className?: string;
}

export function GeoGebraEmbed({
  materialId,
  ggbBase64,
  appName = 'graphing',
  width = 720,
  height = 440,
  caption,
  className,
}: GeoGebraEmbedProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [status, setStatus] = useState<'idle' | 'loading' | 'ready' | 'error'>('idle');
  const containerId = useRef(`ggb-${Math.random().toString(36).slice(2, 10)}`);

  useEffect(() => {
    if (!GEOGEBRA_ENABLED || !containerRef.current) return;

    let cancelled = false;
    setStatus('loading');

    const inject = () => {
      if (cancelled || !window.GGBApplet) return;
      try {
        const applet = new window.GGBApplet(
          {
            appName,
            width,
            height,
            showToolBar: false,
            showAlgebraInput: false,
            showMenuBar: false,
            showResetIcon: true,
            enableLabelDrags: false,
            enableShiftDragZoom: true,
            useBrowserForJS: false,
            ...(materialId ? { material_id: materialId } : {}),
            ...(ggbBase64 ? { ggbBase64 } : {}),
          },
          true,
        );
        applet.inject(containerId.current);
        setStatus('ready');
      } catch {
        setStatus('error');
      }
    };

    if (window.GGBApplet) {
      inject();
      return () => {
        cancelled = true;
      };
    }

    const existing = document.querySelector<HTMLScriptElement>(`script[src="${DEPLOY_SCRIPT_URL}"]`);
    const script = existing ?? document.createElement('script');
    if (!existing) {
      script.src = DEPLOY_SCRIPT_URL;
      script.async = true;
      document.head.appendChild(script);
    }
    script.addEventListener('load', inject);
    script.addEventListener('error', () => setStatus('error'));

    return () => {
      cancelled = true;
      script.removeEventListener('load', inject);
    };
  }, [appName, ggbBase64, height, materialId, width]);

  if (!GEOGEBRA_ENABLED) {
    return (
      <figure className={cn('my-6', className)}>
        <div className="rounded-3xl border-2 border-dashed border-sun-300 bg-sun-50 p-6">
          <p className="font-bold text-ink-900">Interactive GeoGebra activity (not enabled)</p>
          <p className="mt-2 text-sm text-ink-600">
            GeoGebra activities are switched off in this deployment. GeoGebra&apos;s licence
            restricts its materials to non-commercial use, so a commercial licence agreement is
            required before enabling them on a platform that charges course fees.
          </p>
          <p className="mt-2 text-sm text-ink-500">
            Set <code className="rounded bg-white px-1.5 py-0.5 font-mono text-xs">
              NEXT_PUBLIC_GEOGEBRA_ENABLED=true
            </code>{' '}
            once that licence is in place.
          </p>
        </div>
        {caption && <figcaption className="mt-2 text-sm text-ink-500">{caption}</figcaption>}
      </figure>
    );
  }

  return (
    <figure className={cn('my-6', className)}>
      <div
        id={containerId.current}
        ref={containerRef}
        className="scroll-x flex min-h-[300px] items-center justify-center rounded-3xl border-2 border-ink-100 bg-white p-2"
      >
        {status === 'loading' && <p className="text-sm text-ink-500">Loading activity…</p>}
        {status === 'error' && (
          <p className="text-sm text-red-600">This interactive activity could not be loaded.</p>
        )}
      </div>
      {caption && <figcaption className="mt-2 text-sm text-ink-500">{caption}</figcaption>}
      <figcaption className="mt-1 text-xs text-ink-400">
        Interactive activity powered by GeoGebra.
      </figcaption>
    </figure>
  );
}
