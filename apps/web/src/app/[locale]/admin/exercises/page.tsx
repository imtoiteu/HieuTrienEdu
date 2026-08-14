'use client';

import { useSearchParams } from 'next/navigation';
import { Eye, Plus, RefreshCw, Trash2, Upload } from 'lucide-react';
import { useCallback, useEffect, useState } from 'react';

import { Alert, Badge, Button, Card } from '@hietedu/ui';

import { AdminShell } from '@/components/admin/admin-shell';
import { DataTable, type Column } from '@/components/admin/data-table';
import { ConfirmDialog, Modal } from '@/components/admin/dialog';
import {
  CheckboxField,
  FormRow,
  SelectField,
  StatusBadge,
  StringListField,
  TextAreaField,
  TextField,
  TranslationPanel,
  useEnumLabel,
} from '@/components/admin/form';
import { useToast } from '@/components/admin/toast';
import { contentLabel, useContentLabel } from '@/lib/content-label';
import { adminApi, type AdminCourse, type AdminQuestion } from '@/lib/admin-api';
import { useRequireAuth } from '@/lib/auth';
import { useI18n } from '@/lib/i18n';

const TYPES = [
  'multiple_choice',
  'multiple_select',
  'true_false',
  'fill_blank',
  'short_answer',
  'numeric',
  'expression',
  'matching',
  'ordering',
];

interface Choice {
  id: string;
  label: string;
  is_correct: boolean;
  /** Vietnamese label. `is_correct` is deliberately not per-language — see the API's whitelist. */
  vi_label?: string;
}

const BLANK_FORM = {
  skill_id: 0,
  question_type: 'multiple_choice',
  prompt: '',
  difficulty: 2,
  estimated_seconds: 60,
  tags: [] as string[],
  choices: [
    { id: 'a', label: '', is_correct: true },
    { id: 'b', label: '', is_correct: false },
  ] as Choice[],
  answer_value: '',
  true_false_value: 'true',
  explanation: '',
  status: 'draft',
  vi_prompt: '',
  vi_explanation: '',
};

export default function ExercisesPage() {
  const { t, locale } = useI18n();
  const enumLabel = useEnumLabel();
  const label = useContentLabel();
  const { user, loading: authLoading } = useRequireAuth(locale, ['admin']);
  const { run, notify } = useToast();
  const params = useSearchParams();

  const [rows, setRows] = useState<AdminQuestion[]>([]);
  const [meta, setMeta] = useState({ total: 0, page: 1, page_size: 25, pages: 0 });
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState('');
  const [sort, setSort] = useState('created_at');
  const [order, setOrder] = useState<'asc' | 'desc'>('desc');
  const [filters, setFilters] = useState<Record<string, string>>({});
  const [selected, setSelected] = useState<number[]>([]);

  const [courses, setCourses] = useState<AdminCourse[]>([]);
  const [skills, setSkills] = useState<{ id: number; name: string; course: string }[]>([]);
  const [creating, setCreating] = useState(false);
  const [saving, setSaving] = useState(false);
  const [form, setForm] = useState({ ...BLANK_FORM });
  const [deleting, setDeleting] = useState<AdminQuestion | null>(null);
  const [preview, setPreview] = useState<{
    data: Record<string, unknown>;
    reveal: boolean;
    locale: string;
  } | null>(null);
  const [importing, setImporting] = useState(false);
  const [importResult, setImportResult] = useState<Record<string, unknown> | null>(null);
  const [importFile, setImportFile] = useState<File | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const result = await adminApi.questions.list({ page, search, sort, order, ...filters });
      setRows(result.items);
      setMeta({
        total: result.total,
        page: result.page,
        page_size: result.page_size,
        pages: result.pages,
      });
    } catch (caught) {
      notify((caught as Error).message, 'error');
    } finally {
      setLoading(false);
    }
  }, [page, search, sort, order, filters, notify]);

  useEffect(() => {
    if (user) void load();
  }, [user, load]);

  // Flatten every skill in the platform once, so the create form has a usable picker.
  useEffect(() => {
    if (!user) return;
    adminApi.courses
      .list({ page_size: 100 })
      .then(async (result) => {
        setCourses(result.items);
        const trees = await Promise.all(
          result.items.map((course) => adminApi.courses.get(course.id).catch(() => null)),
        );
        const flattened = trees.flatMap((course) =>
          course
            ? course.units.flatMap((unit) =>
                unit.topics.flatMap((topic) =>
                  topic.skills.map((skill) => ({
                    id: skill.id,
                    // Flattened for the picker at load time, so the label is resolved here
                    // rather than at render — the option is a plain string either way.
                    name: `${contentLabel(topic, 'title', locale)} → ${contentLabel(skill, 'name', locale)}`,
                    course: contentLabel(course, 'title', locale),
                  })),
                ),
              )
            : [],
        );
        setSkills(flattened);
        setForm((current) => ({
          ...current,
          skill_id: current.skill_id || flattened[0]?.id || 0,
        }));
      })
      .catch(() => undefined);
    // `locale` is a dependency because the option labels are baked in above: switching language
    // has to rebuild them, or the picker keeps the language the page was first opened in.
  }, [user, locale]);

  useEffect(() => {
    if (params.get('new')) setCreating(true);
    const status = params.get('status');
    const skillId = params.get('skill_id');
    if (status || skillId) {
      setFilters((current) => ({
        ...current,
        ...(status ? { status } : {}),
        ...(skillId ? { skill_id: skillId } : {}),
      }));
    }
  }, [params]);

  function buildPayload() {
    const base: Record<string, unknown> = {
      skill_id: form.skill_id,
      question_type: form.question_type,
      prompt: form.prompt,
      difficulty: form.difficulty,
      estimated_seconds: form.estimated_seconds,
      tags: form.tags,
      status: form.status,
      solution: form.explanation ? [{ text: form.explanation }] : [],
    };

    // Vietnamese content. Blank fields are sent as null so the API removes them and the site
    // falls back to English, rather than storing an empty Vietnamese prompt.
    const viChoiceLabels = form.choices
      .filter((choice) => choice.label.trim())
      .map((choice) => choice.vi_label?.trim() ?? '');
    base.translations = {
      vi: {
        prompt: form.vi_prompt.trim() || null,
        solution: form.vi_explanation.trim() ? [{ text: form.vi_explanation.trim() }] : null,
        // Only send choice labels once every one of them has been translated: a partial list
        // would be rejected, since labels are merged onto the English choices by position.
        options:
          viChoiceLabels.length && viChoiceLabels.every(Boolean)
            ? { choices: viChoiceLabels }
            : null,
      },
    };

    if (form.question_type === 'multiple_choice' || form.question_type === 'multiple_select') {
      base.options = { choices: form.choices.filter((choice) => choice.label.trim()) };
      base.answer_spec = {
        choice_ids: form.choices.filter((choice) => choice.is_correct).map((choice) => choice.id),
      };
    } else if (form.question_type === 'true_false') {
      base.answer_spec = { value: form.true_false_value === 'true' };
    } else {
      base.answer_spec = { value: form.answer_value };
    }
    return base;
  }

  async function create() {
    if (!form.prompt.trim()) {
      notify(t('admin.ex.promptRequired'), 'error');
      return;
    }
    if (!form.skill_id) {
      notify(t('admin.ex.skillRequired'), 'error');
      return;
    }
    setSaving(true);
    const created = await run(() => adminApi.questions.create(buildPayload()), t('admin.ex.created'));
    setSaving(false);
    if (created) {
      setCreating(false);
      setForm({ ...BLANK_FORM, skill_id: form.skill_id });
      await load();
    }
  }

  async function showPreview(
    questionId: number,
    reveal: boolean,
    seed?: number,
    previewLocale = 'vi',
  ) {
    const data = await run(() =>
      adminApi.questions.preview(questionId, { reveal, seed, locale: previewLocale }),
    );
    if (data) setPreview({ data, reveal, locale: previewLocale });
  }

  const columns: Column<AdminQuestion>[] = [
    {
      key: 'prompt',
      header: t('admin.ex.exercise'),
      render: (row) => (
        <div className="min-w-0">
          <p className="line-clamp-2 font-semibold text-ink-900">{label(row, 'prompt')}</p>
          <p className="truncate text-xs text-ink-500">
            #{row.id} · {row.skill_name ?? row.topic_slug}
            {row.is_parametric && ` · ${t('admin.ex.parametric')}`}
          </p>
        </div>
      ),
    },
    {
      key: 'type',
      header: t('admin.ex.type'),
      sortKey: 'type',
      hideOnMobile: true,
      render: (row) => <Badge tone="neutral">{enumLabel(row.question_type)}</Badge>,
    },
    {
      key: 'difficulty',
      header: t('admin.stu.level'),
      sortKey: 'difficulty',
      render: (row) => (
        <span className="font-bold tabular-nums text-ink-700">{row.difficulty}</span>
      ),
    },
    {
      key: 'usage',
      header: t('admin.ex.usage'),
      sortKey: 'served',
      hideOnMobile: true,
      render: (row) => (
        <span className="text-xs text-ink-600">
          {row.times_served > 0
            ? t('admin.ex.usageValue', {
                served: row.times_served,
                rate: Math.round((row.success_rate ?? 0) * 100),
              })
            : t('admin.ex.notServed')}
        </span>
      ),
    },
    {
      key: 'status',
      header: t('admin.a.status'),
      sortKey: 'status',
      render: (row) => <StatusBadge value={row.status} />,
    },
    {
      key: 'actions',
      header: '',
      className: 'text-right',
      render: (row) => (
        <div className="flex justify-end gap-1">
          <button
            type="button"
            aria-label={t('admin.ex.previewAria', { id: row.id })}
            onClick={() => showPreview(row.id, true)}
            className="rounded-lg p-2 text-ink-500 hover:bg-ink-100"
          >
            <Eye className="h-4 w-4" aria-hidden="true" />
          </button>
          {row.status === 'published' ? (
            <Button
              size="sm"
              variant="outline"
              onClick={async () => {
                const ok = await run(
                  () => adminApi.questions.unpublish(row.id),
                  t('admin.ex.unpublishedToast'),
                );
                if (ok) await load();
              }}
            >{t('admin.a.unpublish')}</Button>
          ) : (
            <Button
              size="sm"
              variant="outline"
              onClick={async () => {
                const ok = await run(
                  () => adminApi.questions.publish(row.id),
                  t('admin.ex.publishedToast'),
                );
                if (ok) await load();
              }}
            >{t('admin.a.publish')}</Button>
          )}
          <button
            type="button"
            aria-label={t('admin.ex.deleteAria', { id: row.id })}
            onClick={() => setDeleting(row)}
            className="rounded-lg p-2 text-coral-600 hover:bg-coral-50"
          >
            <Trash2 className="h-4 w-4" aria-hidden="true" />
          </button>
        </div>
      ),
    },
  ];

  if (authLoading || !user) return <AdminShell loading />;

  const isChoice =
    form.question_type === 'multiple_choice' || form.question_type === 'multiple_select';

  return (
    <AdminShell
      title={t('admin.ex.title')}
      description={t('admin.ex.subtitle')}
      breadcrumbs={[{ label: t('admin.a.adminCrumb'), href: '/admin' }, { label: t('admin.ex.title') }]}
      actions={
        <>
          <Button variant="outline" onClick={() => setImporting(true)}>
            <Upload className="h-4 w-4" aria-hidden="true" />{t('admin.ex.import')}</Button>
          <Button onClick={() => setCreating(true)}>
            <Plus className="h-4 w-4" aria-hidden="true" />{t('admin.ex.new')}</Button>
        </>
      }
    >
      <DataTable
        columns={columns}
        rows={rows}
        total={meta.total}
        page={meta.page}
        pageSize={meta.page_size}
        pages={meta.pages}
        loading={loading}
        search={search}
        onSearchChange={(value) => {
          setSearch(value);
          setPage(1);
        }}
        sort={sort}
        order={order}
        onSortChange={(nextSort, nextOrder) => {
          setSort(nextSort);
          setOrder(nextOrder);
        }}
        onPageChange={setPage}
        selectable
        selectedIds={selected}
        onSelectionChange={setSelected}
        filters={[
          {
            key: 'status',
            label: t('admin.a.status'),
            options: [
              { value: 'draft', label: t('admin.st.draft') },
              { value: 'pending_review', label: t('admin.st.pending_review') },
              { value: 'published', label: t('admin.st.published') },
              { value: 'archived', label: t('admin.st.archived') },
            ],
          },
          {
            key: 'question_type',
            label: t('admin.tea.typeLabel'),
            options: TYPES.map((type) => ({ value: type, label: enumLabel(type) })),
          },
          {
            key: 'difficulty',
            label: t('admin.ex.difficultyLabel'),
            options: [1, 2, 3, 4, 5].map((value) => ({
              value: String(value),
              label: t('admin.ex.levelN', { n: value }),
            })),
          },
          {
            key: 'grade',
            label: t('admin.a.grade'),
            options: Array.from({ length: 12 }, (_, index) => ({
              value: String(index + 1),
              label: t('admin.a.gradeN', { n: index + 1 }),
            })),
          },
        ]}
        filterValues={filters}
        onFilterChange={(key, value) => {
          setFilters((current) => ({ ...current, [key]: value }));
          setPage(1);
        }}
        actions={
          selected.length > 0 && (
            <div className="flex items-center gap-2">
              <span className="text-xs font-bold text-ink-600">
                {t('admin.a.selected', { count: selected.length })}
              </span>
              <Button
                size="sm"
                variant="outline"
                onClick={async () => {
                  const ok = await run(
                    () => adminApi.questions.bulkStatus(selected, 'published'),
                    t('admin.ex.bulkPublished', { count: selected.length }),
                  );
                  if (ok) {
                    setSelected([]);
                    await load();
                  }
                }}
              >{t('admin.a.publish')}</Button>
              <Button
                size="sm"
                variant="outline"
                onClick={async () => {
                  const ok = await run(
                    () => adminApi.questions.bulkStatus(selected, 'archived'),
                    t('admin.ex.bulkArchived', { count: selected.length }),
                  );
                  if (ok) {
                    setSelected([]);
                    await load();
                  }
                }}
              >{t('admin.a.archive')}</Button>
            </div>
          )
        }
        emptyTitle={t('admin.ex.empty')}
        emptyBody={t('admin.ex.emptyBody')}
        emptyAction={
          <Button onClick={() => setCreating(true)}>
            <Plus className="h-4 w-4" aria-hidden="true" />{t('admin.ex.createOne')}</Button>
        }
      />

      {/* create */}
      <Modal
        open={creating}
        onClose={() => setCreating(false)}
        title={t('admin.ex.new')}
        size="lg"
        footer={
          <>
            <Button variant="ghost" onClick={() => setCreating(false)}>{t('admin.a.cancel')}</Button>
            <Button loading={saving} onClick={create}>{t('admin.ex.createExercise')}</Button>
          </>
        }
      >
        <div className="grid gap-4 sm:grid-cols-2">
          <FormRow label={t('admin.blk.f.skillLabel')} required htmlFor="q-skill" className="sm:col-span-2">
            <SelectField
              id="q-skill"
              value={form.skill_id}
              onChange={(event) => setForm({ ...form, skill_id: Number(event.target.value) })}
            >
              <option value={0}>{t('admin.ex.chooseSkill')}</option>
              {skills.map((skill) => (
                <option key={skill.id} value={skill.id}>
                  {skill.course} — {skill.name}
                </option>
              ))}
            </SelectField>
            {skills.length === 0 && (
              <p className="mt-1 text-xs text-coral-700">{t('admin.ex.noSkillsWarning')}</p>
            )}
          </FormRow>

          <FormRow label={t('admin.ex.type')} required htmlFor="q-type">
            <SelectField
              id="q-type"
              value={form.question_type}
              onChange={(event) => setForm({ ...form, question_type: event.target.value })}
            >
              {TYPES.map((type) => (
                <option key={type} value={type}>
                  {enumLabel(type)}
                </option>
              ))}
            </SelectField>
          </FormRow>

          <FormRow label={t('admin.ex.difficultyLabel')} htmlFor="q-difficulty">
            <SelectField
              id="q-difficulty"
              value={form.difficulty}
              onChange={(event) => setForm({ ...form, difficulty: Number(event.target.value) })}
            >
              {[1, 2, 3, 4, 5].map((value) => (
                <option key={value} value={value}>
                  Level {value}
                </option>
              ))}
            </SelectField>
          </FormRow>

          <FormRow label={t('admin.ex.question')} required htmlFor="q-prompt" className="sm:col-span-2">
            <TextAreaField
              id="q-prompt"
              value={form.prompt}
              onChange={(event) => setForm({ ...form, prompt: event.target.value })}
              placeholder={t('admin.ex.questionPlaceholder')}
            />
          </FormRow>

          {isChoice && (
            <div className="sm:col-span-2">
              <p className="text-xs font-bold text-ink-700">{t('admin.ex.options')}</p>
              <ul className="mt-2 space-y-2">
                {form.choices.map((choice, index) => (
                  <li key={choice.id} className="flex items-center gap-2">
                    <input
                      type={form.question_type === 'multiple_choice' ? 'radio' : 'checkbox'}
                      name="correct-choice"
                      checked={choice.is_correct}
                      aria-label={t('admin.ex.optionCorrect', { id: choice.id })}
                      onChange={(event) =>
                        setForm({
                          ...form,
                          choices: form.choices.map((entry, i) =>
                            form.question_type === 'multiple_choice'
                              ? { ...entry, is_correct: i === index }
                              : i === index
                                ? { ...entry, is_correct: event.target.checked }
                                : entry,
                          ),
                        })
                      }
                      className="h-4 w-4 shrink-0"
                    />
                    <TextField
                      value={choice.label}
                      placeholder={t('admin.ex.option', { id: choice.id.toUpperCase() })}
                      onChange={(event) =>
                        setForm({
                          ...form,
                          choices: form.choices.map((entry, i) =>
                            i === index ? { ...entry, label: event.target.value } : entry,
                          ),
                        })
                      }
                    />
                    {form.choices.length > 2 && (
                      <button
                        type="button"
                        aria-label={t('admin.ex.removeOption', { id: choice.id })}
                        onClick={() =>
                          setForm({
                            ...form,
                            choices: form.choices.filter((_, i) => i !== index),
                          })
                        }
                        className="rounded-lg p-2 text-coral-500 hover:bg-coral-50"
                      >
                        <Trash2 className="h-4 w-4" aria-hidden="true" />
                      </button>
                    )}
                  </li>
                ))}
              </ul>
              <Button
                size="sm"
                variant="outline"
                className="mt-2"
                onClick={() =>
                  setForm({
                    ...form,
                    choices: [
                      ...form.choices,
                      {
                        id: String.fromCharCode(97 + form.choices.length),
                        label: '',
                        is_correct: false,
                      },
                    ],
                  })
                }
              >
                <Plus className="h-4 w-4" aria-hidden="true" />{t('admin.ex.addOption')}</Button>
              <p className="mt-1.5 text-xs text-ink-500">
                Tick the correct answer{form.question_type === 'multiple_select' ? '(s)' : ''}.
              </p>
            </div>
          )}

          {form.question_type === 'true_false' && (
            <FormRow label={t('admin.ex.correctAnswer')} required htmlFor="q-tf" className="sm:col-span-2">
              <SelectField
                id="q-tf"
                value={form.true_false_value}
                onChange={(event) => setForm({ ...form, true_false_value: event.target.value })}
              >
                <option value="true">{t('admin.ex.true')}</option>
                <option value="false">{t('admin.ex.false')}</option>
              </SelectField>
            </FormRow>
          )}

          {!isChoice && form.question_type !== 'true_false' && (
            <FormRow
              label={t('admin.ex.correctAnswer')}
              required
              htmlFor="q-answer"
              className="sm:col-span-2"
              hint={t('admin.ex.correctAnswerHint')}
            >
              <TextField
                id="q-answer"
                value={form.answer_value}
                onChange={(event) => setForm({ ...form, answer_value: event.target.value })}
              />
            </FormRow>
          )}

          <FormRow label={t('admin.ex.explanationLabel')} htmlFor="q-explain" className="sm:col-span-2">
            <TextAreaField
              id="q-explain"
              value={form.explanation}
              onChange={(event) => setForm({ ...form, explanation: event.target.value })}
              placeholder={t('admin.ex.explanationHint')}
            />
          </FormRow>

          <div className="sm:col-span-2">
            <TranslationPanel
              fields={[
                { name: 'prompt', label: t('admin.ex.viPrompt'), multiline: true },
                { name: 'explanation', label: t('admin.ex.viExplanation'), multiline: true },
              ]}
              value={{ prompt: form.vi_prompt, explanation: form.vi_explanation }}
              onChange={(next) =>
                setForm({
                  ...form,
                  vi_prompt: next.prompt ?? '',
                  vi_explanation: next.explanation ?? '',
                })
              }
            />
            {isChoice && (
              <div className="mt-3 rounded-2xl border-2 border-dashed border-brand-200 bg-brand-50/40 p-4">
                <p className="text-xs font-black uppercase tracking-wide text-brand-700">
                  {t('admin.ex.viChoices')}
                </p>
                <p className="mt-1 text-xs text-ink-600">{t('admin.ex.viChoicesHint')}</p>
                <ul className="mt-3 space-y-2">
                  {form.choices.map((choice, index) => (
                    <li key={choice.id} className="flex items-center gap-2">
                      <span className="w-6 shrink-0 text-xs font-bold text-ink-500">
                        {choice.id.toUpperCase()}
                      </span>
                      <TextField
                        lang="vi"
                        value={choice.vi_label ?? ''}
                        placeholder={choice.label || undefined}
                        onChange={(event) =>
                          setForm({
                            ...form,
                            choices: form.choices.map((entry, i) =>
                              i === index ? { ...entry, vi_label: event.target.value } : entry,
                            ),
                          })
                        }
                      />
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>

          <FormRow label={t('admin.ex.tags')} className="sm:col-span-2">
            <StringListField
              values={form.tags}
              onChange={(tags) => setForm({ ...form, tags })}
              placeholder={t('admin.ex.addTag')}
            />
          </FormRow>

          <div className="sm:col-span-2">
            <CheckboxField
              label={t('admin.ex.publishNow')}
              hint={t('admin.ex.publishNowHint')}
              checked={form.status === 'published'}
              onChange={(value) => setForm({ ...form, status: value ? 'published' : 'draft' })}
            />
          </div>
        </div>
      </Modal>

      {/* preview */}
      <Modal
        open={preview !== null}
        onClose={() => setPreview(null)}
        title={t('admin.ex.previewTitle')}
        description={t('admin.ex.previewHint')}
        size="lg"
        footer={
          preview && (
            <>
              <Button
                variant="outline"
                onClick={() =>
                  showPreview(
                    Number(preview.data.question_id),
                    preview.reveal,
                    undefined,
                    preview.locale,
                  )
                }
              >
                <RefreshCw className="h-4 w-4" aria-hidden="true" />{t('admin.ex.newVariant')}</Button>
              <Button
                variant="outline"
                onClick={() =>
                  showPreview(
                    Number(preview.data.question_id),
                    !preview.reveal,
                    Number(preview.data.seed),
                    preview.locale,
                  )
                }
              >
                {preview.reveal ? t('admin.ex.hideAnswer') : t('admin.ex.showAnswer')}
              </Button>
              {/* Same seed, other language: the point is to compare, not to reroll. */}
              <Button
                variant="outline"
                onClick={() =>
                  showPreview(
                    Number(preview.data.question_id),
                    preview.reveal,
                    Number(preview.data.seed),
                    preview.locale === 'vi' ? 'en' : 'vi',
                  )
                }
              >
                {preview.locale === 'vi' ? 'English' : 'Tiếng Việt'}
              </Button>
            </>
          )
        }
      >
        {preview && <QuestionPreview data={preview.data} reveal={preview.reveal} />}
      </Modal>

      {/* import */}
      <Modal
        open={importing}
        onClose={() => {
          setImporting(false);
          setImportResult(null);
          setImportFile(null);
        }}
        title={t('admin.ex.importTitle')}
        size="lg"
        description={t('admin.ex.importHint')}
        footer={
          <>
            <Button
              variant="ghost"
              onClick={() => {
                setImporting(false);
                setImportResult(null);
                setImportFile(null);
              }}
            >{t('admin.a.close')}</Button>
            {importFile && (
              <Button
                variant="outline"
                onClick={async () => {
                  const result = await run(() => adminApi.questions.import(importFile, false));
                  if (result) setImportResult(result);
                }}
              >{t('admin.ex.checkFile')}</Button>
            )}
            {importResult && Number(importResult.parsed ?? 0) > 0 && (
              <Button
                onClick={async () => {
                  if (!importFile) return;
                  const result = await run(
                    () => adminApi.questions.import(importFile, true),
                    t('admin.ex.importedToast'),
                  );
                  if (result) {
                    setImportResult(result);
                    await load();
                  }
                }}
              >
                {t('admin.ex.importCount', { count: String(importResult.parsed) })}
              </Button>
            )}
          </>
        }
      >
        <div className="space-y-4">
          <Alert tone="info" title={t('admin.ex.importColumns')}>
            <code className="text-xs">
              question, type, options, correct_answer, explanation, difficulty, skill_slug, tags
            </code>
            <p className="mt-1 text-xs">{t('admin.ex.pipeHint')}<code>4|5|6|7</code>. Imported
              exercises always arrive as drafts for review.
            </p>
          </Alert>

          <FormRow label={t('admin.ex.file')} required htmlFor="import-file">
            <input
              id="import-file"
              type="file"
              accept=".csv,.json"
              onChange={(event) => {
                setImportFile(event.target.files?.[0] ?? null);
                setImportResult(null);
              }}
              className="w-full rounded-xl border-2 border-ink-200 p-2 text-sm"
            />
          </FormRow>

          {importResult && (
            <Card className="bg-ink-50">
              <p className="text-sm font-bold">{String(importResult.message ?? '')}</p>
              {Array.isArray(importResult.errors) && importResult.errors.length > 0 && (
                <div className="mt-3">
                  <p className="text-xs font-bold text-coral-700">
                    {t('admin.ex.importErrors', { count: importResult.errors.length })}
                  </p>
                  <ul className="mt-1 max-h-40 space-y-0.5 overflow-y-auto text-xs text-ink-600">
                    {(importResult.errors as { row: number; error: string }[])
                      .slice(0, 20)
                      .map((entry) => (
                        <li key={entry.row}>
                          {t('admin.ex.importRow', { n: entry.row, error: entry.error })}
                        </li>
                      ))}
                  </ul>
                </div>
              )}
              {Array.isArray(importResult.preview) && importResult.preview.length > 0 && (
                <div className="mt-3">
                  <p className="text-xs font-bold">{t('admin.ex.importReady')}</p>
                  <ul className="mt-1 max-h-40 space-y-0.5 overflow-y-auto text-xs text-ink-600">
                    {(importResult.preview as { row: number; prompt: string; type: string }[]).map(
                      (entry) => (
                        <li key={entry.row} className="truncate">
                          {entry.prompt} ({enumLabel(entry.type)})
                        </li>
                      ),
                    )}
                  </ul>
                </div>
              )}
            </Card>
          )}
        </div>
      </Modal>

      <ConfirmDialog
        open={deleting !== null}
        onClose={() => setDeleting(null)}
        title={t('admin.ex.deleteQ')}
        message={
          <>
            {deleting && deleting.times_served > 0
              ? t('admin.ex.deleteServedBody', { count: deleting.times_served })
              : t('admin.ex.deleteBody')}
          </>
        }
        onConfirm={async () => {
          if (!deleting) return;
          const ok = await run(() => adminApi.questions.remove(deleting.id), t('admin.ex.deletedToast'));
          if (ok !== undefined) await load();
        }}
      />
    </AdminShell>
  );
}

function QuestionPreview({
  data,
  reveal,
}: {
  data: Record<string, unknown>;
  reveal: boolean;
}) {
  const { t } = useI18n();
  const enumLabel = useEnumLabel();
  const view = (data.student_view ?? {}) as Record<string, unknown>;
  const choices = (view.choices ?? []) as { id: string; label: string }[];

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-2">
        <Badge tone="neutral">{enumLabel(String(data.question_type))}</Badge>
        <Badge tone="neutral">{t('admin.ex.levelN', { n: String(data.difficulty) })}</Badge>
        <span className="text-xs text-ink-500">
          {t('admin.ex.seed')} {String(data.seed)}
        </span>
      </div>

      <div className="rounded-2xl border-2 border-ink-900 bg-white p-5 shadow-pop-sm">
        <p className="font-display text-lg">{String(view.prompt ?? '')}</p>

        {choices.length > 0 && (
          <ul className="mt-4 space-y-2">
            {choices.map((choice) => (
              <li
                key={choice.id}
                className="flex items-center gap-3 rounded-xl border-2 border-ink-200 p-3"
              >
                <span className="flex h-6 w-6 items-center justify-center rounded-full bg-ink-100 text-xs font-extrabold uppercase">
                  {choice.id}
                </span>
                <span className="text-sm">{choice.label}</span>
              </li>
            ))}
          </ul>
        )}

        {Boolean(view.blanks) && (
          <p className="mt-4 text-sm text-ink-500">
            {t('admin.ex.blanksCount', { count: ((view.blanks as unknown[]) ?? []).length })}
          </p>
        )}
        {Boolean(view.items) && (
          <ol className="mt-4 list-decimal space-y-1 pl-5 text-sm">
            {((view.items as { id: string; label: string }[]) ?? []).map((item) => (
              <li key={item.id}>{item.label}</li>
            ))}
          </ol>
        )}
        {choices.length === 0 && !view.blanks && !view.items && (
          <div className="mt-4 rounded-xl border-2 border-dashed border-ink-200 p-3 text-sm text-ink-400">
            {t('admin.ex.studentTypes')}
            {view.unit ? ` (${String(view.unit)})` : ''}
          </div>
        )}
      </div>

      {Number(data.hint_count ?? 0) > 0 && (
        <div className="rounded-2xl bg-brand-50 p-3">
          <p className="text-xs font-bold text-brand-800">
            {t('admin.ex.hintsAvailable', { count: String(data.hint_count) })}
          </p>
          {reveal && (
            <ul className="mt-1 list-disc pl-5 text-xs text-brand-900">
              {((data.hints as { text: string }[]) ?? []).map((hint, index) => (
                <li key={index}>{hint.text}</li>
              ))}
            </ul>
          )}
        </div>
      )}

      {reveal ? (
        <div className="rounded-2xl border-2 border-teal-300 bg-teal-50 p-4">
          <p className="text-xs font-extrabold uppercase tracking-widest text-teal-800">{t('admin.ex.correctAnswer')}</p>
          <pre className="mt-1 overflow-x-auto text-sm text-teal-900">
            {JSON.stringify(data.answer, null, 2)}
          </pre>
          {((data.solution as { text?: string }[]) ?? []).length > 0 && (
            <ol className="mt-2 list-decimal space-y-1 pl-5 text-sm text-teal-900">
              {((data.solution as { text?: string }[]) ?? []).map((step, index) => (
                <li key={index}>{step.text}</li>
              ))}
            </ol>
          )}
        </div>
      ) : (
        <p className="text-center text-xs text-ink-400">{t('admin.ex.answerHidden')}</p>
      )}
    </div>
  );
}
