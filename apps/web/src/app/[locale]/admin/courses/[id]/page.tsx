'use client';

import Link from 'next/link';
import {
  ArrowDown,
  ArrowUp,
  ChevronDown,
  ChevronRight,
  FileText,
  Pencil,
  Plus,
  Target,
  Trash2,
} from 'lucide-react';
import { use, useCallback, useEffect, useState } from 'react';

import { Badge, Button, Card } from '@hietedu/ui';

import { AdminShell } from '@/components/admin/admin-shell';
import { ConfirmDialog, Modal } from '@/components/admin/dialog';
import {
  CheckboxField,
  FormRow,
  SelectField,
  StatusBadge,
  TextAreaField,
  TextField,
  TranslationPanel,
  translationDraft,
  translationsPayload,
} from '@/components/admin/form';
import { useToast } from '@/components/admin/toast';
import { useContentLabel } from '@/lib/content-label';
import {
  adminApi,
  type AdminCourse,
  type Category,
  type ReviewStatus,
  type StructureTopic,
  type StructureUnit,
} from '@/lib/admin-api';
import { useRequireAuth } from '@/lib/auth';
import { useI18n } from '@/lib/i18n';

type NodeKind = 'unit' | 'topic' | 'skill' | 'lesson';

interface NodeDraft {
  kind: NodeKind;
  id?: number;
  parentId: number;
  title: string;
  summary: string;
  difficulty: number;
  estimated_minutes: number;
  /** Vietnamese title and summary. Kept flat because a node has exactly two translatable fields. */
  viTitle: string;
  viSummary: string;
}

const BLANK_NODE: NodeDraft = {
  kind: 'unit',
  parentId: 0,
  title: '',
  summary: '',
  difficulty: 2,
  estimated_minutes: 15,
  viTitle: '',
  viSummary: '',
};

/** Read a node's Vietnamese fields out of the API's `translations` blob. */
function nodeTranslations(
  translations: Record<string, Record<string, unknown>> | undefined,
  titleField: 'title' | 'name',
): { viTitle: string; viSummary: string } {
  const bucket = translations?.vi ?? {};
  const summaryField = titleField === 'name' ? 'description' : 'summary';
  return {
    viTitle: typeof bucket[titleField] === 'string' ? (bucket[titleField] as string) : '',
    viSummary: typeof bucket[summaryField] === 'string' ? (bucket[summaryField] as string) : '',
  };
}

export default function CourseStructurePage({
  params,
}: {
  params: Promise<{ locale: string; id: string }>;
}) {
  const { id } = use(params);
  const courseId = Number(id);
  const { t, locale } = useI18n();
  // Content carries its English column plus its translations; which one this screen shows
  // depends on the language the administrator is working in, not on the row.
  const label = useContentLabel();
  const { user, loading: authLoading } = useRequireAuth(locale, ['admin']);
  const { run, notify } = useToast();

  const [course, setCourse] = useState<(AdminCourse & { units: StructureUnit[] }) | null>(null);
  const [loading, setLoading] = useState(true);
  const [expanded, setExpanded] = useState<Record<number, boolean>>({});
  const [node, setNode] = useState<NodeDraft | null>(null);
  const [saving, setSaving] = useState(false);
  const [deleting, setDeleting] = useState<{ kind: NodeKind; id: number; label: string } | null>(
    null,
  );
  const [editingCourse, setEditingCourse] = useState(false);
  const [categories, setCategories] = useState<Category[]>([]);
  const [courseForm, setCourseForm] = useState({
    title: '',
    summary: '',
    description: '',
    estimated_hours: 0,
    is_featured: false,
    thumbnail_url: '',
    seo_title: '',
    seo_description: '',
    category_ids: [] as number[],
  });
  const [courseVi, setCourseVi] = useState<Record<string, string>>({
    title: '',
    summary: '',
    description: '',
  });

  const href = (path: string) => `/${locale}${path}`;

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const result = await adminApi.courses.get(courseId);
      setCourse(result);
      setExpanded((current) =>
        Object.keys(current).length
          ? current
          : Object.fromEntries(result.units.map((unit) => [unit.id, true])),
      );
    } catch (caught) {
      notify((caught as Error).message, 'error');
    } finally {
      setLoading(false);
    }
  }, [courseId, notify]);

  useEffect(() => {
    if (user) void load();
  }, [user, load]);

  useEffect(() => {
    if (user) {
      adminApi.categories
        .list({ page_size: 200 })
        .then((result) => setCategories(result.items))
        .catch(() => undefined);
    }
  }, [user]);

  function openCourseEditor() {
    if (!course) return;
    setCourseForm({
      title: course.title,
      summary: course.summary ?? '',
      description: course.description ?? '',
      estimated_hours: course.estimated_hours,
      is_featured: course.is_featured,
      thumbnail_url: course.thumbnail_url ?? '',
      seo_title: course.seo_title ?? '',
      seo_description: course.seo_description ?? '',
      category_ids: course.categories.map((category) => category.id),
    });
    setCourseVi(
      translationDraft(course.translations, [
        { name: 'title', label: '' },
        { name: 'summary', label: '' },
        { name: 'description', label: '' },
      ]),
    );
    setEditingCourse(true);
  }

  async function saveCourse() {
    setSaving(true);
    const ok = await run(
      () =>
        adminApi.courses.update(courseId, {
          ...courseForm,
          summary: courseForm.summary || null,
          description: courseForm.description || null,
          thumbnail_url: courseForm.thumbnail_url || null,
          seo_title: courseForm.seo_title || null,
          seo_description: courseForm.seo_description || null,
          translations: translationsPayload(courseVi),
        }),
      t('admin.crs.saved'),
    );
    setSaving(false);
    if (ok) {
      setEditingCourse(false);
      await load();
    }
  }

  async function setStatus(status: ReviewStatus) {
    const ok = await run(
      () => adminApi.courses.setStatus(courseId, status),
      status === 'published' ? t('admin.crs.publishedToast') : t('admin.crs.statusToast', { status: status }),
    );
    if (ok) await load();
  }

  async function saveNode() {
    if (!node || !node.title.trim()) {
      notify(t('admin.a.titleRequired'), 'error');
      return;
    }
    setSaving(true);

    // A skill's translatable fields are `name`/`description`; everything else uses
    // `title`/`summary`. The dialog shows one pair of inputs either way.
    const skillTranslations = translationsPayload({
      name: node.viTitle,
      description: node.viSummary,
    });
    const translations = translationsPayload({
      title: node.viTitle,
      summary: node.viSummary,
    });

    const ok = await run(async () => {
      if (node.kind === 'unit') {
        const body = { title: node.title, summary: node.summary || null, translations };
        return node.id
          ? adminApi.units.update(node.id, body)
          : adminApi.units.create({ ...body, course_id: courseId });
      }
      if (node.kind === 'topic') {
        const body = { title: node.title, summary: node.summary || null, translations };
        return node.id
          ? adminApi.topics.update(node.id, body)
          : adminApi.topics.create({ ...body, unit_id: node.parentId });
      }
      if (node.kind === 'skill') {
        const body = {
          name: node.title,
          description: node.summary || null,
          difficulty: node.difficulty,
          translations: skillTranslations,
        };
        return node.id
          ? adminApi.skills.update(node.id, body)
          : adminApi.skills.create({ ...body, topic_id: node.parentId });
      }
      const body = {
        title: node.title,
        summary: node.summary || null,
        estimated_minutes: node.estimated_minutes,
        translations,
      };
      return node.id
        ? adminApi.lessons.update(node.id, body)
        : adminApi.lessons.create({ ...body, topic_id: node.parentId });
    }, t(node.id ? 'admin.a.saved' : 'admin.a.created'));

    setSaving(false);
    if (ok) {
      setNode(null);
      await load();
    }
  }

  async function reorder(kind: 'units' | 'topics' | 'skills' | 'lessons', ids: number[]) {
    const ok = await run(() => adminApi.structure.reorder(kind, ids), t('admin.a.orderSaved'));
    if (ok) await load();
  }

  function moveWithin(list: { id: number }[], index: number, direction: -1 | 1): number[] | null {
    const target = index + direction;
    if (target < 0 || target >= list.length) return null;
    const ids = list.map((item) => item.id);
    [ids[index], ids[target]] = [ids[target], ids[index]];
    return ids;
  }

  async function removeNode() {
    if (!deleting) return;
    const remove =
      deleting.kind === 'unit'
        ? adminApi.units.remove
        : deleting.kind === 'topic'
          ? adminApi.topics.remove
          : deleting.kind === 'skill'
            ? adminApi.skills.remove
            : adminApi.lessons.remove;
    const ok = await run(() => remove(deleting.id), t('admin.a.deleted'));
    if (ok !== undefined) await load();
  }

  if (authLoading || !user) return <AdminShell loading />;

  return (
    <AdminShell
      title={course ? label(course, 'title') : t('admin.a.course')}
      description={
        course
          ? t('admin.crs.courseMeta', {
              // `subject_name` is borrowed from the parent row, so the API already localised
              // it; the course's own title has to be picked here, where both languages are.
              subject: course.subject_name ?? '',
              grade: course.grade,
              modules: course.units.length,
            })
          : undefined
      }
      breadcrumbs={[
        { label: t('admin.a.adminCrumb'), href: '/admin' },
        { label: t('admin.crs.title'), href: '/admin/courses' },
        { label: course ? label(course, 'title') : '…' },
      ]}
      actions={
        course && (
          <>
            <Button variant="outline" onClick={openCourseEditor}>
              <Pencil className="h-4 w-4" aria-hidden="true" />{t('admin.crs.editDetails')}</Button>
            {course.status === 'published' ? (
              <Button variant="outline" onClick={() => setStatus('draft')}>{t('admin.a.unpublish')}</Button>
            ) : (
              <Button onClick={() => setStatus('published')}>{t('admin.a.publish')}</Button>
            )}
          </>
        )
      }
    >
      {loading || !course ? (
        <p className="py-16 text-center text-sm text-ink-500">{t('admin.a.loading')}</p>
      ) : (
        <>
          <Card className="mb-6 flex flex-wrap items-center gap-4">
            <StatusBadge value={course.status} />
            <span className="text-sm text-ink-600">
              {course.unit_count ?? course.units.length} modules ·{' '}
              {course.units.reduce((sum, unit) => sum + unit.topics.length, 0)} topics ·{' '}
              {course.units.reduce(
                (sum, unit) =>
                  sum + unit.topics.reduce((inner, topic) => inner + topic.lessons.length, 0),
                0,
              )}{' '}
              lessons
            </span>
            {course.categories.map((category) => (
              <Badge key={category.id} tone="brand">
                {category.name}
              </Badge>
            ))}
            <div className="ml-auto">
              <Button
                size="sm"
                onClick={() => setNode({ ...BLANK_NODE, kind: 'unit', parentId: courseId })}
              >
                <Plus className="h-4 w-4" aria-hidden="true" />{t('admin.crs.addModule')}</Button>
            </div>
          </Card>

          {course.units.length === 0 ? (
            <Card>
              <div className="py-8 text-center">
                <p className="font-bold text-ink-800">{t('admin.crs.noModules')}</p>
                <p className="mt-1 text-sm text-ink-500">{t('admin.crs.noModulesBody')}</p>
                <Button
                  className="mt-4"
                  onClick={() => setNode({ ...BLANK_NODE, kind: 'unit', parentId: courseId })}
                >
                  <Plus className="h-4 w-4" aria-hidden="true" />{t('admin.crs.addFirstModule')}</Button>
              </div>
            </Card>
          ) : (
            <ul className="space-y-3">
              {course.units.map((unit, unitIndex) => (
                <li key={unit.id}>
                  <Card className="p-0">
                    <div className="flex flex-wrap items-center gap-2 border-b-2 border-ink-100 p-4">
                      <button
                        type="button"
                        onClick={() =>
                          setExpanded((current) => ({ ...current, [unit.id]: !current[unit.id] }))
                        }
                        aria-expanded={Boolean(expanded[unit.id])}
                        className="rounded-lg p-1 text-ink-500 hover:bg-ink-100"
                      >
                        {expanded[unit.id] ? (
                          <ChevronDown className="h-4 w-4" aria-hidden="true" />
                        ) : (
                          <ChevronRight className="h-4 w-4" aria-hidden="true" />
                        )}
                      </button>
                      <div className="min-w-0 flex-1">
                        <p className="font-display text-lg">{label(unit, 'title')}</p>
                        <p className="truncate text-xs text-ink-500">
                          {t('admin.crs.topicCount', { count: unit.topics.length })}
                          {unit.summary ? ` · ${label(unit, 'summary')}` : ''}
                        </p>
                      </div>
                      <NodeControls
                        onUp={() => {
                          const ids = moveWithin(course.units, unitIndex, -1);
                          if (ids) void reorder('units', ids);
                        }}
                        onDown={() => {
                          const ids = moveWithin(course.units, unitIndex, 1);
                          if (ids) void reorder('units', ids);
                        }}
                        onEdit={() =>
                          setNode({
                            ...BLANK_NODE,
                            kind: 'unit',
                            id: unit.id,
                            parentId: courseId,
                            title: unit.title,
                            summary: unit.summary ?? '',
                            ...nodeTranslations(unit.translations, 'title'),
                          })
                        }
                        onDelete={() =>
                          setDeleting({ kind: 'unit', id: unit.id, label: label(unit, 'title') })
                        }
                        label={label(unit, 'title')}
                      />
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() =>
                          setNode({ ...BLANK_NODE, kind: 'topic', parentId: unit.id })
                        }
                      >
                        <Plus className="h-4 w-4" aria-hidden="true" />{t('admin.crs.topic')}</Button>
                    </div>

                    {expanded[unit.id] && (
                      <div className="divide-y divide-ink-100">
                        {unit.topics.length === 0 ? (
                          <p className="p-4 text-sm text-ink-500">
                            {t('admin.crs.noTopicsBody')}
                          </p>
                        ) : (
                          unit.topics.map((topic, topicIndex) => (
                            <TopicRow
                              key={topic.id}
                              topic={topic}
                              locale={locale}
                              onUp={() => {
                                const ids = moveWithin(unit.topics, topicIndex, -1);
                                if (ids) void reorder('topics', ids);
                              }}
                              onDown={() => {
                                const ids = moveWithin(unit.topics, topicIndex, 1);
                                if (ids) void reorder('topics', ids);
                              }}
                              onEdit={() =>
                                setNode({
                                  ...BLANK_NODE,
                                  kind: 'topic',
                                  id: topic.id,
                                  parentId: unit.id,
                                  title: topic.title,
                                  summary: topic.summary ?? '',
                                  ...nodeTranslations(topic.translations, 'title'),
                                })
                              }
                              onDelete={() =>
                                setDeleting({ kind: 'topic', id: topic.id, label: label(topic, 'title') })
                              }
                              onAddSkill={() =>
                                setNode({ ...BLANK_NODE, kind: 'skill', parentId: topic.id })
                              }
                              onAddLesson={() =>
                                setNode({ ...BLANK_NODE, kind: 'lesson', parentId: topic.id })
                              }
                              onEditSkill={(skill) =>
                                setNode({
                                  ...BLANK_NODE,
                                  kind: 'skill',
                                  id: skill.id,
                                  parentId: topic.id,
                                  title: skill.name,
                                  difficulty: skill.difficulty,
                                  ...nodeTranslations(skill.translations, 'name'),
                                })
                              }
                              onDeleteSkill={(skill) =>
                                setDeleting({ kind: 'skill', id: skill.id, label: label(skill, 'name') })
                              }
                              onReorderSkills={(ids) => void reorder('skills', ids)}
                              onReorderLessons={(ids) => void reorder('lessons', ids)}
                            />
                          ))
                        )}
                      </div>
                    )}
                  </Card>
                </li>
              ))}
            </ul>
          )}
        </>
      )}

      {/* node editor */}
      <Modal
        open={node !== null}
        onClose={() => setNode(null)}
        title={
          node
            ? t(node.id ? 'admin.crs.editNode' : 'admin.crs.newNode', {
                kind: t(`admin.crs.kind.${node.kind}`),
              })
            : ''
        }
        footer={
          <>
            <Button variant="ghost" onClick={() => setNode(null)}>{t('admin.a.cancel')}</Button>
            <Button loading={saving} onClick={saveNode}>
              {node?.id ? t('admin.a.saveChanges') : t('admin.a.create')}
            </Button>
          </>
        }
      >
        {node && (
          <div className="space-y-4">
            <FormRow
              label={node.kind === 'skill' ? t('admin.crs.skillName') : t('admin.a.title')}
              required
              htmlFor="node-title"
            >
              <TextField
                id="node-title"
                value={node.title}
                onChange={(event) => setNode({ ...node, title: event.target.value })}
                placeholder={
                  node.kind === 'unit'
                    ? t('admin.crs.placeholderModule')
                    : node.kind === 'topic'
                      ? t('admin.crs.placeholderTopic')
                      : node.kind === 'skill'
                        ? t('admin.crs.placeholderSkill')
                        : t('admin.crs.placeholderLesson')
                }
              />
            </FormRow>

            {node.kind !== 'skill' && (
              <FormRow label={t('admin.a.summary')} htmlFor="node-summary">
                <TextAreaField
                  id="node-summary"
                  value={node.summary}
                  onChange={(event) => setNode({ ...node, summary: event.target.value })}
                />
              </FormRow>
            )}

            {node.kind === 'skill' && (
              <>
                <FormRow label={t('admin.a.description')} htmlFor="node-desc">
                  <TextAreaField
                    id="node-desc"
                    value={node.summary}
                    onChange={(event) => setNode({ ...node, summary: event.target.value })}
                  />
                </FormRow>
                <FormRow
                  label={t('admin.crs.difficulty')}
                  htmlFor="node-difficulty"
                  hint={t('admin.crs.difficultyHint')}
                >
                  <SelectField
                    id="node-difficulty"
                    value={node.difficulty}
                    onChange={(event) =>
                      setNode({ ...node, difficulty: Number(event.target.value) })
                    }
                  >
                    {[1, 2, 3, 4, 5].map((value) => (
                      <option key={value} value={value}>
                        {value}
                      </option>
                    ))}
                  </SelectField>
                </FormRow>
              </>
            )}

            {node.kind === 'lesson' && (
              <FormRow label={t('admin.crs.estimatedMinutes')} htmlFor="node-minutes">
                <TextField
                  id="node-minutes"
                  type="number"
                  min={1}
                  max={600}
                  value={node.estimated_minutes}
                  onChange={(event) =>
                    setNode({ ...node, estimated_minutes: Number(event.target.value) })
                  }
                />
              </FormRow>
            )}

            <TranslationPanel
              fields={[
                {
                  name: 'viTitle',
                  label: node.kind === 'skill' ? t('admin.crs.skillName') : t('admin.a.title'),
                },
                {
                  name: 'viSummary',
                  label:
                    node.kind === 'skill' ? t('admin.a.description') : t('admin.a.summary'),
                  multiline: true,
                },
              ]}
              value={{ viTitle: node.viTitle, viSummary: node.viSummary }}
              onChange={(next) =>
                setNode({ ...node, viTitle: next.viTitle ?? '', viSummary: next.viSummary ?? '' })
              }
            />

            {node.kind === 'lesson' && !node.id && (
              <p className="rounded-2xl bg-brand-50 p-3 text-xs text-brand-800">
                The lesson is created as a draft. You will be able to build its content blocks from
                the lesson editor.
              </p>
            )}
          </div>
        )}
      </Modal>

      {/* course details */}
      <Modal
        open={editingCourse}
        onClose={() => setEditingCourse(false)}
        title={t('admin.crs.courseDetails')}
        size="lg"
        footer={
          <>
            <Button variant="ghost" onClick={() => setEditingCourse(false)}>{t('admin.a.cancel')}</Button>
            <Button loading={saving} onClick={saveCourse}>{t('admin.a.saveChanges')}</Button>
          </>
        }
      >
        <div className="grid gap-4 sm:grid-cols-2">
          <FormRow label={t('admin.a.title')} required htmlFor="c-title" className="sm:col-span-2">
            <TextField
              id="c-title"
              value={courseForm.title}
              onChange={(event) => setCourseForm({ ...courseForm, title: event.target.value })}
            />
          </FormRow>
          <div className="sm:col-span-2 order-last">
            <TranslationPanel
              fields={[
                { name: 'title', label: t('admin.a.title') },
                { name: 'summary', label: t('admin.a.summary'), multiline: true },
                { name: 'description', label: t('admin.a.description'), multiline: true },
              ]}
              value={courseVi}
              onChange={setCourseVi}
            />
          </div>
          <FormRow label={t('admin.a.summary')} htmlFor="c-summary" className="sm:col-span-2">
            <TextAreaField
              id="c-summary"
              value={courseForm.summary}
              onChange={(event) => setCourseForm({ ...courseForm, summary: event.target.value })}
            />
          </FormRow>
          <FormRow label={t('admin.a.description')} htmlFor="c-desc" className="sm:col-span-2">
            <TextAreaField
              id="c-desc"
              value={courseForm.description}
              onChange={(event) =>
                setCourseForm({ ...courseForm, description: event.target.value })
              }
            />
          </FormRow>
          <FormRow label={t('admin.a.thumbnailUrl')} htmlFor="c-thumb">
            <TextField
              id="c-thumb"
              value={courseForm.thumbnail_url}
              onChange={(event) =>
                setCourseForm({ ...courseForm, thumbnail_url: event.target.value })
              }
            />
          </FormRow>
          <FormRow label={t('admin.crs.estimatedHours')} htmlFor="c-hours">
            <TextField
              id="c-hours"
              type="number"
              min={0}
              value={courseForm.estimated_hours}
              onChange={(event) =>
                setCourseForm({ ...courseForm, estimated_hours: Number(event.target.value) })
              }
            />
          </FormRow>
          <FormRow label={t('admin.a.seoTitle')} htmlFor="c-seo-title">
            <TextField
              id="c-seo-title"
              value={courseForm.seo_title}
              onChange={(event) => setCourseForm({ ...courseForm, seo_title: event.target.value })}
            />
          </FormRow>
          <FormRow label={t('admin.a.seoDescription')} htmlFor="c-seo-desc">
            <TextField
              id="c-seo-desc"
              value={courseForm.seo_description}
              onChange={(event) =>
                setCourseForm({ ...courseForm, seo_description: event.target.value })
              }
            />
          </FormRow>
          <FormRow label={t('admin.a.categories')} className="sm:col-span-2">
            <div className="flex flex-wrap gap-1.5">
              {categories.map((category) => {
                const selected = courseForm.category_ids.includes(category.id);
                return (
                  <button
                    key={category.id}
                    type="button"
                    onClick={() =>
                      setCourseForm({
                        ...courseForm,
                        category_ids: selected
                          ? courseForm.category_ids.filter((cid) => cid !== category.id)
                          : [...courseForm.category_ids, category.id],
                      })
                    }
                    className={`rounded-full border-2 px-3 py-1 text-xs font-bold ${
                      selected
                        ? 'border-brand-500 bg-brand-500 text-white'
                        : 'border-ink-200 text-ink-700'
                    }`}
                  >
                    {label(category, 'name')}
                  </button>
                );
              })}
            </div>
          </FormRow>
          <div className="sm:col-span-2">
            <CheckboxField
              label={t('admin.a.featureOnHome')}
              checked={courseForm.is_featured}
              onChange={(value) => setCourseForm({ ...courseForm, is_featured: value })}
            />
          </div>
        </div>
      </Modal>

      <ConfirmDialog
        open={deleting !== null}
        onClose={() => setDeleting(null)}
        title={t('admin.a.deleteQ', { name: deleting?.label ?? '' })}
        message={
          deleting?.kind === 'skill'
            ? t('admin.crs.deleteSkillBody')
            : deleting?.kind === 'lesson'
              ? t('admin.crs.deleteLessonBody')
              : t('admin.crs.deleteContainerBody')
        }
        onConfirm={removeNode}
      />
    </AdminShell>
  );
}

function NodeControls({
  onUp,
  onDown,
  onEdit,
  onDelete,
  label,
}: {
  onUp: () => void;
  onDown: () => void;
  onEdit: () => void;
  onDelete: () => void;
  label: string;
}) {
  const { t } = useI18n();
  return (
    <div className="flex items-center gap-0.5">
      <button
        type="button"
        onClick={onUp}
        aria-label={t('admin.a.moveUpAria', { name: label })}
        className="rounded-lg p-1.5 text-ink-400 hover:bg-ink-100 hover:text-ink-700"
      >
        <ArrowUp className="h-4 w-4" aria-hidden="true" />
      </button>
      <button
        type="button"
        onClick={onDown}
        aria-label={t('admin.a.moveDownAria', { name: label })}
        className="rounded-lg p-1.5 text-ink-400 hover:bg-ink-100 hover:text-ink-700"
      >
        <ArrowDown className="h-4 w-4" aria-hidden="true" />
      </button>
      <button
        type="button"
        onClick={onEdit}
        aria-label={t('admin.a.editAria', { name: label })}
        className="rounded-lg p-1.5 text-ink-400 hover:bg-ink-100 hover:text-ink-700"
      >
        <Pencil className="h-4 w-4" aria-hidden="true" />
      </button>
      <button
        type="button"
        onClick={onDelete}
        aria-label={t('admin.a.deleteAria', { name: label })}
        className="rounded-lg p-1.5 text-coral-500 hover:bg-coral-50"
      >
        <Trash2 className="h-4 w-4" aria-hidden="true" />
      </button>
    </div>
  );
}

function TopicRow({
  topic,
  locale,
  onUp,
  onDown,
  onEdit,
  onDelete,
  onAddSkill,
  onAddLesson,
  onEditSkill,
  onDeleteSkill,
  onReorderLessons,
  onReorderSkills,
}: {
  topic: StructureTopic;
  locale: string;
  onUp: () => void;
  onDown: () => void;
  onEdit: () => void;
  onDelete: () => void;
  onAddSkill: () => void;
  onAddLesson: () => void;
  onEditSkill: (skill: StructureTopic['skills'][number]) => void;
  onDeleteSkill: (skill: StructureTopic['skills'][number]) => void;
  onReorderLessons: (ids: number[]) => void;
  onReorderSkills: (ids: number[]) => void;
}) {
  const { t } = useI18n();
  const label = useContentLabel();
  const href = (path: string) => `/${locale}${path}`;

  return (
    <div className="bg-ink-50/30 p-4 pl-10">
      <div className="flex flex-wrap items-center gap-2">
        <div className="min-w-0 flex-1">
          <p className="font-bold text-ink-900">{label(topic, 'title')}</p>
          <p className="truncate text-xs text-ink-500">
            {t('admin.crs.lessonSkillCount', {
              lessons: topic.lessons.length,
              skills: topic.skills.length,
            })}
          </p>
        </div>
        <NodeControls
          onUp={onUp}
          onDown={onDown}
          onEdit={onEdit}
          onDelete={onDelete}
          label={label(topic, 'title')}
        />
        <Button size="sm" variant="ghost" onClick={onAddSkill}>
          <Target className="h-4 w-4" aria-hidden="true" />{t('admin.crs.skill')}</Button>
        <Button size="sm" variant="ghost" onClick={onAddLesson}>
          <FileText className="h-4 w-4" aria-hidden="true" />{t('admin.crs.lesson')}</Button>
      </div>

      {topic.lessons.length > 0 && (
        <ul className="mt-3 space-y-1">
          {topic.lessons.map((lesson, index) => (
            <li
              key={lesson.id}
              className="flex flex-wrap items-center gap-2 rounded-xl bg-white px-3 py-2"
            >
              <FileText className="h-4 w-4 shrink-0 text-brand-500" aria-hidden="true" />
              <Link
                href={href(`/admin/lessons/${lesson.id}`)}
                className="min-w-0 flex-1 truncate text-sm font-semibold text-ink-800 hover:text-brand-700 hover:underline"
              >
                {label(lesson, 'title')}
              </Link>
              <span className="text-xs text-ink-400">
                {t('admin.a.blockCount', { count: lesson.block_count })}
              </span>
              {lesson.has_draft && <Badge tone="sun">{t('admin.crs.unpublishedEdits')}</Badge>}
              <StatusBadge value={lesson.status} />
              <div className="flex gap-0.5">
                <button
                  type="button"
                  aria-label={t('admin.a.moveUpAria', { name: label(lesson, 'title') })}
                  onClick={() => {
                    if (index === 0) return;
                    const ids = topic.lessons.map((l) => l.id);
                    [ids[index], ids[index - 1]] = [ids[index - 1], ids[index]];
                    onReorderLessons(ids);
                  }}
                  className="rounded-lg p-1 text-ink-400 hover:bg-ink-100"
                >
                  <ArrowUp className="h-3.5 w-3.5" aria-hidden="true" />
                </button>
                <button
                  type="button"
                  aria-label={t('admin.a.moveDownAria', { name: label(lesson, 'title') })}
                  onClick={() => {
                    if (index === topic.lessons.length - 1) return;
                    const ids = topic.lessons.map((l) => l.id);
                    [ids[index], ids[index + 1]] = [ids[index + 1], ids[index]];
                    onReorderLessons(ids);
                  }}
                  className="rounded-lg p-1 text-ink-400 hover:bg-ink-100"
                >
                  <ArrowDown className="h-3.5 w-3.5" aria-hidden="true" />
                </button>
              </div>
            </li>
          ))}
        </ul>
      )}

      {topic.skills.length > 0 && (
        <ul className="mt-2 flex flex-wrap gap-1.5">
          {topic.skills.map((skill, index) => (
            <li
              key={skill.id}
              className="inline-flex items-center gap-1.5 rounded-full bg-white py-1 pl-3 pr-1 text-xs"
            >
              <Target className="h-3 w-3 text-teal-600" aria-hidden="true" />
              <span className="font-semibold text-ink-800">{label(skill, 'name')}</span>
              <Link
                href={href(`/admin/exercises?skill_id=${skill.id}`)}
                className="rounded-full bg-ink-100 px-1.5 font-bold text-ink-600 hover:bg-brand-100"
                title={t('admin.crs.exercisesForSkill')}
              >
                {skill.question_count}
              </Link>
              <button
                type="button"
                aria-label={t('admin.a.moveUpAria', { name: label(skill, 'name') })}
                onClick={() => {
                  if (index === 0) return;
                  const ids = topic.skills.map((s) => s.id);
                  [ids[index], ids[index - 1]] = [ids[index - 1], ids[index]];
                  onReorderSkills(ids);
                }}
                className="rounded-full p-0.5 text-ink-400 hover:bg-ink-100"
              >
                <ArrowUp className="h-3 w-3" aria-hidden="true" />
              </button>
              <button
                type="button"
                onClick={() => onEditSkill(skill)}
                aria-label={t('admin.a.editAria', { name: label(skill, 'name') })}
                className="rounded-full p-0.5 text-ink-400 hover:bg-ink-100"
              >
                <Pencil className="h-3 w-3" aria-hidden="true" />
              </button>
              <button
                type="button"
                onClick={() => onDeleteSkill(skill)}
                aria-label={t('admin.a.deleteAria', { name: label(skill, 'name') })}
                className="rounded-full p-0.5 text-coral-500 hover:bg-coral-50"
              >
                <Trash2 className="h-3 w-3" aria-hidden="true" />
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
