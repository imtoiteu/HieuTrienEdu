'use client';

import Link from 'next/link';
import { Archive, Eye, History, Save, Trash2, Undo2, Upload } from 'lucide-react';
import { use, useCallback, useEffect, useState } from 'react';

import { Alert, Badge, Button, Card } from '@hietedu/ui';

import { AdminShell } from '@/components/admin/admin-shell';
import { BlockEditor } from '@/components/admin/block-editor';
import { ConfirmDialog, Modal } from '@/components/admin/dialog';
import {
  FormRow,
  StatusBadge,
  StringListField,
  TextAreaField,
  TextField,
  TranslationPanel,
} from '@/components/admin/form';
import { useToast } from '@/components/admin/toast';
import { useContentLabel } from '@/lib/content-label';
import { adminApi, type LessonBlock, type LessonDetail } from '@/lib/admin-api';
import { useRequireAuth } from '@/lib/auth';
import { useI18n } from '@/lib/i18n';

export default function LessonEditorPage({
  params,
}: {
  params: Promise<{ locale: string; id: string }>;
}) {
  const { id } = use(params);
  const lessonId = Number(id);
  const { t, locale, formatDateTime } = useI18n();
  const label = useContentLabel();
  const { user, loading: authLoading } = useRequireAuth(locale, ['admin']);
  const { run, notify } = useToast();

  const [lesson, setLesson] = useState<LessonDetail | null>(null);
  const [blocks, setBlocks] = useState<LessonBlock[]>([]);
  const [meta, setMeta] = useState({
    title: '',
    summary: '',
    objectives: [] as string[],
    estimated_minutes: 15,
    teacher_notes: '',
  });
  // The lesson body is edited one language at a time in the same editor: `blocks` is the
  // English draft, `viBlocks` the Vietnamese one. They are separate arrays rather than a diff,
  // because a translator needs to see the whole Vietnamese lesson as a lesson.
  const [viBlocks, setViBlocks] = useState<LessonBlock[]>([]);
  const [bodyLocale, setBodyLocale] = useState<'en' | 'vi'>('en');
  const [vi, setVi] = useState({ title: '', summary: '', objectives: [] as string[] });
  const [dirty, setDirty] = useState(false);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [skills, setSkills] = useState<{ id: number; slug: string; name: string }[]>([]);
  const [preview, setPreview] = useState<Record<string, unknown> | null>(null);
  const [revisions, setRevisions] = useState<
    { id: number; version: number; note: string | null; created_at: string; block_count: number }[]
  >([]);
  const [showRevisions, setShowRevisions] = useState(false);
  const [confirming, setConfirming] = useState<'delete' | 'discard' | 'archive' | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const result = await adminApi.lessons.get(lessonId);
      setLesson(result);
      setBlocks(result.draft_blocks ?? []);
      const bucket = (result.translations?.vi ?? {}) as Record<string, unknown>;
      // Fall back to the live translated body when there is no translated draft yet — that is
      // the case for content imported from the YAML sidecars.
      const viDraft = (bucket.draft_blocks ?? bucket.blocks) as LessonBlock[] | undefined;
      setViBlocks(Array.isArray(viDraft) ? viDraft : []);
      setVi({
        title: typeof bucket.title === 'string' ? bucket.title : '',
        summary: typeof bucket.summary === 'string' ? bucket.summary : '',
        objectives: Array.isArray(bucket.objectives) ? (bucket.objectives as string[]) : [],
      });
      setMeta({
        title: result.title,
        summary: result.summary ?? '',
        objectives: result.objectives ?? [],
        estimated_minutes: result.estimated_minutes,
        teacher_notes: result.teacher_notes ?? '',
      });
      setDirty(false);

      // The practice-block picker needs the skills that sit under this lesson's course.
      if (result.breadcrumb.course_id) {
        const course = await adminApi.courses.get(result.breadcrumb.course_id);
        setSkills(
          course.units.flatMap((unit) =>
            unit.topics.flatMap((topic) =>
              topic.skills.map((skill) => ({
                id: skill.id,
                slug: skill.slug,
                name: skill.name,
              })),
            ),
          ),
        );
      }
    } catch (caught) {
      notify((caught as Error).message, 'error');
    } finally {
      setLoading(false);
    }
  }, [lessonId, notify]);

  useEffect(() => {
    if (user) void load();
  }, [user, load]);

  // Warn before losing unsaved block edits to a browser navigation.
  useEffect(() => {
    if (!dirty) return;
    const handler = (event: BeforeUnloadEvent) => {
      event.preventDefault();
      event.returnValue = '';
    };
    window.addEventListener('beforeunload', handler);
    return () => window.removeEventListener('beforeunload', handler);
  }, [dirty]);

  /**
   * The Vietnamese half of the save payload.
   *
   * Empty values are sent as `null` so the API drops them: an empty Vietnamese title should make
   * the site fall back to English, not display nothing.
   */
  function viPayload() {
    return {
      vi: {
        title: vi.title.trim() || null,
        summary: vi.summary.trim() || null,
        objectives: vi.objectives.length ? vi.objectives : null,
        blocks: viBlocks.length ? viBlocks : null,
      },
    };
  }

  async function save() {
    setSaving(true);
    const ok = await run(
      () =>
        adminApi.lessons.update(lessonId, {
          ...meta,
          summary: meta.summary || null,
          teacher_notes: meta.teacher_notes || null,
          blocks,
          translations: viPayload(),
        }),
      t('admin.les.draftSaved'),
    );
    setSaving(false);
    if (ok) {
      setDirty(false);
      await load();
    }
  }

  async function publish() {
    // Save first: publishing copies the *stored* draft to live, so unsaved edits in the browser
    // would otherwise be silently left behind.
    setSaving(true);
    const saved = await run(() =>
      adminApi.lessons.update(lessonId, {
        ...meta,
        summary: meta.summary || null,
        teacher_notes: meta.teacher_notes || null,
        blocks,
        translations: viPayload(),
      }),
    );
    if (!saved) {
      setSaving(false);
      return;
    }
    const ok = await run(
      () => adminApi.lessons.publish(lessonId),
      t('admin.les.publishedToast'),
    );
    setSaving(false);
    if (ok) {
      setDirty(false);
      await load();
    }
  }

  if (authLoading || !user) return <AdminShell loading />;

  return (
    <AdminShell
      title={lesson ? label(lesson, 'title') : t('admin.a.lesson')}
      breadcrumbs={[
        { label: t('admin.a.adminCrumb'), href: '/admin' },
        { label: t('admin.les.title'), href: '/admin/lessons' },
        ...(lesson?.breadcrumb.course_id
          ? [
              {
                label: lesson.breadcrumb.course_title ?? t('admin.a.course'),
                href: `/admin/courses/${lesson.breadcrumb.course_id}`,
              },
            ]
          : []),
        { label: lesson?.title ?? '…' },
      ]}
      actions={
        lesson && (
          <>
            <Button
              variant="outline"
              onClick={async () => {
                const result = await run(() => adminApi.lessons.preview(lessonId, true));
                if (result) setPreview(result);
              }}
            >
              <Eye className="h-4 w-4" aria-hidden="true" />{t('admin.a.preview')}</Button>
            <Button variant="outline" loading={saving} onClick={save}>
              <Save className="h-4 w-4" aria-hidden="true" />{t('admin.les.saveDraft')}</Button>
            <Button loading={saving} onClick={publish}>
              <Upload className="h-4 w-4" aria-hidden="true" />{t('admin.a.publish')}</Button>
          </>
        )
      }
    >
      {loading || !lesson ? (
        <p className="py-16 text-center text-sm text-ink-500">{t('admin.a.loading')}</p>
      ) : (
        <>
          <div className="mb-6 flex flex-wrap items-center gap-3">
            <StatusBadge value={lesson.status} />
            <Badge tone="neutral">{t('admin.les.versionN', { n: lesson.version })}</Badge>
            {lesson.has_draft && <Badge tone="sun">{t('admin.les.unpublishedChanges')}</Badge>}
            {dirty && <Badge tone="coral">{t('admin.les.unsavedEdits')}</Badge>}
            {lesson.published_at && (
              <span className="text-xs text-ink-500">
                {t('admin.les.publishedOn', { date: formatDateTime(lesson.published_at) })}
              </span>
            )}
            <div className="ml-auto flex flex-wrap gap-2">
              <Button
                size="sm"
                variant="ghost"
                onClick={async () => {
                  const result = await run(() => adminApi.lessons.revisions(lessonId));
                  if (result) {
                    setRevisions(result);
                    setShowRevisions(true);
                  }
                }}
              >
                <History className="h-4 w-4" aria-hidden="true" />{t('admin.les.history')}</Button>
              {lesson.has_draft && (
                <Button size="sm" variant="ghost" onClick={() => setConfirming('discard')}>
                  <Undo2 className="h-4 w-4" aria-hidden="true" />{t('admin.les.discardDraft')}</Button>
              )}
              {lesson.status === 'published' && (
                <Button
                  size="sm"
                  variant="ghost"
                  onClick={async () => {
                    const ok = await run(
                      () => adminApi.lessons.unpublish(lessonId),
                      t('admin.les.unpublishedToast'),
                    );
                    if (ok) await load();
                  }}
                >{t('admin.a.unpublish')}</Button>
              )}
              <Button size="sm" variant="ghost" onClick={() => setConfirming('archive')}>
                <Archive className="h-4 w-4" aria-hidden="true" />{t('admin.a.archive')}</Button>
              <Button size="sm" variant="ghost" onClick={() => setConfirming('delete')}>
                <Trash2 className="h-4 w-4 text-coral-600" aria-hidden="true" />
              </Button>
            </div>
          </div>

          {lesson.has_draft && (
            <Alert tone="info" className="mb-6" title={t('admin.les.draftAlert')}>{t('admin.les.draftNotice')}<strong>{t('admin.a.publish')}</strong> {t('admin.les.toMakeLive')}
            </Alert>
          )}

          <div className="grid gap-6 lg:grid-cols-[1fr_20rem]">
            <div className="min-w-0">
              <div className="mb-3 flex flex-wrap items-center gap-2">
                <span className="text-xs font-bold text-ink-600">{t('admin.les.bodyLanguage')}</span>
                <div className="inline-flex overflow-hidden rounded-full border-2 border-ink-200">
                  {(['en', 'vi'] as const).map((code) => (
                    <button
                      key={code}
                      type="button"
                      onClick={() => setBodyLocale(code)}
                      aria-pressed={bodyLocale === code}
                      className={`px-3 py-1 text-xs font-bold ${
                        bodyLocale === code ? 'bg-brand-500 text-white' : 'text-ink-700'
                      }`}
                    >
                      {code === 'en' ? t('admin.les.english') : t('admin.les.vietnamese')}
                    </button>
                  ))}
                </div>
                {bodyLocale === 'vi' && (
                  <span className="text-xs text-ink-500">{t('admin.i18n.blocksNote')}</span>
                )}
              </div>
              {bodyLocale === 'vi' && viBlocks.length === 0 && blocks.length > 0 && (
                <div className="mb-3 flex flex-wrap items-center gap-3 rounded-2xl bg-brand-50 p-3">
                  <p className="text-xs text-brand-900">{t('admin.les.startFromEnglish')}</p>
                  <Button
                    size="sm"
                    variant="ghost"
                    onClick={() => {
                      // Copy the English blocks as a starting point, so the translator edits prose
                      // in place rather than rebuilding the lesson structure from scratch.
                      setViBlocks(blocks.map((block) => ({ ...block })));
                      setDirty(true);
                    }}
                  >
                    {t('admin.les.copyEnglishBlocks')}
                  </Button>
                </div>
              )}
              <BlockEditor
                key={bodyLocale}
                blocks={bodyLocale === 'en' ? blocks : viBlocks}
                skills={skills}
                onChange={(next) => {
                  if (bodyLocale === 'en') setBlocks(next);
                  else setViBlocks(next);
                  setDirty(true);
                }}
              />
            </div>

            <aside className="space-y-4">
              <Card>
                <h2 className="font-display text-lg">{t('admin.les.details')}</h2>
                <div className="mt-4 space-y-4">
                  <FormRow label={t('admin.a.title')} required htmlFor="l-title">
                    <TextField
                      id="l-title"
                      value={meta.title}
                      onChange={(event) => {
                        setMeta({ ...meta, title: event.target.value });
                        setDirty(true);
                      }}
                    />
                  </FormRow>
                  <FormRow label={t('admin.a.summary')} htmlFor="l-summary">
                    <TextAreaField
                      id="l-summary"
                      value={meta.summary}
                      onChange={(event) => {
                        setMeta({ ...meta, summary: event.target.value });
                        setDirty(true);
                      }}
                    />
                  </FormRow>
                  <FormRow label={t('admin.les.objectives')}>
                    <StringListField
                      values={meta.objectives}
                      onChange={(objectives) => {
                        setMeta({ ...meta, objectives });
                        setDirty(true);
                      }}
                      placeholder={t('admin.les.objectivePlaceholder')}
                    />
                  </FormRow>
                  <FormRow label={t('admin.crs.estimatedMinutes')} htmlFor="l-minutes">
                    <TextField
                      id="l-minutes"
                      type="number"
                      min={1}
                      value={meta.estimated_minutes}
                      onChange={(event) => {
                        setMeta({ ...meta, estimated_minutes: Number(event.target.value) });
                        setDirty(true);
                      }}
                    />
                  </FormRow>
                  <FormRow
                    label={t('admin.les.teacherNotes')}
                    hint={t('admin.les.teacherNotesHint')}
                    htmlFor="l-notes"
                  >
                    <TextAreaField
                      id="l-notes"
                      value={meta.teacher_notes}
                      onChange={(event) => {
                        setMeta({ ...meta, teacher_notes: event.target.value });
                        setDirty(true);
                      }}
                    />
                  </FormRow>
                </div>
              </Card>

              <Card>
                <TranslationPanel
                  fields={[
                    { name: 'title', label: t('admin.a.title') },
                    { name: 'summary', label: t('admin.a.summary'), multiline: true },
                  ]}
                  value={{ title: vi.title, summary: vi.summary }}
                  onChange={(next) => {
                    setVi({ ...vi, title: next.title ?? '', summary: next.summary ?? '' });
                    setDirty(true);
                  }}
                />
                <div className="mt-3">
                  <FormRow label={`${t('admin.les.objectives')} (VI)`}>
                    <StringListField
                      values={vi.objectives}
                      onChange={(objectives) => {
                        setVi({ ...vi, objectives });
                        setDirty(true);
                      }}
                      placeholder={t('admin.les.objectivePlaceholder')}
                    />
                  </FormRow>
                </div>
              </Card>

              <Card>
                <h2 className="font-display text-lg">{t('admin.les.whereItLives')}</h2>
                <dl className="mt-3 space-y-2 text-sm">
                  <div>
                    <dt className="text-xs font-bold text-ink-500">{t('admin.crs.course')}</dt>
                    <dd>
                      {lesson.breadcrumb.course_id ? (
                        <Link
                          href={`/${locale}/admin/courses/${lesson.breadcrumb.course_id}`}
                          className="font-semibold text-brand-600 hover:underline"
                        >
                          {lesson.breadcrumb.course_title}
                        </Link>
                      ) : (
                        '—'
                      )}
                    </dd>
                  </div>
                  <div>
                    <dt className="text-xs font-bold text-ink-500">{t('admin.les.moduleLabel')}</dt>
                    <dd className="font-semibold">{lesson.breadcrumb.unit_title ?? '—'}</dd>
                  </div>
                  <div>
                    <dt className="text-xs font-bold text-ink-500">{t('admin.crs.topic')}</dt>
                    <dd className="font-semibold">{lesson.breadcrumb.topic_title ?? '—'}</dd>
                  </div>
                  <div>
                    <dt className="text-xs font-bold text-ink-500">{t('admin.les.publicUrl')}</dt>
                    <dd className="truncate font-mono text-xs">/{locale}/lessons/{lesson.slug}</dd>
                  </div>
                </dl>
              </Card>
            </aside>
          </div>
        </>
      )}

      {/* preview */}
      <Modal
        open={preview !== null}
        onClose={() => setPreview(null)}
        title={t('admin.les.studentPreview')}
        description={t('admin.les.studentPreviewHint')}
        size="xl"
      >
        {preview && (
          <article className="prose-admin space-y-4">
            <h1 className="font-display text-2xl">{String(preview.title)}</h1>
            {Boolean(preview.summary) && (
              <p className="text-ink-600">{String(preview.summary)}</p>
            )}
            {((preview.objectives as string[]) ?? []).length > 0 && (
              <div className="rounded-2xl bg-brand-50 p-4">
                <p className="text-sm font-bold">{t('admin.les.objectives')}</p>
                <ul className="mt-2 list-disc pl-5 text-sm">
                  {((preview.objectives as string[]) ?? []).map((objective) => (
                    <li key={objective}>{objective}</li>
                  ))}
                </ul>
              </div>
            )}
            {((preview.blocks as LessonBlock[]) ?? []).map((block, index) => (
              <PreviewBlock key={block.id ?? index} block={block} />
            ))}
            {((preview.blocks as LessonBlock[]) ?? []).length === 0 && (
              <p className="text-sm text-ink-500">{t('admin.les.noBlocksYet')}</p>
            )}
          </article>
        )}
      </Modal>

      {/* revisions */}
      <Modal
        open={showRevisions}
        onClose={() => setShowRevisions(false)}
        title={t('admin.les.versionHistory')}
        description={t('admin.les.versionHistoryHint')}
      >
        {revisions.length === 0 ? (
          <p className="text-sm text-ink-500">{t('admin.les.noRevisions')}</p>
        ) : (
          <ul className="divide-y divide-ink-100">
            {revisions.map((revision) => (
              <li key={revision.id} className="flex flex-wrap items-center gap-3 py-3">
                <div className="min-w-0 flex-1">
                  <p className="font-bold">{t('admin.les.versionN', { n: revision.version })}</p>
                  <p className="text-xs text-ink-500">
                    {t('admin.les.revisionMeta', {
                      count: revision.block_count,
                      date: formatDateTime(revision.created_at),
                    })}
                    {revision.note ? ` · ${revision.note}` : ''}
                  </p>
                </div>
                <Button
                  size="sm"
                  variant="outline"
                  onClick={async () => {
                    const ok = await run(
                      () => adminApi.lessons.restore(lessonId, revision.id),
                      t('admin.les.restored', { n: revision.version }),
                    );
                    if (ok) {
                      setShowRevisions(false);
                      await load();
                    }
                  }}
                >{t('admin.les.restore')}</Button>
              </li>
            ))}
          </ul>
        )}
      </Modal>

      <ConfirmDialog
        open={confirming !== null}
        onClose={() => setConfirming(null)}
        title={
          confirming === 'delete'
            ? t('admin.les.deleteQ')
            : confirming === 'discard'
              ? t('admin.les.discardQ')
              : t('admin.les.archiveQ')
        }
        confirmLabel={
          confirming === 'delete'
            ? t('admin.a.delete')
            : confirming === 'discard'
              ? t('admin.a.discard')
              : t('admin.a.archive')
        }
        tone={confirming === 'archive' ? 'default' : 'danger'}
        message={
          confirming === 'delete'
            ? t('admin.les.deleteAllBody')
            : confirming === 'discard'
              ? t('admin.les.discardBody')
              : t('admin.les.archiveBody')
        }
        onConfirm={async () => {
          if (confirming === 'delete') {
            const ok = await run(() => adminApi.lessons.remove(lessonId), t('admin.les.deletedToast'));
            if (ok !== undefined) window.location.href = `/${locale}/admin/lessons`;
          } else if (confirming === 'discard') {
            const ok = await run(() => adminApi.lessons.discardDraft(lessonId), t('admin.les.discardedToast'));
            if (ok) await load();
          } else {
            const ok = await run(() => adminApi.lessons.archive(lessonId), t('admin.les.archivedToast'));
            if (ok) await load();
          }
        }}
      />
    </AdminShell>
  );
}

/** A deliberately plain rendering — enough to check structure and copy before publishing. */
function PreviewBlock({ block }: { block: LessonBlock }) {
  const { t } = useI18n();
  const text = (key: string) => String(block[key] ?? '');

  switch (block.type) {
    case 'heading':
      return <h2 className="mt-6 font-display text-xl">{text('text')}</h2>;
    case 'text':
      return <p className="whitespace-pre-wrap text-ink-700">{text('markdown')}</p>;
    case 'summary':
      return (
        <div className="rounded-2xl border-2 border-teal-200 bg-teal-50 p-4">
          <p className="font-bold">{t('admin.les.keyPointsLabel')}</p>
          <ul className="mt-2 list-disc pl-5 text-sm">
            {((block.points as string[]) ?? []).map((point, index) => (
              <li key={index}>{point}</li>
            ))}
          </ul>
        </div>
      );
    case 'callout':
      return (
        <aside className="rounded-2xl border-2 border-brand-200 bg-brand-50 p-4">
          <p className="font-bold">{text('title') || text('variant') || 'Note'}</p>
          <p className="mt-1 text-sm">{text('text')}</p>
        </aside>
      );
    case 'math':
      return (
        <pre className="overflow-x-auto rounded-xl bg-ink-900 p-3 font-mono text-xs text-white">
          {text('latex')}
        </pre>
      );
    case 'image':
      return text('url') ? (
        /* eslint-disable-next-line @next/next/no-img-element */
        <img
          src={text('url')}
          alt={text('alt')}
          className="max-h-80 rounded-2xl border border-ink-100 object-contain"
        />
      ) : (
        <p className="text-xs text-coral-700">{t('admin.les.imageNoUrl')}</p>
      );
    case 'video':
    case 'audio':
    case 'document':
    case 'embed':
      return (
        <div className="rounded-2xl border-2 border-ink-100 p-4 text-sm">
          <Badge tone="neutral">{block.type}</Badge>
          <p className="mt-1 truncate font-mono text-xs text-ink-600">
            {text('url') || 'No URL set'}
          </p>
        </div>
      );
    case 'example':
      return (
        <div className="rounded-2xl border-2 border-ink-900 p-4">
          <p className="text-xs font-bold uppercase tracking-widest text-brand-700">{t('admin.les.exampleLabel')}</p>
          <p className="font-display text-lg">{text('title')}</p>
          <ol className="mt-2 list-decimal space-y-1 pl-5 text-sm">
            {((block.steps as { text?: string; math?: string }[]) ?? []).map((step, index) => (
              <li key={index}>
                {step.text}
                {step.math ? ` — ${step.math}` : ''}
              </li>
            ))}
          </ol>
        </div>
      );
    case 'table':
      return (
        <div className="scroll-x rounded-2xl border-2 border-ink-100">
          <table className="w-full text-left text-sm">
            <thead className="bg-ink-50">
              <tr>
                {((block.headers as string[]) ?? []).map((header, index) => (
                  <th key={index} className="px-3 py-2 font-display">
                    {header}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {((block.rows as string[][]) ?? []).map((row, rowIndex) => (
                <tr key={rowIndex} className="border-t border-ink-100">
                  {row.map((cell, cellIndex) => (
                    <td key={cellIndex} className="px-3 py-2">
                      {cell}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      );
    case 'practice':
    case 'quiz':
    case 'homework':
      return (
        <div className="rounded-2xl border-2 border-brand-300 bg-brand-50 p-4">
          <Badge tone="brand">{block.type}</Badge>
          <p className="mt-1 text-sm">
            {text('prompt') || text('title') || text('instructions') || t('admin.blk.new.assessment')}
          </p>
          {Boolean(block.skill) && (
            <p className="mt-1 text-xs text-ink-600">
              {t('admin.les.skillLabel')} {text('skill')}
            </p>
          )}
          {((block.question_ids as number[]) ?? []).length > 0 && (
            <p className="mt-1 text-xs text-ink-600">
              {t('admin.les.exerciseCount', {
                count: ((block.question_ids as number[]) ?? []).length,
              })}
            </p>
          )}
        </div>
      );
    case 'divider':
      return <hr className="border-ink-200" />;
    default:
      return (
        <div className="rounded-2xl border-2 border-dashed border-ink-200 p-3 text-xs text-ink-500">
          {block.type} block
        </div>
      );
  }
}
