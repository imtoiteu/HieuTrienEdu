'use client';

import { ArrowDown, ArrowUp, Check } from 'lucide-react';
import { useEffect, useState } from 'react';

import { Input, MathText, cn } from '@hietedu/ui';

import type { ServedQuestion } from '@/lib/api';
import { useI18n } from '@/lib/i18n';

export type AnswerValue = Record<string, unknown>;

interface AnswerInputProps {
  question: ServedQuestion;
  value: AnswerValue;
  onChange: (value: AnswerValue) => void;
  disabled?: boolean;
}

/**
 * Renders the correct input for a question type and reports the answer in the exact shape the
 * API's grader expects.
 *
 * The mapping between question type and payload shape lives here and nowhere else — the player
 * treats the answer as an opaque object, so adding a tenth question type means adding a branch
 * here rather than touching the session logic.
 */
export function AnswerInput({ question, value, onChange, disabled }: AnswerInputProps) {
  switch (question.question_type) {
    case 'multiple_choice':
      return (
        <ChoiceInput question={question} value={value} onChange={onChange} disabled={disabled} />
      );
    case 'multiple_select':
      return (
        <MultiSelectInput
          question={question}
          value={value}
          onChange={onChange}
          disabled={disabled}
        />
      );
    case 'true_false':
      return (
        <TrueFalseInput question={question} value={value} onChange={onChange} disabled={disabled} />
      );
    case 'numeric':
    case 'expression':
    case 'short_answer':
      return <TextAnswerInput question={question} value={value} onChange={onChange} disabled={disabled} />;
    case 'fill_blank':
      return (
        <FillBlankInput question={question} value={value} onChange={onChange} disabled={disabled} />
      );
    case 'matching':
      return (
        <MatchingInput question={question} value={value} onChange={onChange} disabled={disabled} />
      );
    case 'ordering':
      return (
        <OrderingInput question={question} value={value} onChange={onChange} disabled={disabled} />
      );
    default:
      return (
        <p className="rounded-2xl bg-sun-50 p-4 text-sm text-ink-700">
          This question type is not supported by this version of the app.
        </p>
      );
  }
}

/* --------------------------------------------------------------------------------------
 * multiple choice
 * ------------------------------------------------------------------------------------ */

function ChoiceInput({ question, value, onChange, disabled }: AnswerInputProps) {
  const { t } = useI18n();
  const selected = value.choice_id as string | undefined;

  return (
    <fieldset disabled={disabled}>
      <legend className="mb-3 text-sm font-semibold text-ink-500">{t('exercise.selectOne')}</legend>
      <div className="space-y-2.5">
        {(question.choices ?? []).map((choice) => (
          <label
            key={choice.id}
            className={cn(
              'flex cursor-pointer items-center gap-3 rounded-2xl border-2 p-4 transition-all',
              selected === choice.id
                ? 'border-brand-500 bg-brand-50 shadow-glow'
                : 'border-ink-200 bg-white hover:border-brand-300',
              disabled && 'cursor-not-allowed opacity-70',
            )}
          >
            <input
              type="radio"
              name={`q-${question.variant_id}`}
              value={choice.id}
              checked={selected === choice.id}
              onChange={() => onChange({ choice_id: choice.id })}
              className="sr-only"
            />
            <span
              aria-hidden="true"
              className={cn(
                'inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-xl border-2 font-display text-sm font-extrabold uppercase',
                selected === choice.id
                  ? 'border-brand-600 bg-brand-500 text-white'
                  : 'border-ink-200 bg-ink-50 text-ink-600',
              )}
            >
              {choice.id}
            </span>
            <span className="flex-1 text-ink-900">
              <MathText>{choice.label}</MathText>
            </span>
          </label>
        ))}
      </div>
    </fieldset>
  );
}

/* --------------------------------------------------------------------------------------
 * multiple select
 * ------------------------------------------------------------------------------------ */

function MultiSelectInput({ question, value, onChange, disabled }: AnswerInputProps) {
  const { t } = useI18n();
  const selected = (value.choice_ids as string[] | undefined) ?? [];

  const toggle = (id: string) => {
    const next = selected.includes(id)
      ? selected.filter((item) => item !== id)
      : [...selected, id];
    onChange({ choice_ids: next });
  };

  return (
    <fieldset disabled={disabled}>
      <legend className="mb-3 text-sm font-semibold text-ink-500">{t('exercise.selectMany')}</legend>
      <div className="space-y-2.5">
        {(question.choices ?? []).map((choice) => {
          const isSelected = selected.includes(choice.id);
          return (
            <label
              key={choice.id}
              className={cn(
                'flex cursor-pointer items-center gap-3 rounded-2xl border-2 p-4 transition-all',
                isSelected
                  ? 'border-brand-500 bg-brand-50 shadow-glow'
                  : 'border-ink-200 bg-white hover:border-brand-300',
                disabled && 'cursor-not-allowed opacity-70',
              )}
            >
              <input
                type="checkbox"
                checked={isSelected}
                onChange={() => toggle(choice.id)}
                className="sr-only"
              />
              <span
                aria-hidden="true"
                className={cn(
                  'inline-flex h-7 w-7 shrink-0 items-center justify-center rounded-lg border-2',
                  isSelected
                    ? 'border-brand-600 bg-brand-500 text-white'
                    : 'border-ink-300 bg-white',
                )}
              >
                {isSelected && <Check className="h-4 w-4" strokeWidth={3} />}
              </span>
              <span className="flex-1 text-ink-900">
                <MathText>{choice.label}</MathText>
              </span>
            </label>
          );
        })}
      </div>
    </fieldset>
  );
}

/* --------------------------------------------------------------------------------------
 * true / false
 * ------------------------------------------------------------------------------------ */

function TrueFalseInput({ question, value, onChange, disabled }: AnswerInputProps) {
  const { t } = useI18n();
  const selected = value.value as boolean | undefined;

  return (
    <fieldset disabled={disabled} className="flex gap-3">
      <legend className="sr-only">{t('exercise.selectOne')}</legend>
      {[
        { label: t('exercise.trueLabel'), option: true },
        { label: t('exercise.falseLabel'), option: false },
      ].map((entry) => (
        <label
          key={String(entry.option)}
          className={cn(
            'flex flex-1 cursor-pointer items-center justify-center rounded-2xl border-2 p-5 text-lg font-bold transition-all',
            selected === entry.option
              ? 'border-brand-500 bg-brand-50 text-brand-800 shadow-glow'
              : 'border-ink-200 bg-white text-ink-700 hover:border-brand-300',
            disabled && 'cursor-not-allowed opacity-70',
          )}
        >
          <input
            type="radio"
            name={`tf-${question.variant_id}`}
            checked={selected === entry.option}
            onChange={() => onChange({ value: entry.option })}
            className="sr-only"
          />
          {entry.label}
        </label>
      ))}
    </fieldset>
  );
}

/* --------------------------------------------------------------------------------------
 * free text (numeric, expression, short answer)
 * ------------------------------------------------------------------------------------ */

function TextAnswerInput({ question, value, onChange, disabled }: AnswerInputProps) {
  const { t } = useI18n();
  const current = (value.value as string | undefined) ?? '';
  const inputId = `answer-${question.variant_id}`;

  return (
    <div>
      <label htmlFor={inputId} className="mb-2 block text-sm font-semibold text-ink-500">
        {t('exercise.yourAnswer')}
      </label>
      <div className="flex items-center gap-3">
        <Input
          id={inputId}
          value={current}
          disabled={disabled}
          onChange={(event) => onChange({ value: event.target.value })}
          placeholder={question.placeholder ?? t('exercise.enterAnswer')}
          // inputMode="text" rather than "decimal" even for numeric answers: students legitimately
          // type fractions like 3/4 and minus signs, and a numeric keypad hides both.
          inputMode="text"
          autoComplete="off"
          className="text-lg"
        />
        {question.unit && (
          <span className="shrink-0 rounded-2xl bg-ink-100 px-4 py-3 font-bold text-ink-700">
            {question.unit}
          </span>
        )}
      </div>
      {question.question_type === 'expression' && (
        <p className="mt-2 text-xs text-ink-500">
          You can write powers as x^2 and products as 2x — both are accepted.
        </p>
      )}
    </div>
  );
}

/* --------------------------------------------------------------------------------------
 * fill in the blanks
 * ------------------------------------------------------------------------------------ */

function FillBlankInput({ question, value, onChange, disabled }: AnswerInputProps) {
  const blanks = (value.blanks as Record<string, string> | undefined) ?? {};

  return (
    <div className="space-y-4">
      {(question.blanks ?? []).map((blank, index) => {
        const inputId = `blank-${question.variant_id}-${blank.id}`;
        return (
          <div key={blank.id}>
            <label htmlFor={inputId} className="mb-1.5 block text-sm font-semibold text-ink-600">
              {blank.label ?? `[${index + 1}]`}
            </label>
            <div className="flex items-center gap-3">
              <Input
                id={inputId}
                value={blanks[blank.id] ?? ''}
                disabled={disabled}
                onChange={(event) =>
                  onChange({ blanks: { ...blanks, [blank.id]: event.target.value } })
                }
                inputMode="text"
                autoComplete="off"
              />
              {blank.unit && (
                <span className="shrink-0 text-sm font-bold text-ink-600">{blank.unit}</span>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}

/* --------------------------------------------------------------------------------------
 * matching
 * ------------------------------------------------------------------------------------ */

function MatchingInput({ question, value, onChange, disabled }: AnswerInputProps) {
  const { t } = useI18n();
  const mapping = (value.mapping as Record<string, string> | undefined) ?? {};

  return (
    <div>
      <p className="mb-3 text-sm font-semibold text-ink-500">{t('exercise.matchPairs')}</p>
      <div className="space-y-3">
        {(question.left ?? []).map((leftItem) => {
          const selectId = `match-${question.variant_id}-${leftItem.id}`;
          return (
            <div
              key={leftItem.id}
              className="flex flex-col gap-2 rounded-2xl border-2 border-ink-200 bg-white p-3 sm:flex-row sm:items-center sm:gap-4"
            >
              <label htmlFor={selectId} className="flex-1 font-semibold text-ink-900">
                <MathText>{leftItem.label}</MathText>
              </label>
              <select
                id={selectId}
                disabled={disabled}
                value={mapping[leftItem.id] ?? ''}
                onChange={(event) =>
                  onChange({ mapping: { ...mapping, [leftItem.id]: event.target.value } })
                }
                className="w-full rounded-xl border-2 border-ink-200 bg-ink-50 px-3 py-2.5 font-medium sm:w-64"
              >
                <option value="">—</option>
                {(question.right ?? []).map((rightItem) => (
                  <option key={rightItem.id} value={rightItem.id}>
                    {rightItem.label}
                  </option>
                ))}
              </select>
            </div>
          );
        })}
      </div>
    </div>
  );
}

/* --------------------------------------------------------------------------------------
 * ordering
 * ------------------------------------------------------------------------------------ */

function OrderingInput({ question, value, onChange, disabled }: AnswerInputProps) {
  const { t } = useI18n();
  const items = question.items ?? [];
  const [order, setOrder] = useState<string[]>(
    (value.order as string[] | undefined) ?? items.map((item) => item.id),
  );

  // Keep local order in sync when the player moves to a new question.
  useEffect(() => {
    setOrder(items.map((item) => item.id));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [question.variant_id]);

  const move = (index: number, direction: -1 | 1) => {
    const target = index + direction;
    if (target < 0 || target >= order.length) return;
    const next = [...order];
    [next[index], next[target]] = [next[target], next[index]];
    setOrder(next);
    onChange({ order: next });
  };

  const labelOf = (id: string) => items.find((item) => item.id === id)?.label ?? id;

  return (
    <div>
      {/* Up/down buttons rather than drag-and-drop: reordering must work with a keyboard and
          with a screen reader, and native HTML5 drag events do neither. */}
      <p className="mb-3 text-sm font-semibold text-ink-500">{t('exercise.dragToOrder')}</p>
      <ol className="space-y-2">
        {order.map((id, index) => (
          <li
            key={id}
            className="flex items-center gap-3 rounded-2xl border-2 border-ink-200 bg-white p-3"
          >
            <span className="inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-xl bg-brand-100 font-display font-extrabold text-brand-700">
              {index + 1}
            </span>
            <span className="min-w-0 flex-1 text-ink-900">
              <MathText>{labelOf(id)}</MathText>
            </span>
            <span className="flex shrink-0 gap-1">
              <button
                type="button"
                disabled={disabled || index === 0}
                onClick={() => move(index, -1)}
                aria-label={`Move ${labelOf(id)} up`}
                className="rounded-lg border-2 border-ink-200 p-1.5 text-ink-600 transition-colors hover:bg-ink-100 disabled:opacity-30"
              >
                <ArrowUp className="h-4 w-4" aria-hidden="true" />
              </button>
              <button
                type="button"
                disabled={disabled || index === order.length - 1}
                onClick={() => move(index, 1)}
                aria-label={`Move ${labelOf(id)} down`}
                className="rounded-lg border-2 border-ink-200 p-1.5 text-ink-600 transition-colors hover:bg-ink-100 disabled:opacity-30"
              >
                <ArrowDown className="h-4 w-4" aria-hidden="true" />
              </button>
            </span>
          </li>
        ))}
      </ol>
    </div>
  );
}

/** True when the student has entered enough to submit. */
export function hasAnswer(question: ServedQuestion, value: AnswerValue): boolean {
  switch (question.question_type) {
    case 'multiple_choice':
      return Boolean(value.choice_id);
    case 'multiple_select':
      return Array.isArray(value.choice_ids) && (value.choice_ids as string[]).length > 0;
    case 'true_false':
      return typeof value.value === 'boolean';
    case 'fill_blank': {
      const blanks = (value.blanks as Record<string, string> | undefined) ?? {};
      const expected = question.blanks ?? [];
      return expected.length > 0 && expected.every((blank) => String(blanks[blank.id] ?? '').trim());
    }
    case 'matching': {
      const mapping = (value.mapping as Record<string, string> | undefined) ?? {};
      const expected = question.left ?? [];
      return expected.length > 0 && expected.every((item) => mapping[item.id]);
    }
    case 'ordering':
      return Array.isArray(value.order) && (value.order as string[]).length > 0;
    default:
      return String(value.value ?? '').trim().length > 0;
  }
}

/** Initial answer state for a freshly served question. */
export function initialAnswer(question: ServedQuestion): AnswerValue {
  if (question.question_type === 'ordering') {
    return { order: (question.items ?? []).map((item) => item.id) };
  }
  if (question.question_type === 'multiple_select') {
    return { choice_ids: [] };
  }
  if (question.question_type === 'fill_blank') {
    return { blanks: {} };
  }
  if (question.question_type === 'matching') {
    return { mapping: {} };
  }
  return {};
}
