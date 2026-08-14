'use client';

import {
  ArrowDown,
  ArrowUp,
  Copy,
  GripVertical,
  Plus,
  Trash2,
  Type as TypeIcon,
} from 'lucide-react';
import { useState } from 'react';

import { Badge, Button, cn } from '@hietedu/ui';

import { FormRow, SelectField, StringListField, TextAreaField, TextField, humanise } from './form';
import type { LessonBlock } from '@/lib/admin-api';
import { useI18n } from '@/lib/i18n';
import type { Translator } from '@hietedu/localization';

/**
 * The block palette.
 *
 * Mirrors `app/schemas/lesson_blocks.py` — the backend rejects anything not in its own list, so
 * offering a type here that the server does not accept would produce a save that fails with a
 * validation error the author cannot act on.
 */
export const BLOCK_TYPES: {
  type: string;
  /** Dictionary keys, resolved where the palette renders so it follows the active locale. */
  labelKey: string;
  descriptionKey: string;
  group: 'Text' | 'Media' | 'Mathematics' | 'Assessment';
}[] = [
  { type: 'heading', labelKey: 'admin.blk.heading', descriptionKey: 'admin.blk.heading.d', group: 'Text' },
  { type: 'text', labelKey: 'admin.blk.text', descriptionKey: 'admin.blk.text.d', group: 'Text' },
  { type: 'summary', labelKey: 'admin.blk.summary', descriptionKey: 'admin.blk.summary.d', group: 'Text' },
  { type: 'callout', labelKey: 'admin.blk.callout', descriptionKey: 'admin.blk.callout.d', group: 'Text' },
  { type: 'divider', labelKey: 'admin.blk.divider', descriptionKey: 'admin.blk.divider.d', group: 'Text' },
  { type: 'image', labelKey: 'admin.blk.image', descriptionKey: 'admin.blk.image.d', group: 'Media' },
  { type: 'video', labelKey: 'admin.blk.video', descriptionKey: 'admin.blk.video.d', group: 'Media' },
  { type: 'audio', labelKey: 'admin.blk.audio', descriptionKey: 'admin.blk.audio.d', group: 'Media' },
  { type: 'document', labelKey: 'admin.blk.document', descriptionKey: 'admin.blk.document.d', group: 'Media' },
  { type: 'embed', labelKey: 'admin.blk.embed', descriptionKey: 'admin.blk.embed.d', group: 'Media' },
  { type: 'math', labelKey: 'admin.blk.math', descriptionKey: 'admin.blk.math.d', group: 'Mathematics' },
  { type: 'example', labelKey: 'admin.blk.example', descriptionKey: 'admin.blk.example.d', group: 'Mathematics' },
  { type: 'table', labelKey: 'admin.blk.table', descriptionKey: 'admin.blk.table.d', group: 'Mathematics' },
  { type: 'interactive', labelKey: 'admin.blk.interactive', descriptionKey: 'admin.blk.interactive.d', group: 'Mathematics' },
  { type: 'figure', labelKey: 'admin.blk.figure', descriptionKey: 'admin.blk.figure.d', group: 'Mathematics' },
  { type: 'practice', labelKey: 'admin.blk.practice', descriptionKey: 'admin.blk.practice.d', group: 'Assessment' },
  { type: 'quiz', labelKey: 'admin.blk.quiz', descriptionKey: 'admin.blk.quiz.d', group: 'Assessment' },
  { type: 'homework', labelKey: 'admin.stu.homework', descriptionKey: 'admin.blk.homework.d', group: 'Assessment' },
];

export const SECTIONS = ['theory', 'examples', 'practice', 'homework', 'materials'] as const;

/** Section names live in the dictionary; this only maps a section id onto its key. */
const SECTION_LABEL_KEYS: Record<string, string> = {
  theory: 'admin.blk.section.theory',
  examples: 'admin.blk.section.examples',
  practice: 'admin.blk.section.practice',
  homework: 'admin.blk.section.homework',
  materials: 'admin.blk.section.materials',
};

/** The starter content of a new block. It is placeholder prose the author replaces, so it is
 *  written in the *author's* language rather than left in English. */
function blankBlock(type: string, section: string, t: Translator): LessonBlock {
  const base: LessonBlock = { type, section, id: `b${Date.now()}-${type}` };
  switch (type) {
    case 'heading':
      return { ...base, text: t('admin.blk.new.heading'), level: 2 };
    case 'text':
      return { ...base, markdown: t('admin.blk.new.text') };
    case 'summary':
      return { ...base, points: [t('admin.blk.new.keyPoint')] };
    case 'callout':
      return { ...base, variant: 'note', title: '', text: t('admin.blk.new.callout') };
    case 'image':
      return { ...base, url: '', alt: '', caption: '' };
    case 'video':
      return { ...base, url: '', caption: '' };
    case 'audio':
      return { ...base, url: '', caption: '' };
    case 'document':
      return { ...base, url: '', title: t('admin.blk.new.worksheet') };
    case 'embed':
      return { ...base, url: '' };
    case 'math':
      return { ...base, latex: 'ax^2 + bx + c = 0', caption: '' };
    case 'example':
      return { ...base, title: t('admin.les.exampleLabel'), steps: [{ text: t('admin.blk.new.step') }] };
    case 'table':
      return { ...base, headers: [t('admin.blk.new.column1'), t('admin.blk.new.column2')], rows: [['', '']] };
    case 'interactive':
      return { ...base, widget: 'number-line', config: { min: 0, max: 10, marks: [] } };
    case 'figure':
      return { ...base, shape: 'right-triangle', config: { base: 4, height: 3 } };
    case 'practice':
      return { ...base, skill: '', prompt: t('admin.blk.new.practice') };
    case 'quiz':
      return { ...base, question_ids: [], title: t('admin.blk.new.quiz') };
    case 'homework':
      return { ...base, question_ids: [], instructions: '' };
    default:
      return base;
  }
}

/**
 * Visual editor for a lesson body.
 *
 * Blocks are grouped into the five pedagogical sections and reordered within them. Reordering is
 * arrow-button based rather than drag-and-drop: it works on a touchscreen, it works with a
 * keyboard, and it needs no dependency.
 */
export function BlockEditor({
  blocks,
  onChange,
  skills = [],
}: {
  blocks: LessonBlock[];
  onChange: (blocks: LessonBlock[]) => void;
  skills?: { id: number; slug: string; name: string }[];
}) {
  const { t } = useI18n();
  const [adding, setAdding] = useState<string | null>(null);

  function update(index: number, patch: Partial<LessonBlock>) {
    onChange(blocks.map((block, i) => (i === index ? { ...block, ...patch } : block)));
  }

  function removeAt(index: number) {
    onChange(blocks.filter((_, i) => i !== index));
  }

  function duplicateAt(index: number) {
    const copy = { ...blocks[index], id: `b${Date.now()}-copy` };
    onChange([...blocks.slice(0, index + 1), copy, ...blocks.slice(index + 1)]);
  }

  /** Swap a block with its neighbour *within the same section*. */
  function move(index: number, direction: -1 | 1) {
    const block = blocks[index];
    const section = block.section ?? 'theory';
    const siblingIndices = blocks
      .map((b, i) => ({ b, i }))
      .filter(({ b }) => (b.section ?? 'theory') === section)
      .map(({ i }) => i);
    const position = siblingIndices.indexOf(index);
    const targetIndex = siblingIndices[position + direction];
    if (targetIndex === undefined) return;

    const next = [...blocks];
    [next[index], next[targetIndex]] = [next[targetIndex], next[index]];
    onChange(next);
  }

  return (
    <div className="space-y-6">
      {SECTIONS.map((section) => {
        const sectionBlocks = blocks
          .map((block, index) => ({ block, index }))
          .filter(({ block }) => (block.section ?? 'theory') === section);

        return (
          <section key={section} aria-labelledby={`section-${section}`}>
            <div className="mb-2 flex items-center justify-between">
              <h3 id={`section-${section}`} className="font-display text-lg">
                {t(SECTION_LABEL_KEYS[section])}
                <span className="ml-2 text-xs font-normal text-ink-400">
                  {t('admin.a.blockCount', { count: sectionBlocks.length })}
                </span>
              </h3>
              <Button size="sm" variant="outline" onClick={() => setAdding(section)}>
                <Plus className="h-4 w-4" aria-hidden="true" />{t('admin.blk.addBlock')}</Button>
            </div>

            {sectionBlocks.length === 0 ? (
              <button
                type="button"
                onClick={() => setAdding(section)}
                className="flex w-full items-center justify-center gap-2 rounded-2xl border-2 border-dashed border-ink-200 bg-ink-50/40 py-6 text-sm font-semibold text-ink-500 hover:border-brand-300 hover:text-brand-600"
              >
                <Plus className="h-4 w-4" aria-hidden="true" />
                {t('admin.blk.addTo', {
                  section: t(SECTION_LABEL_KEYS[section]).toLowerCase(),
                })}
              </button>
            ) : (
              <ul className="space-y-2">
                {sectionBlocks.map(({ block, index }, position) => (
                  <li
                    key={block.id ?? index}
                    className="rounded-2xl border-2 border-ink-100 bg-white"
                  >
                    <div className="flex flex-wrap items-center gap-2 border-b border-ink-100 px-3 py-2">
                      <GripVertical className="h-4 w-4 text-ink-300" aria-hidden="true" />
                      <Badge tone="brand">
                        {(() => {
                          const meta = BLOCK_TYPES.find((entry) => entry.type === block.type);
                          return meta ? t(meta.labelKey) : humanise(block.type);
                        })()}
                      </Badge>
                      <div className="ml-auto flex items-center gap-0.5">
                        <button
                          type="button"
                          onClick={() => move(index, -1)}
                          disabled={position === 0}
                          aria-label={t('admin.blk.moveUp')}
                          className="rounded-lg p-1.5 text-ink-400 hover:bg-ink-100 disabled:opacity-30"
                        >
                          <ArrowUp className="h-4 w-4" aria-hidden="true" />
                        </button>
                        <button
                          type="button"
                          onClick={() => move(index, 1)}
                          disabled={position === sectionBlocks.length - 1}
                          aria-label={t('admin.blk.moveDown')}
                          className="rounded-lg p-1.5 text-ink-400 hover:bg-ink-100 disabled:opacity-30"
                        >
                          <ArrowDown className="h-4 w-4" aria-hidden="true" />
                        </button>
                        <button
                          type="button"
                          onClick={() => duplicateAt(index)}
                          aria-label={t('admin.blk.duplicate')}
                          className="rounded-lg p-1.5 text-ink-400 hover:bg-ink-100"
                        >
                          <Copy className="h-4 w-4" aria-hidden="true" />
                        </button>
                        <select
                          value={block.section ?? 'theory'}
                          onChange={(event) => update(index, { section: event.target.value })}
                          aria-label={t('admin.blk.moveToSection')}
                          className="rounded-lg border border-ink-200 px-2 py-1 text-xs"
                        >
                          {SECTIONS.map((value) => (
                            <option key={value} value={value}>
                              {t(SECTION_LABEL_KEYS[value])}
                            </option>
                          ))}
                        </select>
                        <button
                          type="button"
                          onClick={() => removeAt(index)}
                          aria-label={t('admin.blk.delete')}
                          className="rounded-lg p-1.5 text-coral-500 hover:bg-coral-50"
                        >
                          <Trash2 className="h-4 w-4" aria-hidden="true" />
                        </button>
                      </div>
                    </div>
                    <div className="p-3">
                      <BlockFields
                        block={block}
                        skills={skills}
                        onChange={(patch) => update(index, patch)}
                      />
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </section>
        );
      })}

      {adding && (
        <BlockPalette
          onClose={() => setAdding(null)}
          onPick={(type) => {
            onChange([...blocks, blankBlock(type, adding, t)]);
            setAdding(null);
          }}
          section={t(SECTION_LABEL_KEYS[adding])}
        />
      )}
    </div>
  );
}

function BlockPalette({
  onPick,
  onClose,
  section,
}: {
  onPick: (type: string) => void;
  onClose: () => void;
  section: string;
}) {
  const { t } = useI18n();
  const groups = ['Text', t('admin.blk.group.Media'), t('admin.blk.group.Mathematics'), t('admin.blk.group.Assessment')] as const;
  return (
    <div className="fixed inset-0 z-[95] flex items-center justify-center bg-ink-900/40 p-4">
      <button type="button" aria-label={t('admin.a.close')} onClick={onClose} className="absolute inset-0" />
      <div className="relative max-h-[80vh] w-full max-w-2xl overflow-y-auto rounded-3xl border-2 border-ink-900 bg-white p-5 shadow-pop">
        <h3 className="font-display text-xl">Add a block to {section.toLowerCase()}</h3>
        {groups.map((group) => (
          <div key={group} className="mt-4">
            <p className="mb-2 text-xs font-extrabold uppercase tracking-widest text-ink-400">
              {t(`admin.blk.group.${group}`)}
            </p>
            <div className="grid gap-2 sm:grid-cols-2">
              {BLOCK_TYPES.filter((entry) => entry.group === group).map((entry) => (
                <button
                  key={entry.type}
                  type="button"
                  onClick={() => onPick(entry.type)}
                  className="flex items-start gap-3 rounded-2xl border-2 border-ink-100 p-3 text-left hover:border-brand-300 hover:bg-brand-50/40"
                >
                  <TypeIcon className="mt-0.5 h-4 w-4 shrink-0 text-brand-500" aria-hidden="true" />
                  <span className="min-w-0">
                    <span className="block text-sm font-bold text-ink-900">{t(entry.labelKey)}</span>
                    <span className="block text-xs text-ink-500">{t(entry.descriptionKey)}</span>
                  </span>
                </button>
              ))}
            </div>
          </div>
        ))}
        <div className="mt-5 flex justify-end">
          <Button variant="ghost" onClick={onClose}>{t('admin.a.cancel')}</Button>
        </div>
      </div>
    </div>
  );
}

/** Per-type fields. Each writes straight into the block's JSON. */
function BlockFields({
  block,
  onChange,
  skills,
}: {
  block: LessonBlock;
  onChange: (patch: Partial<LessonBlock>) => void;
  skills: { id: number; slug: string; name: string }[];
}) {
  const { t } = useI18n();
  const str = (key: string) => String(block[key] ?? '');

  switch (block.type) {
    case 'heading':
      return (
        <div className="grid gap-3 sm:grid-cols-[1fr_8rem]">
          <FormRow label={t('admin.blk.group.Text')} required>
            <TextField value={str('text')} onChange={(e) => onChange({ text: e.target.value })} />
          </FormRow>
          <FormRow label={t('admin.blk.f.level')}>
            <SelectField
              value={String(block.level ?? 2)}
              onChange={(e) => onChange({ level: Number(e.target.value) })}
            >
              <option value="2">{t('admin.blk.f.h2')}</option>
              <option value="3">{t('admin.blk.f.h3')}</option>
            </SelectField>
          </FormRow>
        </div>
      );

    case 'text':
      return (
        <FormRow
          label={t('admin.blk.f.markdown')}
          required
          hint={t('admin.blk.f.markdownHint')}
        >
          <TextAreaField
            rows={6}
            value={str('markdown')}
            onChange={(e) => onChange({ markdown: e.target.value })}
          />
        </FormRow>
      );

    case 'summary':
      return (
        <FormRow label={t('admin.blk.summary')} required>
          <StringListField
            values={(block.points as string[]) ?? []}
            onChange={(points) => onChange({ points })}
            placeholder={t('admin.blk.f.addKeyPoint')}
          />
        </FormRow>
      );

    case 'callout':
      return (
        <div className="grid gap-3 sm:grid-cols-[8rem_1fr]">
          <FormRow label={t('admin.blk.f.style')}>
            <SelectField
              value={str('variant') || 'note'}
              onChange={(e) => onChange({ variant: e.target.value })}
            >
              <option value="note">{t('admin.blk.f.note')}</option>
              <option value="tip">{t('admin.blk.f.tip')}</option>
              <option value="warning">{t('admin.blk.f.warning')}</option>
            </SelectField>
          </FormRow>
          <FormRow label={t('admin.blk.f.titleOptional')}>
            <TextField value={str('title')} onChange={(e) => onChange({ title: e.target.value })} />
          </FormRow>
          <FormRow label={t('admin.blk.group.Text')} required className="sm:col-span-2">
            <TextAreaField value={str('text')} onChange={(e) => onChange({ text: e.target.value })} />
          </FormRow>
        </div>
      );

    case 'divider':
      return <p className="text-xs text-ink-500">{t('admin.blk.f.divider')}</p>;

    case 'image':
      return (
        <div className="grid gap-3 sm:grid-cols-2">
          <FormRow label={t('admin.a.imageUrl')} required className="sm:col-span-2">
            <TextField
              value={str('url')}
              onChange={(e) => onChange({ url: e.target.value })}
              placeholder="/media/image/…"
            />
          </FormRow>
          <FormRow label={t('admin.blk.f.altText')} hint={t('admin.blk.f.altHint')}>
            <TextField value={str('alt')} onChange={(e) => onChange({ alt: e.target.value })} />
          </FormRow>
          <FormRow label={t('admin.blk.f.caption')}>
            <TextField
              value={str('caption')}
              onChange={(e) => onChange({ caption: e.target.value })}
            />
          </FormRow>
          {str('url') && (
            /* eslint-disable-next-line @next/next/no-img-element */
            <img
              src={str('url')}
              alt={str('alt')}
              className="sm:col-span-2 max-h-48 rounded-xl border border-ink-100 object-contain"
            />
          )}
        </div>
      );

    case 'video':
      return (
        <div className="grid gap-3 sm:grid-cols-2">
          <FormRow label={t('admin.blk.f.videoUrl')} required className="sm:col-span-2">
            <TextField
              value={str('url')}
              onChange={(e) => onChange({ url: e.target.value })}
              placeholder="https://www.youtube.com/watch?v=…"
            />
          </FormRow>
          <FormRow label={t('admin.blk.f.caption')} className="sm:col-span-2">
            <TextField
              value={str('caption')}
              onChange={(e) => onChange({ caption: e.target.value })}
            />
          </FormRow>
        </div>
      );

    case 'audio':
      return (
        <div className="grid gap-3">
          <FormRow label={t('admin.blk.f.audioUrl')} required>
            <TextField value={str('url')} onChange={(e) => onChange({ url: e.target.value })} />
          </FormRow>
          <FormRow label={t('admin.blk.f.caption')}>
            <TextField
              value={str('caption')}
              onChange={(e) => onChange({ caption: e.target.value })}
            />
          </FormRow>
        </div>
      );

    case 'document':
      return (
        <div className="grid gap-3 sm:grid-cols-2">
          <FormRow label={t('admin.a.title')} required>
            <TextField value={str('title')} onChange={(e) => onChange({ title: e.target.value })} />
          </FormRow>
          <FormRow label={t('admin.blk.f.fileUrl')} required>
            <TextField
              value={str('url')}
              onChange={(e) => onChange({ url: e.target.value })}
              placeholder="/media/document/…"
            />
          </FormRow>
        </div>
      );

    case 'embed':
      return (
        <FormRow label={t('admin.blk.f.embedUrl')} required>
          <TextField value={str('url')} onChange={(e) => onChange({ url: e.target.value })} />
        </FormRow>
      );

    case 'math':
      return (
        <div className="grid gap-3">
          <FormRow label={t('admin.blk.f.latex')} required hint={t('admin.blk.f.latexHint')}>
            <TextAreaField
              rows={3}
              value={str('latex')}
              onChange={(e) => onChange({ latex: e.target.value })}
            />
          </FormRow>
          <FormRow label={t('admin.blk.f.caption')}>
            <TextField
              value={str('caption')}
              onChange={(e) => onChange({ caption: e.target.value })}
            />
          </FormRow>
        </div>
      );

    case 'example': {
      const steps = (block.steps as { text?: string; math?: string }[]) ?? [];
      return (
        <div className="space-y-3">
          <FormRow label={t('admin.a.title')}>
            <TextField value={str('title')} onChange={(e) => onChange({ title: e.target.value })} />
          </FormRow>
          <div>
            <p className="text-xs font-bold text-ink-700">{t('admin.blk.f.steps')}</p>
            <ul className="mt-1.5 space-y-2">
              {steps.map((step, index) => (
                <li key={index} className="flex gap-2">
                  <span className="mt-2 text-xs font-bold text-ink-400">{index + 1}</span>
                  <div className="grid min-w-0 flex-1 gap-1.5 sm:grid-cols-2">
                    <TextField
                      value={step.text ?? ''}
                      placeholder={t('admin.blk.f.explanation')}
                      onChange={(e) => {
                        const next = [...steps];
                        next[index] = { ...next[index], text: e.target.value };
                        onChange({ steps: next });
                      }}
                    />
                    <TextField
                      value={step.math ?? ''}
                      placeholder={t('admin.blk.f.latexOptional')}
                      onChange={(e) => {
                        const next = [...steps];
                        next[index] = { ...next[index], math: e.target.value };
                        onChange({ steps: next });
                      }}
                    />
                  </div>
                  <button
                    type="button"
                    aria-label={t('admin.blk.f.removeStep', { n: index + 1 })}
                    onClick={() => onChange({ steps: steps.filter((_, i) => i !== index) })}
                    className="mt-1 rounded-lg p-1.5 text-coral-500 hover:bg-coral-50"
                  >
                    <Trash2 className="h-4 w-4" aria-hidden="true" />
                  </button>
                </li>
              ))}
            </ul>
            <Button
              size="sm"
              variant="outline"
              className="mt-2"
              onClick={() => onChange({ steps: [...steps, { text: '' }] })}
            >
              <Plus className="h-4 w-4" aria-hidden="true" />{t('admin.blk.f.addStep')}</Button>
          </div>
        </div>
      );
    }

    case 'table': {
      const headers = (block.headers as string[]) ?? [];
      const rows = (block.rows as string[][]) ?? [];
      return (
        <div className="space-y-3">
          <FormRow label={t('admin.blk.f.columns')} required>
            <StringListField
              values={headers}
              onChange={(next) =>
                onChange({
                  headers: next,
                  // Keep every row the same width as the header list, otherwise the rendered
                  // table has ragged rows.
                  rows: rows.map((row) =>
                    next.map((_, index) => row[index] ?? ''),
                  ),
                })
              }
              placeholder={t('admin.blk.f.addColumn')}
            />
          </FormRow>
          <div className="scroll-x">
            <table className="w-full text-sm">
              <tbody>
                {rows.map((row, rowIndex) => (
                  <tr key={rowIndex}>
                    {headers.map((_, cellIndex) => (
                      <td key={cellIndex} className="p-1">
                        <TextField
                          value={row[cellIndex] ?? ''}
                          onChange={(e) => {
                            const next = rows.map((r) => [...r]);
                            next[rowIndex][cellIndex] = e.target.value;
                            onChange({ rows: next });
                          }}
                        />
                      </td>
                    ))}
                    <td className="p-1">
                      <button
                        type="button"
                        aria-label={t('admin.blk.f.removeRow', { n: rowIndex + 1 })}
                        onClick={() => onChange({ rows: rows.filter((_, i) => i !== rowIndex) })}
                        className="rounded-lg p-1.5 text-coral-500 hover:bg-coral-50"
                      >
                        <Trash2 className="h-4 w-4" aria-hidden="true" />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <Button
            size="sm"
            variant="outline"
            onClick={() => onChange({ rows: [...rows, headers.map(() => '')] })}
          >
            <Plus className="h-4 w-4" aria-hidden="true" />{t('admin.blk.f.addRow')}</Button>
        </div>
      );
    }

    case 'interactive':
      return (
        <div className="grid gap-3">
          <FormRow label={t('admin.blk.f.widget')} required>
            <SelectField
              value={str('widget')}
              onChange={(e) => onChange({ widget: e.target.value })}
            >
              <option value="number-line">{t('admin.blk.f.numberLine')}</option>
              <option value="function-plot">{t('admin.blk.f.functionPlot')}</option>
              <option value="fraction-bars">{t('admin.blk.f.fractionBars')}</option>
              <option value="geogebra">{t('admin.blk.f.geogebra')}</option>
            </SelectField>
          </FormRow>
          <FormRow
            label={t('admin.blk.f.config')}
            hint={t('admin.blk.f.configHint')}
          >
            <JsonField
              value={block.config as Record<string, unknown>}
              onChange={(config) => onChange({ config })}
            />
          </FormRow>
        </div>
      );

    case 'figure':
      return (
        <div className="grid gap-3">
          <FormRow label={t('admin.blk.f.shape')} required>
            <SelectField value={str('shape')} onChange={(e) => onChange({ shape: e.target.value })}>
              <option value="right-triangle">{t('admin.blk.f.rightTriangle')}</option>
            </SelectField>
          </FormRow>
          <FormRow label={t('admin.blk.f.config')}>
            <JsonField
              value={block.config as Record<string, unknown>}
              onChange={(config) => onChange({ config })}
            />
          </FormRow>
        </div>
      );

    case 'practice':
      return (
        <div className="grid gap-3 sm:grid-cols-2">
          <FormRow
            label={t('admin.blk.f.skillLabel')}
            required
            hint={t('admin.blk.f.skillHint')}
          >
            <SelectField value={str('skill')} onChange={(e) => onChange({ skill: e.target.value })}>
              <option value="">{t('admin.blk.f.chooseSkill')}</option>
              {skills.map((skill) => (
                <option key={skill.id} value={skill.slug}>
                  {skill.name}
                </option>
              ))}
            </SelectField>
          </FormRow>
          <FormRow label={t('admin.blk.f.prompt')}>
            <TextField
              value={str('prompt')}
              onChange={(e) => onChange({ prompt: e.target.value })}
            />
          </FormRow>
        </div>
      );

    case 'quiz':
    case 'homework':
      return (
        <div className="grid gap-3">
          <FormRow label={block.type === 'quiz' ? 'Title' : t('admin.blk.f.instructions')}>
            {block.type === 'quiz' ? (
              <TextField
                value={str('title')}
                onChange={(e) => onChange({ title: e.target.value })}
              />
            ) : (
              <TextAreaField
                value={str('instructions')}
                onChange={(e) => onChange({ instructions: e.target.value })}
              />
            )}
          </FormRow>
          <FormRow
            label={t('admin.blk.f.exerciseIds')}
            required
            hint={t('admin.blk.f.exerciseIdsHint')}
          >
            <TextField
              value={((block.question_ids as number[]) ?? []).join(', ')}
              onChange={(e) =>
                onChange({
                  question_ids: e.target.value
                    .split(',')
                    .map((part) => Number(part.trim()))
                    .filter((value) => Number.isFinite(value) && value > 0),
                })
              }
              placeholder="12, 15, 18"
            />
          </FormRow>
        </div>
      );

    default:
      return <p className="text-xs text-ink-500">{t('admin.blk.noFields')}</p>;
  }
}

/** JSON textarea that keeps invalid text on screen instead of discarding the author's typing. */
function JsonField({
  value,
  onChange,
}: {
  value: Record<string, unknown> | undefined;
  onChange: (value: Record<string, unknown>) => void;
}) {
  const [text, setText] = useState(() => JSON.stringify(value ?? {}, null, 2));
  const [error, setError] = useState<string | null>(null);

  return (
    <div>
      <TextAreaField
        rows={5}
        value={text}
        invalid={Boolean(error)}
        className="font-mono text-xs"
        onChange={(event) => {
          setText(event.target.value);
          try {
            const parsed = JSON.parse(event.target.value || '{}');
            setError(null);
            onChange(parsed);
          } catch (caught) {
            setError((caught as Error).message);
          }
        }}
      />
      {error && <p className={cn('mt-1 text-xs font-semibold text-coral-700')}>{error}</p>}
    </div>
  );
}
