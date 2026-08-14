'use client';

import { Plus, X } from 'lucide-react';
import { useState, type ReactNode } from 'react';

import { Badge, cn } from '@hietedu/ui';

import type { EnrollmentStatus, LeadStatus, ReviewStatus } from '@/lib/admin-api';
import { useI18n } from '@/lib/i18n';

/* --------------------------------------------------------------------------------------
 * fields
 * ------------------------------------------------------------------------------------ */

export function FormRow({
  label,
  hint,
  error,
  required,
  htmlFor,
  children,
  className,
}: {
  label: string;
  hint?: string;
  error?: string;
  required?: boolean;
  htmlFor?: string;
  children: ReactNode;
  className?: string;
}) {
  return (
    <div className={cn('min-w-0', className)}>
      <label htmlFor={htmlFor} className="block text-xs font-bold text-ink-700">
        {label}
        {required && (
          <span className="ml-1 text-coral-600" aria-hidden="true">
            *
          </span>
        )}
      </label>
      <div className="mt-1.5">{children}</div>
      {error ? (
        <p className="mt-1 text-xs font-semibold text-coral-700">{error}</p>
      ) : hint ? (
        <p className="mt-1 text-xs text-ink-500">{hint}</p>
      ) : null}
    </div>
  );
}

const fieldClass =
  'w-full rounded-xl border-2 border-ink-200 bg-white px-3 py-2 text-sm text-ink-900 outline-none transition-colors focus:border-brand-400 disabled:bg-ink-50 disabled:text-ink-400';

export function TextField(
  props: React.InputHTMLAttributes<HTMLInputElement> & { invalid?: boolean },
) {
  const { invalid, className, ...rest } = props;
  return (
    <input
      {...rest}
      aria-invalid={invalid || undefined}
      className={cn(fieldClass, invalid && 'border-coral-400', className)}
    />
  );
}

export function TextAreaField(
  props: React.TextareaHTMLAttributes<HTMLTextAreaElement> & { invalid?: boolean },
) {
  const { invalid, className, ...rest } = props;
  return (
    <textarea
      {...rest}
      aria-invalid={invalid || undefined}
      className={cn(fieldClass, 'min-h-[6rem] resize-y', invalid && 'border-coral-400', className)}
    />
  );
}

export function SelectField(
  props: React.SelectHTMLAttributes<HTMLSelectElement> & { invalid?: boolean },
) {
  const { invalid, className, children, ...rest } = props;
  return (
    <select
      {...rest}
      aria-invalid={invalid || undefined}
      className={cn(fieldClass, invalid && 'border-coral-400', className)}
    >
      {children}
    </select>
  );
}

export function CheckboxField({
  label,
  checked,
  onChange,
  hint,
}: {
  label: string;
  checked: boolean;
  onChange: (value: boolean) => void;
  hint?: string;
}) {
  return (
    <label className="flex cursor-pointer items-start gap-2.5">
      <input
        type="checkbox"
        checked={checked}
        onChange={(event) => onChange(event.target.checked)}
        className="mt-0.5 h-4 w-4 shrink-0 rounded border-2 border-ink-300 text-brand-500"
      />
      <span className="min-w-0">
        <span className="block text-sm font-semibold text-ink-800">{label}</span>
        {hint && <span className="block text-xs text-ink-500">{hint}</span>}
      </span>
    </label>
  );
}

/** Editor for a `string[]` column — objectives, features, tags, qualifications. */
export function StringListField({
  values,
  onChange,
  placeholder,
}: {
  values: string[];
  onChange: (values: string[]) => void;
  placeholder?: string;
}) {
  const { t } = useI18n();
  const [draft, setDraft] = useState('');

  function add() {
    const value = draft.trim();
    if (!value || values.includes(value)) {
      setDraft('');
      return;
    }
    onChange([...values, value]);
    setDraft('');
  }

  return (
    <div>
      {values.length > 0 && (
        <ul className="mb-2 flex flex-wrap gap-1.5">
          {values.map((value, index) => (
            <li
              key={`${value}-${index}`}
              className="inline-flex items-center gap-1 rounded-full bg-ink-100 py-1 pl-3 pr-1 text-xs font-semibold text-ink-800"
            >
              {value}
              <button
                type="button"
                onClick={() => onChange(values.filter((_, i) => i !== index))}
                aria-label={t('admin.a.removeAria', { name: value })}
                className="rounded-full p-0.5 hover:bg-ink-200"
              >
                <X className="h-3 w-3" aria-hidden="true" />
              </button>
            </li>
          ))}
        </ul>
      )}
      <div className="flex gap-2">
        <input
          value={draft}
          onChange={(event) => setDraft(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === 'Enter') {
              event.preventDefault();
              add();
            }
          }}
          placeholder={placeholder ?? t('admin.a.addItem')}
          className={fieldClass}
        />
        <button
          type="button"
          onClick={add}
          aria-label={t('admin.a.add')}
          className="shrink-0 rounded-xl border-2 border-ink-200 px-3 hover:bg-ink-50"
        >
          <Plus className="h-4 w-4" aria-hidden="true" />
        </button>
      </div>
    </div>
  );
}

/* --------------------------------------------------------------------------------------
 * status display
 * ------------------------------------------------------------------------------------ */

type Tone = 'brand' | 'coral' | 'teal' | 'sun' | 'neutral';

const REVIEW_TONES: Record<string, Tone> = {
  published: 'teal',
  draft: 'neutral',
  pending_review: 'sun',
  rejected: 'coral',
  archived: 'neutral',
};

const LEAD_TONES: Record<string, Tone> = {
  new: 'coral',
  contacted: 'sun',
  consulting: 'sun',
  interested: 'brand',
  enrolled: 'teal',
  completed: 'teal',
  rejected: 'neutral',
  no_response: 'neutral',
  closed: 'neutral',
};

const ENROLLMENT_TONES: Record<string, Tone> = {
  pending: 'sun',
  confirmed: 'brand',
  active: 'teal',
  completed: 'neutral',
  cancelled: 'coral',
};

const PAYMENT_TONES: Record<string, Tone> = {
  paid: 'teal',
  partial: 'sun',
  unpaid: 'neutral',
  refunded: 'coral',
  waived: 'brand',
};

/**
 * Last-resort label for a snake_case enum value.
 *
 * Only used when the dictionary has no entry for the value — a status the backend invents after
 * this build should still read as "Pending review" rather than "pending_review", in whichever
 * language it lands.
 */
export function humanise(value: string): string {
  return value.replace(/_/g, ' ').replace(/^./, (char) => char.toUpperCase());
}

/**
 * Translate an enum value coming from the API.
 *
 * Statuses, formats, question types and note kinds all arrive as snake_case strings. Rather than
 * a translated lookup table per screen, every one of them resolves through `admin.st.<value>`,
 * so adding a language means adding dictionary entries and nothing else.
 */
export function useEnumLabel(): (value: string | null | undefined) => string {
  const { t } = useI18n();
  return (value) => {
    if (!value) return '—';
    const key = `admin.st.${value}`;
    const translated = t(key);
    // `createTranslator` returns the key itself when it is missing from both dictionaries.
    return translated === key ? humanise(value) : translated;
  };
}

export function StatusBadge({
  value,
  kind = 'review',
}: {
  value: ReviewStatus | LeadStatus | EnrollmentStatus | string;
  kind?: 'review' | 'lead' | 'enrollment' | 'payment';
}) {
  const label = useEnumLabel();
  const map =
    kind === 'lead'
      ? LEAD_TONES
      : kind === 'enrollment'
        ? ENROLLMENT_TONES
        : kind === 'payment'
          ? PAYMENT_TONES
          : REVIEW_TONES;
  return <Badge tone={map[value] ?? 'neutral'}>{label(String(value))}</Badge>;
}

/* --------------------------------------------------------------------------------------
 * bilingual authoring
 * ------------------------------------------------------------------------------------ */

/** One translatable field inside a {@link TranslationPanel}. */
export type TranslatableField = {
  /** Must match a field name the API's `translations` whitelist accepts. */
  name: string;
  label: string;
  multiline?: boolean;
  placeholder?: string;
};

/**
 * Vietnamese fields for a record whose base columns are English.
 *
 * The administrator types Vietnamese here and it is saved as-is — nothing is machine-translated,
 * at save time or at request time. A field left blank is not an empty Vietnamese value; the API
 * drops it and the public site falls back to the English column, which is why the panel says so
 * rather than leaving the author to guess.
 */
export function TranslationPanel({
  fields,
  value,
  onChange,
  disabled,
}: {
  fields: TranslatableField[];
  value: Record<string, string>;
  onChange: (next: Record<string, string>) => void;
  disabled?: boolean;
}) {
  const { t } = useI18n();

  function set(name: string, next: string) {
    onChange({ ...value, [name]: next });
  }

  return (
    <section className="rounded-2xl border-2 border-dashed border-brand-200 bg-brand-50/40 p-4">
      <h3 className="text-xs font-black uppercase tracking-wide text-brand-700">
        {t('admin.i18n.heading')}
      </h3>
      <p className="mt-1 text-xs text-ink-600">{t('admin.i18n.hint')}</p>
      <div className="mt-3 space-y-3">
        {fields.map((field) => (
          <FormRow key={field.name} label={field.label} htmlFor={`vi-${field.name}`}>
            {field.multiline ? (
              <TextAreaField
                id={`vi-${field.name}`}
                lang="vi"
                disabled={disabled}
                value={value[field.name] ?? ''}
                placeholder={field.placeholder}
                onChange={(event) => set(field.name, event.target.value)}
              />
            ) : (
              <TextField
                id={`vi-${field.name}`}
                lang="vi"
                disabled={disabled}
                value={value[field.name] ?? ''}
                placeholder={field.placeholder}
                onChange={(event) => set(field.name, event.target.value)}
              />
            )}
          </FormRow>
        ))}
      </div>
    </section>
  );
}

/**
 * Turn the panel's draft into the `translations` payload the API expects.
 *
 * Blank fields become `null`, which is how the API is told to *remove* a translation rather than
 * store an empty string — an empty string would otherwise sit in the blob forever, and `localise`
 * treats it as untranslated anyway.
 */
export function translationsPayload(
  draft: Record<string, string>,
  locale = 'vi',
): Record<string, Record<string, string | null>> {
  const bucket: Record<string, string | null> = {};
  for (const [name, text] of Object.entries(draft)) {
    bucket[name] = text.trim() ? text.trim() : null;
  }
  return { [locale]: bucket };
}

/** Read the Vietnamese bucket off an API record into panel state. */
export function translationDraft(
  translations: Record<string, Record<string, unknown>> | undefined,
  fields: TranslatableField[],
  locale = 'vi',
): Record<string, string> {
  const bucket = translations?.[locale] ?? {};
  const draft: Record<string, string> = {};
  for (const field of fields) {
    const raw = bucket[field.name];
    draft[field.name] = typeof raw === 'string' ? raw : '';
  }
  return draft;
}
