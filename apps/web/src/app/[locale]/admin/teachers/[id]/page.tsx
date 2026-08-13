'use client';

import Link from 'next/link';
import { ExternalLink, KeyRound, Plus, Trash2 } from 'lucide-react';
import { use, useCallback, useEffect, useState } from 'react';

import { Avatar, Badge, Button, Card } from '@hietedu/ui';

import { AdminShell } from '@/components/admin/admin-shell';
import { ConfirmDialog, Modal } from '@/components/admin/dialog';
import {
  CheckboxField,
  FormRow,
  SelectField,
  StatusBadge,
  StringListField,
  TextAreaField,
  TextField,
  humanise,
} from '@/components/admin/form';
import { useToast } from '@/components/admin/toast';
import { adminApi, type AdminClass, type AdminCourse, type TeacherCredential } from '@/lib/admin-api';
import { useRequireAuth } from '@/lib/auth';
import { useI18n } from '@/lib/i18n';

type Detail = Record<string, any>;

const CREDENTIAL_KINDS = [
  'education',
  'award',
  'certification',
  'publication',
  'competition',
  'experience',
];

const TABS = [
  { id: 'profile', labelKey: 'admin.tea.tab.profile' },
  { id: 'background', labelKey: 'admin.tea.tab.background' },
  { id: 'teaching', labelKey: 'admin.tea.tab.teaching' },
  { id: 'schedule', labelKey: 'admin.tea.tab.schedule' },
] as const;

type TabId = (typeof TABS)[number]['id'];

export default function TeacherDetailPage({
  params,
}: {
  params: Promise<{ locale: string; id: string }>;
}) {
  const { id } = use(params);
  const teacherId = Number(id);
  const { t, locale, formatDateTime } = useI18n();
  const { user, loading: authLoading } = useRequireAuth(locale, ['admin']);
  const { run, notify } = useToast();

  const [teacher, setTeacher] = useState<Detail | null>(null);
  const [loading, setLoading] = useState(true);
  const [tab, setTab] = useState<TabId>('profile');
  const [saving, setSaving] = useState(false);
  const [form, setForm] = useState<Record<string, any>>({});
  const [credential, setCredential] = useState<Partial<TeacherCredential> | null>(null);
  const [deletingCredential, setDeletingCredential] = useState<TeacherCredential | null>(null);
  const [courses, setCourses] = useState<AdminCourse[]>([]);
  const [classes, setClasses] = useState<AdminClass[]>([]);
  const [assigning, setAssigning] = useState(false);
  const [assignment, setAssignment] = useState({ course_id: 0, class_id: 0 });

  const href = (path: string) => `/${locale}${path}`;

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const result = (await adminApi.teachers.get(teacherId)) as Detail;
      setTeacher(result);
      setForm({
        full_name: result.full_name ?? '',
        email: result.email ?? '',
        phone: result.phone ?? '',
        slug: result.slug ?? '',
        headline: result.headline ?? '',
        bio: result.bio ?? '',
        photo_url: result.photo_url ?? '',
        subjects: result.subjects ?? [],
        grades: (result.grades ?? []).map(String),
        qualifications: result.qualifications ?? [],
        specializations: result.specializations ?? [],
        learning_formats: result.learning_formats ?? [],
        languages: result.languages ?? [],
        years_experience: result.years_experience ?? 0,
        hourly_rate_vnd: result.hourly_rate_vnd ?? '',
        teaching_philosophy: result.teaching_philosophy ?? '',
        teaching_style: result.teaching_style ?? '',
        video_intro_url: result.video_intro_url ?? '',
        public_email: result.public_email ?? '',
        public_phone: result.public_phone ?? '',
        social_facebook: result.social_links?.facebook ?? '',
        social_youtube: result.social_links?.youtube ?? '',
        is_featured: result.is_featured ?? false,
        accepts_one_to_one: result.accepts_one_to_one ?? true,
      });
    } catch (caught) {
      notify((caught as Error).message, 'error');
    } finally {
      setLoading(false);
    }
  }, [teacherId, notify]);

  useEffect(() => {
    if (user) void load();
  }, [user, load]);

  useEffect(() => {
    if (!user) return;
    adminApi.courses.list({ page_size: 100 }).then((p) => setCourses(p.items)).catch(() => undefined);
    adminApi.classes.list({ page_size: 100 }).then((p) => setClasses(p.items)).catch(() => undefined);
  }, [user]);

  async function saveProfile() {
    setSaving(true);
    const ok = await run(
      () =>
        adminApi.teachers.update(teacherId, {
          full_name: form.full_name,
          email: form.email,
          phone: form.phone || null,
          slug: form.slug || undefined,
          headline: form.headline || null,
          bio: form.bio || null,
          photo_url: form.photo_url || null,
          subjects: form.subjects,
          grades: (form.grades as string[]).map(Number).filter(Number.isFinite),
          qualifications: form.qualifications,
          specializations: form.specializations,
          learning_formats: form.learning_formats,
          languages: form.languages,
          years_experience: Number(form.years_experience) || 0,
          hourly_rate_vnd: form.hourly_rate_vnd === '' ? null : Number(form.hourly_rate_vnd),
          teaching_philosophy: form.teaching_philosophy || null,
          teaching_style: form.teaching_style || null,
          video_intro_url: form.video_intro_url || null,
          public_email: form.public_email || null,
          public_phone: form.public_phone || null,
          social_links: {
            ...(form.social_facebook ? { facebook: form.social_facebook } : {}),
            ...(form.social_youtube ? { youtube: form.social_youtube } : {}),
          },
          is_featured: form.is_featured,
          accepts_one_to_one: form.accepts_one_to_one,
        }),
      t('admin.tea.saved'),
    );
    setSaving(false);
    if (ok) await load();
  }

  if (authLoading || !user) return <AdminShell loading />;

  const credentialsByKind = ((teacher?.credentials ?? []) as TeacherCredential[]).reduce(
    (acc, item) => {
      (acc[item.kind] ??= []).push(item);
      return acc;
    },
    {} as Record<string, TeacherCredential[]>,
  );

  return (
    <AdminShell
      title={teacher?.full_name ?? 'Teacher'}
      description={teacher?.headline ?? undefined}
      breadcrumbs={[
        { label: t('admin.a.adminCrumb'), href: '/admin' },
        { label: t('admin.tea.title'), href: '/admin/teachers' },
        { label: teacher?.full_name ?? '…' },
      ]}
      actions={
        teacher && (
          <>
            {teacher.is_published && teacher.slug && (
              <Link href={href(`/teachers/${teacher.slug}`)} target="_blank">
                <Button variant="outline">
                  <ExternalLink className="h-4 w-4" aria-hidden="true" />{t('admin.tea.viewPublic')}</Button>
              </Link>
            )}
            <Button
              variant="outline"
              onClick={async () => {
                const result = await run(() => adminApi.teachers.resetPassword(teacherId));
                if (result?.temporary_password) {
                  notify(`Temporary password: ${result.temporary_password}`, 'info', 'Shown once.');
                }
              }}
            >
              <KeyRound className="h-4 w-4" aria-hidden="true" />{t('admin.a.resetPassword')}</Button>
            <Button
              variant={teacher.is_published ? 'outline' : 'primary'}
              onClick={async () => {
                const ok = await run(
                  () =>
                    teacher.is_published
                      ? adminApi.teachers.unpublish(teacherId)
                      : adminApi.teachers.publish(teacherId),
                  teacher.is_published ? 'Profile hidden' : 'Profile published',
                );
                if (ok) await load();
              }}
            >
              {teacher.is_published ? 'Unpublish' : 'Publish profile'}
            </Button>
            <Button loading={saving} onClick={saveProfile}>{t('admin.a.save')}</Button>
          </>
        )
      }
    >
      {loading || !teacher ? (
        <p className="py-16 text-center text-sm text-ink-500">{t('admin.a.loading')}</p>
      ) : (
        <>
          <div className="mb-6 flex flex-wrap items-center gap-3">
            <Avatar name={teacher.full_name ?? ''} src={teacher.photo_url} size="lg" />
            <div className="min-w-0">
              <p className="font-display text-xl">{teacher.full_name}</p>
              <p className="text-sm text-ink-500">
                {teacher.email} · {teacher.years_experience} years
              </p>
            </div>
            <div className="ml-auto flex flex-wrap gap-2">
              {teacher.is_published ? (
                <Badge tone="teal">{t('admin.tea.publicProfile')}</Badge>
              ) : (
                <Badge tone="neutral">{t('admin.tea.profileHidden')}</Badge>
              )}
              {!teacher.is_active && <Badge tone="coral">{t('admin.tea.accountDisabled')}</Badge>}
            </div>
          </div>

          <div className="mb-4 flex flex-wrap gap-2 border-b-2 border-ink-100">
            {TABS.map((entry) => (
              <button
                key={entry.id}
                type="button"
                onClick={() => setTab(entry.id)}
                className={`-mb-0.5 border-b-4 px-3 py-2 text-sm font-bold ${
                  tab === entry.id
                    ? 'border-brand-500 text-brand-700'
                    : 'border-transparent text-ink-500 hover:text-ink-800'
                }`}
              >
                {t(entry.labelKey)}
              </button>
            ))}
          </div>

          {tab === 'profile' && (
            <div className="grid gap-4 lg:grid-cols-2">
              <Card>
                <h2 className="font-display text-lg">{t('admin.tea.account')}</h2>
                <div className="mt-4 grid gap-4 sm:grid-cols-2">
                  <FormRow label={t('admin.stu.fullName')} required htmlFor="tp-name">
                    <TextField
                      id="tp-name"
                      value={form.full_name}
                      onChange={(e) => setForm({ ...form, full_name: e.target.value })}
                    />
                  </FormRow>
                  <FormRow label={t('admin.a.email')} required htmlFor="tp-email">
                    <TextField
                      id="tp-email"
                      type="email"
                      value={form.email}
                      onChange={(e) => setForm({ ...form, email: e.target.value })}
                    />
                  </FormRow>
                  <FormRow label={t('admin.a.phone')} htmlFor="tp-phone">
                    <TextField
                      id="tp-phone"
                      value={form.phone}
                      onChange={(e) => setForm({ ...form, phone: e.target.value })}
                    />
                  </FormRow>
                  <FormRow label={t('admin.tea.publicUrlSlug')} htmlFor="tp-slug" hint={`/teachers/${form.slug || '…'}`}>
                    <TextField
                      id="tp-slug"
                      value={form.slug}
                      onChange={(e) => setForm({ ...form, slug: e.target.value })}
                    />
                  </FormRow>
                </div>
              </Card>

              <Card>
                <h2 className="font-display text-lg">{t('admin.tea.publicProfile')}</h2>
                <div className="mt-4 space-y-4">
                  <FormRow label={t('admin.tea.photoUrl')} htmlFor="tp-photo">
                    <TextField
                      id="tp-photo"
                      value={form.photo_url}
                      onChange={(e) => setForm({ ...form, photo_url: e.target.value })}
                      placeholder="/media/image/…"
                    />
                  </FormRow>
                  <FormRow label={t('admin.tea.shortIntro')} htmlFor="tp-headline">
                    <TextField
                      id="tp-headline"
                      value={form.headline}
                      onChange={(e) => setForm({ ...form, headline: e.target.value })}
                    />
                  </FormRow>
                  <FormRow label={t('admin.tea.fullBio')} htmlFor="tp-bio">
                    <TextAreaField
                      id="tp-bio"
                      rows={5}
                      value={form.bio}
                      onChange={(e) => setForm({ ...form, bio: e.target.value })}
                    />
                  </FormRow>
                  <FormRow label={t('admin.tea.videoIntro')} htmlFor="tp-video">
                    <TextField
                      id="tp-video"
                      value={form.video_intro_url}
                      onChange={(e) => setForm({ ...form, video_intro_url: e.target.value })}
                    />
                  </FormRow>
                </div>
              </Card>

              <Card>
                <h2 className="font-display text-lg">{t('admin.tea.approach')}</h2>
                <div className="mt-4 space-y-4">
                  <FormRow label={t('admin.tea.philosophy')} htmlFor="tp-phil">
                    <TextAreaField
                      id="tp-phil"
                      value={form.teaching_philosophy}
                      onChange={(e) => setForm({ ...form, teaching_philosophy: e.target.value })}
                    />
                  </FormRow>
                  <FormRow label={t('admin.tea.style')} htmlFor="tp-style">
                    <TextAreaField
                      id="tp-style"
                      value={form.teaching_style}
                      onChange={(e) => setForm({ ...form, teaching_style: e.target.value })}
                    />
                  </FormRow>
                </div>
              </Card>

              <Card>
                <h2 className="font-display text-lg">{t('admin.tea.detailsContact')}</h2>
                <div className="mt-4 grid gap-4 sm:grid-cols-2">
                  <FormRow label={t('admin.tea.subjects')}>
                    <StringListField
                      values={form.subjects}
                      onChange={(subjects) => setForm({ ...form, subjects })}
                    />
                  </FormRow>
                  <FormRow label={t('admin.tea.gradesLabel2')}>
                    <StringListField
                      values={form.grades}
                      onChange={(grades) => setForm({ ...form, grades })}
                    />
                  </FormRow>
                  <FormRow label={t('admin.tea.specialisations')}>
                    <StringListField
                      values={form.specializations}
                      onChange={(specializations) => setForm({ ...form, specializations })}
                    />
                  </FormRow>
                  <FormRow label={t('admin.tea.learningFormats')}>
                    <StringListField
                      values={form.learning_formats}
                      onChange={(learning_formats) => setForm({ ...form, learning_formats })}
                      placeholder="one_to_one"
                    />
                  </FormRow>
                  <FormRow label={t('admin.tea.languages')}>
                    <StringListField
                      values={form.languages}
                      onChange={(languages) => setForm({ ...form, languages })}
                    />
                  </FormRow>
                  <FormRow label={t('admin.tea.qualifications')}>
                    <StringListField
                      values={form.qualifications}
                      onChange={(qualifications) => setForm({ ...form, qualifications })}
                    />
                  </FormRow>
                  <FormRow label={t('admin.tea.years')} htmlFor="tp-years">
                    <TextField
                      id="tp-years"
                      type="number"
                      min={0}
                      value={form.years_experience}
                      onChange={(e) => setForm({ ...form, years_experience: e.target.value })}
                    />
                  </FormRow>
                  <FormRow label={t('admin.tea.hourlyRate')} htmlFor="tp-rate">
                    <TextField
                      id="tp-rate"
                      type="number"
                      min={0}
                      value={form.hourly_rate_vnd}
                      onChange={(e) => setForm({ ...form, hourly_rate_vnd: e.target.value })}
                    />
                  </FormRow>
                  <FormRow label={t('admin.tea.publicEmail')} htmlFor="tp-pemail">
                    <TextField
                      id="tp-pemail"
                      value={form.public_email}
                      onChange={(e) => setForm({ ...form, public_email: e.target.value })}
                    />
                  </FormRow>
                  <FormRow label={t('admin.tea.publicPhone')} htmlFor="tp-pphone">
                    <TextField
                      id="tp-pphone"
                      value={form.public_phone}
                      onChange={(e) => setForm({ ...form, public_phone: e.target.value })}
                    />
                  </FormRow>
                  <FormRow label={t('admin.tea.facebook')} htmlFor="tp-fb">
                    <TextField
                      id="tp-fb"
                      value={form.social_facebook}
                      onChange={(e) => setForm({ ...form, social_facebook: e.target.value })}
                    />
                  </FormRow>
                  <FormRow label={t('admin.tea.youtube')} htmlFor="tp-yt">
                    <TextField
                      id="tp-yt"
                      value={form.social_youtube}
                      onChange={(e) => setForm({ ...form, social_youtube: e.target.value })}
                    />
                  </FormRow>
                  <div className="space-y-2 sm:col-span-2">
                    <CheckboxField
                      label={t('admin.a.featureOnHome')}
                      checked={form.is_featured}
                      onChange={(value) => setForm({ ...form, is_featured: value })}
                    />
                    <CheckboxField
                      label={t('admin.tea.acceptsOneToOne')}
                      checked={form.accepts_one_to_one}
                      onChange={(value) => setForm({ ...form, accepts_one_to_one: value })}
                    />
                  </div>
                </div>
              </Card>
            </div>
          )}

          {tab === 'background' && (
            <Card>
              <div className="flex items-center justify-between">
                <div>
                  <h2 className="font-display text-lg">{t('admin.tea.credentials')}</h2>
                  <p className="text-sm text-ink-600">{t('admin.tea.credentialsHint')}</p>
                </div>
                <Button
                  size="sm"
                  onClick={() => setCredential({ kind: 'education', title: '', is_published: true })}
                >
                  <Plus className="h-4 w-4" aria-hidden="true" />{t('admin.tea.addEntry')}</Button>
              </div>

              {(teacher.credentials ?? []).length === 0 ? (
                <p className="mt-6 text-sm text-ink-500">
                  Nothing added yet. Add degrees, awards, certifications and publications — each
                  as its own entry rather than one long paragraph.
                </p>
              ) : (
                <div className="mt-6 space-y-6">
                  {CREDENTIAL_KINDS.filter((kind) => credentialsByKind[kind]?.length).map(
                    (kind) => (
                      <section key={kind}>
                        <h3 className="font-display text-base">{humanise(kind)}</h3>
                        <ul className="mt-2 divide-y divide-ink-100">
                          {credentialsByKind[kind].map((item) => (
                            <li key={item.id} className="flex flex-wrap items-center gap-3 py-3">
                              <div className="min-w-0 flex-1">
                                <p className="font-semibold text-ink-900">{item.title}</p>
                                <p className="text-xs text-ink-500">
                                  {[
                                    item.organisation,
                                    item.year_start &&
                                      `${item.year_start}${item.year_end ? `–${item.year_end}` : ''}`,
                                  ]
                                    .filter(Boolean)
                                    .join(' · ')}
                                </p>
                                {item.description && (
                                  <p className="mt-1 text-sm text-ink-600">{item.description}</p>
                                )}
                              </div>
                              {!item.is_published && <Badge tone="neutral">{t('admin.a.hidden')}</Badge>}
                              <button
                                type="button"
                                aria-label={`Edit ${item.title}`}
                                onClick={() => setCredential(item)}
                                className="rounded-lg px-2 py-1 text-xs font-bold text-brand-600 hover:bg-brand-50"
                              >{t('admin.a.edit')}</button>
                              <button
                                type="button"
                                aria-label={`Delete ${item.title}`}
                                onClick={() => setDeletingCredential(item)}
                                className="rounded-lg p-1.5 text-coral-500 hover:bg-coral-50"
                              >
                                <Trash2 className="h-4 w-4" aria-hidden="true" />
                              </button>
                            </li>
                          ))}
                        </ul>
                      </section>
                    ),
                  )}
                </div>
              )}
            </Card>
          )}

          {tab === 'teaching' && (
            <div className="grid gap-4 lg:grid-cols-2">
              <Card>
                <div className="flex items-center justify-between">
                  <h2 className="font-display text-lg">{t('admin.tea.assignments')}</h2>
                  <Button size="sm" variant="outline" onClick={() => setAssigning(true)}>
                    <Plus className="h-4 w-4" aria-hidden="true" />{t('admin.a.assign')}</Button>
                </div>
                <p className="mt-1 text-sm text-ink-600">{t('admin.tea.assignmentsHint')}</p>
                {(teacher.assignments ?? []).length === 0 ? (
                  <p className="mt-4 text-sm text-ink-500">{t('admin.tea.noAssignments')}</p>
                ) : (
                  <ul className="mt-4 divide-y divide-ink-100">
                    {teacher.assignments.map((item: Detail) => (
                      <li key={item.id} className="flex items-center gap-3 py-2">
                        <span className="min-w-0 flex-1 truncate text-sm">
                          {item.course_title ?? item.subject_name ?? 'Subject'}
                          {item.grade ? ` · Grade ${item.grade}` : ''}
                        </span>
                        {item.is_lead && <Badge tone="brand">{t('admin.tea.lead')}</Badge>}
                        <button
                          type="button"
                          aria-label={t('admin.tea.removeAssignment')}
                          onClick={async () => {
                            const ok = await run(
                              () => adminApi.teachers.unassign(item.id),
                              t('admin.tea.assignmentRemoved'),
                            );
                            if (ok !== undefined) await load();
                          }}
                          className="rounded-lg p-1.5 text-coral-500 hover:bg-coral-50"
                        >
                          <Trash2 className="h-4 w-4" aria-hidden="true" />
                        </button>
                      </li>
                    ))}
                  </ul>
                )}
              </Card>

              <Card>
                <h2 className="font-display text-lg">{t('admin.tea.classCount')}</h2>
                {(teacher.classes ?? []).length === 0 ? (
                  <p className="mt-3 text-sm text-ink-500">{t('admin.tea.notTeaching')}</p>
                ) : (
                  <ul className="mt-3 divide-y divide-ink-100">
                    {teacher.classes.map((group: Detail) => (
                      <li key={group.id} className="flex flex-wrap items-center gap-2 py-3">
                        <Link
                          href={href(`/admin/classes/${group.id}`)}
                          className="min-w-0 flex-1 truncate font-semibold text-ink-900 hover:text-brand-700 hover:underline"
                        >
                          {group.name}
                        </Link>
                        <Badge tone="neutral">
                          {group.active}/{group.capacity} students
                        </Badge>
                      </li>
                    ))}
                  </ul>
                )}

                <h2 className="mt-6 font-display text-lg">{t('admin.tea.coursesOwned')}</h2>
                {(teacher.courses_taught ?? []).length === 0 ? (
                  <p className="mt-3 text-sm text-ink-500">{t('admin.tea.noCourses')}</p>
                ) : (
                  <ul className="mt-3 divide-y divide-ink-100">
                    {teacher.courses_taught.map((course: Detail) => (
                      <li key={course.id} className="flex items-center gap-2 py-2">
                        <Link
                          href={href(`/admin/courses/${course.id}`)}
                          className="min-w-0 flex-1 truncate text-sm font-semibold hover:underline"
                        >
                          {course.title}
                        </Link>
                        <StatusBadge value={course.status} />
                      </li>
                    ))}
                  </ul>
                )}
              </Card>

              <Card className="lg:col-span-2">
                <h2 className="font-display text-lg">{t('admin.tea.students')}</h2>
                {(teacher.students ?? []).length === 0 ? (
                  <p className="mt-3 text-sm text-ink-500">{t('admin.tea.noStudents')}</p>
                ) : (
                  <ul className="mt-3 grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
                    {teacher.students.map((student: Detail) => (
                      <li key={`${student.class_id}-${student.id}`}>
                        <Link
                          href={href(`/admin/students/${student.id}`)}
                          className="block rounded-2xl border-2 border-ink-100 p-3 hover:border-brand-300"
                        >
                          <p className="truncate font-semibold text-ink-900">{student.name}</p>
                          <p className="truncate text-xs text-ink-500">
                            Grade {student.grade} · {humanise(student.status)}
                          </p>
                        </Link>
                      </li>
                    ))}
                  </ul>
                )}
              </Card>
            </div>
          )}

          {tab === 'schedule' && (
            <div className="grid gap-4 lg:grid-cols-2">
              <Card>
                <h2 className="font-display text-lg">{t('admin.tea.weeklySlots')}</h2>
                {(teacher.schedule_slots ?? []).length === 0 ? (
                  <p className="mt-3 text-sm text-ink-500">{t('admin.tea.noSlots')}</p>
                ) : (
                  <ul className="mt-3 flex flex-wrap gap-1.5">
                    {teacher.schedule_slots.map((slot: Detail) => (
                      <li key={slot.id}>
                        <Badge tone="brand">
                          {['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'][slot.weekday % 7]}{' '}
                          {slot.start_time}–{slot.end_time}
                        </Badge>
                      </li>
                    ))}
                  </ul>
                )}
              </Card>

              <Card>
                <h2 className="font-display text-lg">{t('admin.tea.sessions')}</h2>
                {(teacher.sessions ?? []).length === 0 ? (
                  <p className="mt-3 text-sm text-ink-500">{t('admin.tea.noSessions')}</p>
                ) : (
                  <ul className="mt-3 max-h-96 divide-y divide-ink-100 overflow-y-auto">
                    {teacher.sessions.map((session: Detail) => (
                      <li key={session.id} className="flex flex-wrap items-center gap-2 py-2">
                        <div className="min-w-0 flex-1">
                          <p className="truncate text-sm font-semibold">{session.title}</p>
                          <p className="text-xs text-ink-500">{session.class_name}</p>
                        </div>
                        <span className="text-xs text-ink-500">
                          {formatDateTime(session.starts_at)}
                        </span>
                      </li>
                    ))}
                  </ul>
                )}
              </Card>
            </div>
          )}
        </>
      )}

      {/* credential editor */}
      <Modal
        open={credential !== null}
        onClose={() => setCredential(null)}
        title={credential?.id ? 'Edit entry' : 'Add entry'}
        footer={
          <>
            <Button variant="ghost" onClick={() => setCredential(null)}>{t('admin.a.cancel')}</Button>
            <Button
              onClick={async () => {
                if (!credential?.title?.trim()) {
                  notify(t('admin.a.titleRequired'), 'error');
                  return;
                }
                const body = {
                  kind: credential.kind ?? 'award',
                  title: credential.title,
                  organisation: credential.organisation || null,
                  year_start: credential.year_start || null,
                  year_end: credential.year_end || null,
                  description: credential.description || null,
                  url: credential.url || null,
                  is_published: credential.is_published ?? true,
                };
                const ok = await run(
                  () =>
                    credential.id
                      ? adminApi.teachers.updateCredential(credential.id, body)
                      : adminApi.teachers.addCredential(teacherId, body),
                  t('admin.a.saved'),
                );
                if (ok) {
                  setCredential(null);
                  await load();
                }
              }}
            >{t('admin.a.save')}</Button>
          </>
        }
      >
        {credential && (
          <div className="grid gap-4 sm:grid-cols-2">
            <FormRow label={t('admin.tea.typeLabel')} required htmlFor="cr-kind">
              <SelectField
                id="cr-kind"
                value={credential.kind ?? 'award'}
                onChange={(e) => setCredential({ ...credential, kind: e.target.value })}
              >
                {CREDENTIAL_KINDS.map((kind) => (
                  <option key={kind} value={kind}>
                    {humanise(kind)}
                  </option>
                ))}
              </SelectField>
            </FormRow>
            <FormRow label={t('admin.tea.organisation')} htmlFor="cr-org">
              <TextField
                id="cr-org"
                value={credential.organisation ?? ''}
                onChange={(e) => setCredential({ ...credential, organisation: e.target.value })}
                placeholder={t('admin.tea.orgPlaceholder')}
              />
            </FormRow>
            <FormRow label={t('admin.a.title')} required htmlFor="cr-title" className="sm:col-span-2">
              <TextField
                id="cr-title"
                value={credential.title ?? ''}
                onChange={(e) => setCredential({ ...credential, title: e.target.value })}
                placeholder={t('admin.tea.credentialTitlePlaceholder')}
              />
            </FormRow>
            <FormRow label={t('admin.tea.startYear')} htmlFor="cr-start">
              <TextField
                id="cr-start"
                type="number"
                value={credential.year_start ?? ''}
                onChange={(e) =>
                  setCredential({
                    ...credential,
                    year_start: e.target.value ? Number(e.target.value) : null,
                  })
                }
              />
            </FormRow>
            <FormRow label={t('admin.tea.endYear')} htmlFor="cr-end">
              <TextField
                id="cr-end"
                type="number"
                value={credential.year_end ?? ''}
                onChange={(e) =>
                  setCredential({
                    ...credential,
                    year_end: e.target.value ? Number(e.target.value) : null,
                  })
                }
              />
            </FormRow>
            <FormRow label={t('admin.a.description')} htmlFor="cr-desc" className="sm:col-span-2">
              <TextAreaField
                id="cr-desc"
                value={credential.description ?? ''}
                onChange={(e) => setCredential({ ...credential, description: e.target.value })}
              />
            </FormRow>
            <div className="sm:col-span-2">
              <CheckboxField
                label={t('admin.tea.showOnProfile')}
                checked={credential.is_published ?? true}
                onChange={(value) => setCredential({ ...credential, is_published: value })}
              />
            </div>
          </div>
        )}
      </Modal>

      {/* assignment */}
      <Modal
        open={assigning}
        onClose={() => setAssigning(false)}
        title={t('admin.tea.assignTitle')}
        footer={
          <>
            <Button variant="ghost" onClick={() => setAssigning(false)}>{t('admin.a.cancel')}</Button>
            <Button
              onClick={async () => {
                if (assignment.class_id) {
                  const ok = await run(
                    () => adminApi.teachers.assignClass(teacherId, assignment.class_id),
                    t('admin.tea.classAssigned'),
                  );
                  if (ok) {
                    setAssigning(false);
                    await load();
                  }
                  return;
                }
                if (!assignment.course_id) {
                  notify(t('admin.tea.chooseCourseOrClass'), 'error');
                  return;
                }
                const course = courses.find((c) => c.id === assignment.course_id);
                const ok = await run(
                  () =>
                    adminApi.teachers.assign(teacherId, {
                      course_id: assignment.course_id,
                      subject_id: course?.subject_id ?? null,
                      grade: course?.grade ?? null,
                    }),
                  t('admin.tea.courseAssigned'),
                );
                if (ok) {
                  setAssigning(false);
                  await load();
                }
              }}
            >{t('admin.a.assign')}</Button>
          </>
        }
      >
        <div className="space-y-4">
          <FormRow label={t('admin.a.course')} htmlFor="as-course">
            <SelectField
              id="as-course"
              value={assignment.course_id}
              onChange={(e) =>
                setAssignment({ course_id: Number(e.target.value), class_id: 0 })
              }
            >
              <option value={0}>{t('admin.a.none')}</option>
              {courses.map((course) => (
                <option key={course.id} value={course.id}>
                  {course.title}
                </option>
              ))}
            </SelectField>
          </FormRow>
          <FormRow label={t('admin.tea.orAssignClass')} htmlFor="as-class">
            <SelectField
              id="as-class"
              value={assignment.class_id}
              onChange={(e) =>
                setAssignment({ course_id: 0, class_id: Number(e.target.value) })
              }
            >
              <option value={0}>{t('admin.a.none')}</option>
              {classes.map((group) => (
                <option key={group.id} value={group.id}>
                  {group.name}
                  {group.teacher_name ? ` (currently ${group.teacher_name})` : ''}
                </option>
              ))}
            </SelectField>
          </FormRow>
        </div>
      </Modal>

      <ConfirmDialog
        open={deletingCredential !== null}
        onClose={() => setDeletingCredential(null)}
        title={`Delete “${deletingCredential?.title}”?`}
        message="This entry is removed from the public profile."
        onConfirm={async () => {
          if (!deletingCredential) return;
          const ok = await run(
            () => adminApi.teachers.removeCredential(deletingCredential.id),
            t('admin.tea.entryDeleted'),
          );
          if (ok !== undefined) await load();
        }}
      />
    </AdminShell>
  );
}
