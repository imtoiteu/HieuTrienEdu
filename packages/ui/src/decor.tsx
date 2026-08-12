import { cn } from './cn';

/**
 * Decorative elements that carry the brand personality.
 *
 * All are pure SVG/CSS — no image assets, so nothing to optimise, host or licence, and they
 * scale perfectly on any screen. Every one is `aria-hidden`: they are decoration and must never
 * appear in a screen reader's output.
 */

export function Logo({
  className,
  showWordmark = true,
}: {
  className?: string;
  showWordmark?: boolean;
}) {
  return (
    <span className={cn('inline-flex items-center gap-2.5', className)}>
      <span className="relative inline-flex h-10 w-10 shrink-0 items-center justify-center">
        <svg viewBox="0 0 40 40" className="h-full w-full" aria-hidden="true">
          {/* Rounded square mark holding an H and T monogram formed from a plus and a pendulum —
              one glyph for Mathematics, one for Physics. */}
          <rect x="1.5" y="1.5" width="37" height="37" rx="12" fill="#6D4AFF" />
          <rect x="1.5" y="1.5" width="37" height="37" rx="12" fill="none" stroke="#1A1633"
            strokeWidth="3" />
          <path d="M12 11v18M12 20h9M21 11v18" stroke="#FFFFFF" strokeWidth="3.4"
            strokeLinecap="round" />
          <circle cx="29" cy="27" r="3.6" fill="#FFC53D" stroke="#1A1633" strokeWidth="2" />
          <path d="M29 12v11" stroke="#FFC53D" strokeWidth="2.6" strokeLinecap="round" />
        </svg>
      </span>
      {showWordmark && (
        <span className="font-display text-lg font-extrabold leading-none tracking-tight text-ink-900">
          HieuTrien
          <span className="text-brand-500">Education</span>
        </span>
      )}
    </span>
  );
}

export function Blob({
  className,
  tone = 'brand',
  variant = 1,
}: {
  className?: string;
  tone?: 'brand' | 'coral' | 'teal' | 'sun';
  variant?: 1 | 2;
}) {
  const tones = {
    brand: 'bg-brand-200/60',
    coral: 'bg-coral-200/60',
    teal: 'bg-teal-200/60',
    sun: 'bg-sun-200/60',
  };
  return (
    <span
      aria-hidden="true"
      className={cn(
        'pointer-events-none absolute block',
        variant === 1 ? 'blob' : 'blob-2',
        tones[tone],
        className,
      )}
    />
  );
}

/** A cluster of soft background blobs, used behind hero and CTA sections. */
export function BlobField({ className }: { className?: string }) {
  return (
    <div aria-hidden="true" className={cn('pointer-events-none absolute inset-0 overflow-hidden', className)}>
      <Blob tone="brand" className="-left-24 -top-20 h-72 w-72 animate-float-slow" />
      <Blob tone="sun" variant={2} className="right-[-6rem] top-10 h-64 w-64 animate-float" />
      <Blob tone="teal" className="bottom-[-5rem] left-1/3 h-56 w-56 animate-float-slow" />
    </div>
  );
}

export function Squiggle({ className, tone = '#FFC53D' }: { className?: string; tone?: string }) {
  return (
    <svg
      aria-hidden="true"
      viewBox="0 0 200 24"
      className={cn('h-4 w-full', className)}
      preserveAspectRatio="none"
    >
      <path
        d="M0 12 Q 12.5 0, 25 12 T 50 12 T 75 12 T 100 12 T 125 12 T 150 12 T 175 12 T 200 12"
        fill="none"
        stroke={tone}
        strokeWidth="5"
        strokeLinecap="round"
      />
    </svg>
  );
}

export function Sparkles({ className }: { className?: string }) {
  return (
    <svg aria-hidden="true" viewBox="0 0 60 60" className={cn('h-6 w-6', className)}>
      <path
        d="M30 4l4.2 13.8L48 22l-13.8 4.2L30 40l-4.2-13.8L12 22l13.8-4.2z"
        fill="currentColor"
      />
      <circle cx="49" cy="45" r="4" fill="currentColor" opacity="0.7" />
      <circle cx="12" cy="46" r="2.6" fill="currentColor" opacity="0.55" />
    </svg>
  );
}
