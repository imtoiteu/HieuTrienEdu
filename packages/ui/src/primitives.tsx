'use client';

import {
  forwardRef,
  type ButtonHTMLAttributes,
  type HTMLAttributes,
  type InputHTMLAttributes,
  type ReactNode,
  type SelectHTMLAttributes,
  type TextareaHTMLAttributes,
} from 'react';

import { cn } from './cn';

export { cn };

/* --------------------------------------------------------------------------------------
 * Button
 * ------------------------------------------------------------------------------------ */

type ButtonVariant = 'primary' | 'secondary' | 'ghost' | 'outline' | 'coral' | 'danger';
type ButtonSize = 'sm' | 'md' | 'lg';

const BUTTON_VARIANTS: Record<ButtonVariant, string> = {
  // The chunky offset shadow that presses in on click is the signature interaction of the
  // whole design system — playful without being childish.
  primary:
    'bg-brand-500 text-white border-ink-900 shadow-pop hover:bg-brand-600 ' +
    'active:translate-x-[3px] active:translate-y-[3px] active:shadow-none',
  coral:
    'bg-coral-500 text-white border-ink-900 shadow-pop hover:bg-coral-600 ' +
    'active:translate-x-[3px] active:translate-y-[3px] active:shadow-none',
  secondary:
    'bg-sun-400 text-ink-900 border-ink-900 shadow-pop hover:bg-sun-300 ' +
    'active:translate-x-[3px] active:translate-y-[3px] active:shadow-none',
  outline:
    'bg-white text-ink-900 border-ink-900 shadow-pop-sm hover:bg-ink-50 ' +
    'active:translate-x-[2px] active:translate-y-[2px] active:shadow-none',
  ghost: 'bg-transparent text-ink-700 border-transparent hover:bg-ink-100 hover:text-ink-900',
  danger:
    'bg-red-500 text-white border-ink-900 shadow-pop hover:bg-red-600 ' +
    'active:translate-x-[3px] active:translate-y-[3px] active:shadow-none',
};

const BUTTON_SIZES: Record<ButtonSize, string> = {
  sm: 'h-9 px-4 text-sm gap-1.5',
  md: 'h-12 px-6 text-base gap-2',
  lg: 'h-14 px-8 text-lg gap-2.5',
};

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  size?: ButtonSize;
  loading?: boolean;
  fullWidth?: boolean;
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(function Button(
  { className, variant = 'primary', size = 'md', loading, fullWidth, children, disabled, ...props },
  ref,
) {
  return (
    <button
      ref={ref}
      // aria-busy tells assistive technology the control is working, which a spinner alone
      // does not communicate.
      aria-busy={loading || undefined}
      disabled={disabled || loading}
      className={cn(
        'inline-flex items-center justify-center rounded-2xl border-2 font-bold',
        // Every size below sets a fixed height, so a label that wraps does not make the button
        // taller — it spills out of it. Vietnamese labels are the ones that expose this: "Bắt đầu
        // miễn phí" is three words where the English is two, and it wrapped inside the header CTA.
        'whitespace-nowrap',
        'transition-all duration-150 select-none',
        'disabled:pointer-events-none disabled:opacity-50',
        BUTTON_VARIANTS[variant],
        BUTTON_SIZES[size],
        fullWidth && 'w-full',
        className,
      )}
      {...props}
    >
      {loading && <Spinner className="h-4 w-4" />}
      {children}
    </button>
  );
});

/* --------------------------------------------------------------------------------------
 * Spinner
 * ------------------------------------------------------------------------------------ */

export function Spinner({ className }: { className?: string }) {
  return (
    <svg
      className={cn('animate-spin', className ?? 'h-5 w-5')}
      viewBox="0 0 24 24"
      fill="none"
      aria-hidden="true"
    >
      <circle cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="3" opacity="0.25" />
      <path
        d="M12 2a10 10 0 0 1 10 10"
        stroke="currentColor"
        strokeWidth="3"
        strokeLinecap="round"
      />
    </svg>
  );
}

/* --------------------------------------------------------------------------------------
 * Card / Section
 * ------------------------------------------------------------------------------------ */

export function Card({
  className,
  interactive,
  children,
  ...props
}: HTMLAttributes<HTMLDivElement> & { interactive?: boolean }) {
  return (
    <div
      className={cn(
        'rounded-3xl border-2 border-ink-100 bg-white p-6 shadow-soft',
        interactive &&
          'transition-all duration-200 hover:-translate-y-1 hover:border-brand-200 hover:shadow-lift',
        className,
      )}
      {...props}
    >
      {children}
    </div>
  );
}

export function Section({
  className,
  children,
  ...props
}: HTMLAttributes<HTMLElement>) {
  return (
    <section className={cn('py-16 sm:py-20 lg:py-24', className)} {...props}>
      {children}
    </section>
  );
}

export function Container({
  className,
  children,
  ...props
}: HTMLAttributes<HTMLDivElement>) {
  return (
    <div className={cn('mx-auto w-full max-w-7xl px-5 sm:px-8 lg:px-12', className)} {...props}>
      {children}
    </div>
  );
}

export function Eyebrow({
  className,
  children,
  tone = 'brand',
}: {
  className?: string;
  children: ReactNode;
  tone?: 'brand' | 'coral' | 'teal' | 'sun';
}) {
  const tones = {
    brand: 'bg-brand-100 text-brand-700',
    coral: 'bg-coral-100 text-coral-700',
    teal: 'bg-teal-100 text-teal-700',
    sun: 'bg-sun-100 text-sun-800',
  };
  return (
    <span
      className={cn(
        'inline-flex items-center gap-2 rounded-full px-4 py-1.5 text-xs font-bold uppercase tracking-widest',
        tones[tone],
        className,
      )}
    >
      {children}
    </span>
  );
}

/* --------------------------------------------------------------------------------------
 * Badge
 * ------------------------------------------------------------------------------------ */

type BadgeTone = 'brand' | 'coral' | 'teal' | 'sun' | 'neutral' | 'success' | 'danger';

const BADGE_TONES: Record<BadgeTone, string> = {
  brand: 'bg-brand-100 text-brand-800 border-brand-200',
  coral: 'bg-coral-100 text-coral-800 border-coral-200',
  teal: 'bg-teal-100 text-teal-800 border-teal-200',
  sun: 'bg-sun-100 text-sun-800 border-sun-200',
  neutral: 'bg-ink-100 text-ink-700 border-ink-200',
  success: 'bg-teal-100 text-teal-800 border-teal-300',
  danger: 'bg-red-100 text-red-800 border-red-200',
};

export function Badge({
  tone = 'neutral',
  className,
  children,
}: {
  tone?: BadgeTone;
  className?: string;
  children: ReactNode;
}) {
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-xs font-bold',
        BADGE_TONES[tone],
        className,
      )}
    >
      {children}
    </span>
  );
}

/* --------------------------------------------------------------------------------------
 * ProgressBar
 * ------------------------------------------------------------------------------------ */

export function ProgressBar({
  value,
  label,
  tone = 'brand',
  size = 'md',
  showValue = false,
  className,
}: {
  /** 0-100. */
  value: number;
  label?: string;
  tone?: 'brand' | 'teal' | 'coral' | 'sun';
  size?: 'sm' | 'md' | 'lg';
  showValue?: boolean;
  className?: string;
}) {
  const clamped = Math.max(0, Math.min(100, Math.round(value)));
  const tones = {
    brand: 'bg-brand-500',
    teal: 'bg-teal-500',
    coral: 'bg-coral-500',
    sun: 'bg-sun-400',
  };
  const heights = { sm: 'h-2', md: 'h-3', lg: 'h-5' };

  return (
    <div className={className}>
      {(label || showValue) && (
        <div className="mb-1.5 flex items-baseline justify-between gap-3">
          {label && <span className="text-sm font-semibold text-ink-700">{label}</span>}
          {showValue && (
            <span className="text-sm font-bold tabular-nums text-ink-900">{clamped}%</span>
          )}
        </div>
      )}
      <div
        // The bar is the accessible control: it carries the role and the value, so a screen
        // reader announces progress even though the visual fill is a plain div.
        role="progressbar"
        aria-valuenow={clamped}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-label={label}
        className={cn(
          'w-full overflow-hidden rounded-full border-2 border-ink-900/10 bg-ink-100',
          heights[size],
        )}
      >
        <div
          className={cn('h-full rounded-full transition-all duration-700 ease-out', tones[tone])}
          style={{ width: `${clamped}%` }}
        />
      </div>
    </div>
  );
}

/* --------------------------------------------------------------------------------------
 * Form controls
 * ------------------------------------------------------------------------------------ */

const FIELD_BASE =
  'w-full rounded-2xl border-2 border-ink-200 bg-white px-4 py-3 text-base text-ink-900 ' +
  'placeholder:text-ink-400 transition-colors focus:border-brand-400 ' +
  'disabled:cursor-not-allowed disabled:bg-ink-50';

export interface FieldProps {
  label: string;
  hint?: string;
  error?: string;
  required?: boolean;
  children: ReactNode;
  htmlFor: string;
}

export function Field({ label, hint, error, required, children, htmlFor }: FieldProps) {
  return (
    <div className="space-y-1.5">
      <label htmlFor={htmlFor} className="block text-sm font-bold text-ink-800">
        {label}
        {required && (
          <span className="ml-1 text-coral-600" aria-hidden="true">
            *
          </span>
        )}
      </label>
      {children}
      {hint && !error && (
        <p id={`${htmlFor}-hint`} className="text-xs text-ink-500">
          {hint}
        </p>
      )}
      {error && (
        // role="alert" so the message is announced when it appears after a failed submit.
        <p id={`${htmlFor}-error`} role="alert" className="text-xs font-semibold text-red-600">
          {error}
        </p>
      )}
    </div>
  );
}

export const Input = forwardRef<HTMLInputElement, InputHTMLAttributes<HTMLInputElement>>(
  function Input({ className, ...props }, ref) {
    return <input ref={ref} className={cn(FIELD_BASE, className)} {...props} />;
  },
);

export const Textarea = forwardRef<HTMLTextAreaElement, TextareaHTMLAttributes<HTMLTextAreaElement>>(
  function Textarea({ className, ...props }, ref) {
    return <textarea ref={ref} className={cn(FIELD_BASE, 'min-h-[7rem]', className)} {...props} />;
  },
);

export const Select = forwardRef<HTMLSelectElement, SelectHTMLAttributes<HTMLSelectElement>>(
  function Select({ className, children, ...props }, ref) {
    return (
      <select ref={ref} className={cn(FIELD_BASE, 'cursor-pointer', className)} {...props}>
        {children}
      </select>
    );
  },
);

/* --------------------------------------------------------------------------------------
 * Alert
 * ------------------------------------------------------------------------------------ */

export function Alert({
  tone = 'info',
  title,
  children,
  className,
}: {
  tone?: 'info' | 'success' | 'warning' | 'error';
  title?: string;
  children?: ReactNode;
  className?: string;
}) {
  const tones = {
    info: 'bg-brand-50 border-brand-200 text-brand-900',
    success: 'bg-teal-50 border-teal-300 text-teal-900',
    warning: 'bg-sun-50 border-sun-300 text-sun-900',
    error: 'bg-red-50 border-red-200 text-red-900',
  };
  return (
    <div
      role={tone === 'error' ? 'alert' : 'status'}
      className={cn('rounded-2xl border-2 p-4 text-sm', tones[tone], className)}
    >
      {title && <p className="mb-1 font-bold">{title}</p>}
      {children}
    </div>
  );
}

/* --------------------------------------------------------------------------------------
 * Avatar / Skeleton
 * ------------------------------------------------------------------------------------ */

export function Avatar({
  name,
  src,
  size = 'md',
  className,
}: {
  name: string;
  src?: string | null;
  size?: 'sm' | 'md' | 'lg' | 'xl';
  className?: string;
}) {
  const sizes = {
    sm: 'h-8 w-8 text-xs',
    md: 'h-11 w-11 text-sm',
    lg: 'h-16 w-16 text-lg',
    xl: 'h-24 w-24 text-2xl',
  };
  const letters = name
    .trim()
    .split(/\s+/)
    .slice(-2)
    .map((part) => part[0]?.toUpperCase() ?? '')
    .join('');

  const palette = [
    'bg-brand-200 text-brand-800',
    'bg-teal-200 text-teal-800',
    'bg-coral-200 text-coral-800',
    'bg-sun-200 text-sun-800',
  ];
  let hash = 0;
  for (let index = 0; index < name.length; index += 1) {
    hash = (hash * 31 + name.charCodeAt(index)) >>> 0;
  }

  if (src) {
    return (
      <img
        src={src}
        alt=""
        className={cn('rounded-2xl border-2 border-ink-900/10 object-cover', sizes[size], className)}
      />
    );
  }

  return (
    <span
      aria-hidden="true"
      className={cn(
        'inline-flex shrink-0 items-center justify-center rounded-2xl border-2 border-ink-900/10 font-extrabold',
        palette[hash % palette.length],
        sizes[size],
        className,
      )}
    >
      {letters}
    </span>
  );
}

export function Skeleton({ className }: { className?: string }) {
  return (
    <div
      aria-hidden="true"
      className={cn('relative overflow-hidden rounded-2xl bg-ink-100', className)}
    >
      <div className="absolute inset-0 -translate-x-full animate-shimmer bg-gradient-to-r from-transparent via-white/70 to-transparent" />
    </div>
  );
}

/* --------------------------------------------------------------------------------------
 * Empty state
 * ------------------------------------------------------------------------------------ */

export function EmptyState({
  icon,
  title,
  description,
  action,
  className,
}: {
  icon?: ReactNode;
  title: string;
  description?: string;
  action?: ReactNode;
  className?: string;
}) {
  return (
    <div
      className={cn(
        'flex flex-col items-center justify-center rounded-3xl border-2 border-dashed border-ink-200 bg-ink-50/50 px-6 py-12 text-center',
        className,
      )}
    >
      {icon && <div className="mb-3 text-ink-300">{icon}</div>}
      <p className="font-bold text-ink-800">{title}</p>
      {description && <p className="mt-1 max-w-sm text-sm text-ink-500">{description}</p>}
      {action && <div className="mt-5">{action}</div>}
    </div>
  );
}
