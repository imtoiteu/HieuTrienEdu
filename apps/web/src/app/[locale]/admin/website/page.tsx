'use client';

import { ExternalLink, Plus, Trash2, Upload } from 'lucide-react';
import { useCallback, useEffect, useState } from 'react';

import { Alert, Badge, Button, Card } from '@hietedu/ui';

import { AdminShell } from '@/components/admin/admin-shell';
import { ConfirmDialog, Modal } from '@/components/admin/dialog';
import {
  CheckboxField,
  FormRow,
  SelectField,
  TextAreaField,
  TextField,
  TranslationPanel,
  useEnumLabel,
  translationDraft,
  translationsPayload,
} from '@/components/admin/form';
import { useToast } from '@/components/admin/toast';
import { useContentLabel } from '@/lib/content-label';
import {
  adminApi,
  type AnnouncementRow,
  type FaqRow,
  type SiteSection,
  type SiteSettingRow,
  type TestimonialRow,
} from '@/lib/admin-api';
import { useRequireAuth } from '@/lib/auth';
import { useI18n } from '@/lib/i18n';

const TESTIMONIAL_FIELDS = [{ name: 'quote', label: '' }, { name: 'author_role', label: '' }];

const TABS = [
  { id: 'pages', labelKey: 'admin.web.tab.pages' },
  { id: 'contact', labelKey: 'admin.web.tab.contact' },
  { id: 'faq', labelKey: 'admin.web.tab.faq' },
  { id: 'announcements', labelKey: 'admin.web.tab.announcements' },
  { id: 'testimonials', labelKey: 'admin.web.tab.testimonials' },
] as const;

type TabId = (typeof TABS)[number]['id'];

export default function WebsitePage() {
  const { t, locale, formatDateTime } = useI18n();
  const enumLabel = useEnumLabel();
  const label = useContentLabel();
  const { user, loading: authLoading } = useRequireAuth(locale, ['admin']);
  const { run, notify } = useToast();

  const [tab, setTab] = useState<TabId>('pages');
  const [sections, setSections] = useState<SiteSection[]>([]);
  const [settings, setSettings] = useState<SiteSettingRow[]>([]);
  const [faqs, setFaqs] = useState<FaqRow[]>([]);
  const [announcements, setAnnouncements] = useState<AnnouncementRow[]>([]);
  const [testimonials, setTestimonials] = useState<TestimonialRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [editingSection, setEditingSection] = useState<SiteSection | null>(null);
  const [sectionDraft, setSectionDraft] = useState<Record<string, string>>({});
  const [editingFaq, setEditingFaq] = useState<Partial<FaqRow> | null>(null);
  const [editingAnnouncement, setEditingAnnouncement] = useState<Partial<AnnouncementRow> | null>(
    null,
  );
  const [editingTestimonial, setEditingTestimonial] = useState<Partial<TestimonialRow> | null>(
    null,
  );
  const [testimonialVi, setTestimonialVi] = useState<Record<string, string>>({});
  const [deleting, setDeleting] = useState<{ kind: string; id: number; label: string } | null>(
    null,
  );

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [s, st, f, a, t] = await Promise.all([
        adminApi.cms.sections(),
        adminApi.cms.settings(),
        adminApi.cms.faqs(),
        adminApi.cms.announcements(),
        adminApi.cms.testimonials(),
      ]);
      setSections(s);
      setSettings(st);
      setFaqs(f);
      setAnnouncements(a);
      setTestimonials(t);
    } catch (caught) {
      notify((caught as Error).message, 'error');
    } finally {
      setLoading(false);
    }
  }, [notify]);

  useEffect(() => {
    if (user) void load();
  }, [user, load]);

  const pages = Array.from(new Set(sections.map((section) => section.page)));
  const pendingCount = sections.filter((section) => section.has_unpublished_changes).length;

  function openSection(section: SiteSection) {
    setSectionDraft(
      Object.fromEntries(
        Object.entries(section.content ?? {}).map(([key, value]) => [key, String(value ?? '')]),
      ),
    );
    setEditingSection(section);
  }

  if (authLoading || !user) return <AdminShell loading />;

  return (
    <AdminShell
      title={t('admin.web.title')}
      description={t('admin.web.subtitle')}
      breadcrumbs={[{ label: t('admin.a.adminCrumb'), href: '/admin' }, { label: t('admin.shell.group.website') }]}
      actions={
        <a href={`/${locale}`} target="_blank" rel="noreferrer">
          <Button variant="outline">
            <ExternalLink className="h-4 w-4" aria-hidden="true" />{t('admin.web.viewSite')}</Button>
        </a>
      }
    >
      {pendingCount > 0 && (
        <Alert tone="warning" className="mb-4" title={t('admin.web.pendingTitle')}>
          {pendingCount} section(s) have edits that visitors cannot see yet. Publish them from the
          Pages tab.
        </Alert>
      )}

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

      {loading ? (
        <p className="py-16 text-center text-sm text-ink-500">{t('admin.a.loading')}</p>
      ) : (
        <>
          {tab === 'pages' && (
            <div className="space-y-6">
              {pages.length === 0 && (
                <Card>
                  <p className="text-sm text-ink-500">{t('admin.web.noSections')}</p>
                </Card>
              )}
              {pages.map((page) => {
                const pageSections = sections.filter((section) => section.page === page);
                const pending = pageSections.filter((s) => s.has_unpublished_changes).length;
                return (
                  <Card key={page} className="p-0">
                    <div className="flex flex-wrap items-center gap-3 border-b-2 border-ink-100 p-4">
                      <h2 className="font-display text-lg capitalize">
                        {t('admin.web.pageName', { page })}
                      </h2>
                      <Badge tone="neutral">
                        {t('admin.web.sectionCount', { count: pageSections.length })}
                      </Badge>
                      {pending > 0 && (
                        <Badge tone="sun">
                          {t('admin.web.unpublishedCount', { count: pending })}
                        </Badge>
                      )}
                      {pending > 0 && (
                        <Button
                          size="sm"
                          className="ml-auto"
                          onClick={async () => {
                            const ok = await run(
                              () => adminApi.cms.publishPage(page),
                              t('admin.web.pagePublished'),
                            );
                            if (ok) await load();
                          }}
                        >
                          <Upload className="h-4 w-4" aria-hidden="true" />{t('admin.web.publishAll')}</Button>
                      )}
                    </div>
                    <ul className="divide-y divide-ink-100">
                      {pageSections.map((section) => (
                        <li
                          key={section.id}
                          className="flex flex-wrap items-center gap-3 px-4 py-3"
                        >
                          <div className="min-w-0 flex-1">
                            <p className="font-semibold text-ink-900">{section.label}</p>
                            <p className="truncate text-xs text-ink-500">
                              {String(
                                section.content?.title ??
                                  section.content?.text ??
                                  section.content?.body ??
                                  Object.values(section.content ?? {})[0] ??
                                  '—',
                              ).slice(0, 90)}
                            </p>
                          </div>
                          {section.has_unpublished_changes && <Badge tone="sun">{t('admin.web.draftEdits')}</Badge>}
                          <Badge tone={section.status === 'published' ? 'teal' : 'neutral'}>
                            {enumLabel(section.status)}
                          </Badge>
                          <Button size="sm" variant="outline" onClick={() => openSection(section)}>{t('admin.a.edit')}</Button>
                        </li>
                      ))}
                    </ul>
                  </Card>
                );
              })}
            </div>
          )}

          {tab === 'contact' && (
            <div className="space-y-6">
              {Array.from(new Set(settings.map((s) => s.group))).map((group) => (
                <Card key={group}>
                  <h2 className="font-display text-lg capitalize">{group}</h2>
                  <div className="mt-4 space-y-4">
                    {settings
                      .filter((setting) => setting.group === group)
                      .map((setting) => {
                        const currentKey = setting.value_type === 'markdown' ? 'markdown' : 'text';
                        const currentValue = String(setting.value?.[currentKey] ?? '');
                        return (
                          <FormRow
                            key={setting.id}
                            label={setting.label}
                            hint={setting.description ?? undefined}
                            htmlFor={`set-${setting.id}`}
                          >
                            {setting.value_type === 'markdown' ? (
                              <TextAreaField
                                id={`set-${setting.id}`}
                                rows={4}
                                defaultValue={currentValue}
                                onBlur={async (event) => {
                                  if (event.target.value === currentValue) return;
                                  const ok = await run(
                                    () =>
                                      adminApi.cms.setSetting(setting.key, {
                                        markdown: event.target.value,
                                      }),
                                    t('admin.web.settingSaved', { label: setting.label }),
                                  );
                                  if (ok) await load();
                                }}
                              />
                            ) : (
                              <TextField
                                id={`set-${setting.id}`}
                                defaultValue={currentValue}
                                onBlur={async (event) => {
                                  if (event.target.value === currentValue) return;
                                  const ok = await run(
                                    () =>
                                      adminApi.cms.setSetting(setting.key, {
                                        text: event.target.value,
                                      }),
                                    t('admin.web.settingSaved', { label: setting.label }),
                                  );
                                  if (ok) await load();
                                }}
                              />
                            )}
                          </FormRow>
                        );
                      })}
                  </div>
                </Card>
              ))}
              <p className="text-xs text-ink-500">
                {t('admin.web.contactLive')}
              </p>
            </div>
          )}

          {tab === 'faq' && (
            <Card className="p-0">
              <div className="flex items-center justify-between border-b-2 border-ink-100 p-4">
                <h2 className="font-display text-lg">{t('admin.web.faqTitle')}</h2>
                <Button
                  size="sm"
                  onClick={() =>
                    setEditingFaq({
                      question: '',
                      answer: '',
                      category: 'general',
                      is_published: true,
                      locale,
                    })
                  }
                >
                  <Plus className="h-4 w-4" aria-hidden="true" />{t('admin.web.addQuestion')}</Button>
              </div>
              {faqs.length === 0 ? (
                <p className="p-6 text-center text-sm text-ink-500">{t('admin.web.noQuestions')}</p>
              ) : (
                <ul className="divide-y divide-ink-100">
                  {faqs.map((faq) => (
                    <li key={faq.id} className="flex flex-wrap items-start gap-3 px-4 py-3">
                      <div className="min-w-0 flex-1">
                        <p className="font-semibold text-ink-900">{faq.question}</p>
                        <p className="mt-0.5 line-clamp-2 text-sm text-ink-600">{faq.answer}</p>
                      </div>
                      <Badge tone="brand">{faq.locale === 'vi' ? 'VI' : 'EN'}</Badge>
                      <Badge tone="neutral">{enumLabel(faq.category)}</Badge>
                      {!faq.is_published && <Badge tone="coral">{t('admin.a.hidden')}</Badge>}
                      <Button size="sm" variant="ghost" onClick={() => setEditingFaq(faq)}>{t('admin.a.edit')}</Button>
                      <button
                        type="button"
                        aria-label={`${t('admin.a.delete')} ${faq.question}`}
                        onClick={() =>
                          setDeleting({ kind: 'faq', id: faq.id, label: faq.question })
                        }
                        className="rounded-lg p-1.5 text-coral-500 hover:bg-coral-50"
                      >
                        <Trash2 className="h-4 w-4" aria-hidden="true" />
                      </button>
                    </li>
                  ))}
                </ul>
              )}
            </Card>
          )}

          {tab === 'announcements' && (
            <Card className="p-0">
              <div className="flex items-center justify-between border-b-2 border-ink-100 p-4">
                <div>
                  <h2 className="font-display text-lg">{t('admin.web.announcementsTitle')}</h2>
                  <p className="text-sm text-ink-600">{t('admin.web.announcementsHint')}</p>
                </div>
                <Button
                  size="sm"
                  onClick={() =>
                    setEditingAnnouncement({
                      title: '',
                      kind: 'banner',
                      tone: 'brand',
                      is_published: false,
                      locale,
                    })
                  }
                >
                  <Plus className="h-4 w-4" aria-hidden="true" />
                  {t('admin.a.add')}
                </Button>
              </div>
              {announcements.length === 0 ? (
                <p className="p-6 text-center text-sm text-ink-500">{t('admin.web.nothingScheduled')}</p>
              ) : (
                <ul className="divide-y divide-ink-100">
                  {announcements.map((item) => (
                    <li key={item.id} className="flex flex-wrap items-center gap-3 px-4 py-3">
                      <div className="min-w-0 flex-1">
                        <p className="font-semibold text-ink-900">{item.title}</p>
                        <p className="truncate text-xs text-ink-500">
                          {enumLabel(item.kind)}
                          {item.starts_at
                            ? ` · ${t('admin.web.fromDate', { date: formatDateTime(item.starts_at) })}`
                            : ''}
                          {item.ends_at
                            ? ` ${t('admin.web.untilDate', { date: formatDateTime(item.ends_at) })}`
                            : ''}
                        </p>
                      </div>
                      {item.is_live ? (
                        <Badge tone="teal">{t('admin.web.liveNow')}</Badge>
                      ) : item.is_published ? (
                        <Badge tone="sun">{t('admin.web.scheduled')}</Badge>
                      ) : (
                        <Badge tone="neutral">{t('admin.st.draft')}</Badge>
                      )}
                      <Button
                        size="sm"
                        variant="ghost"
                        onClick={() => setEditingAnnouncement(item)}
                      >{t('admin.a.edit')}</Button>
                      <button
                        type="button"
                        aria-label={t('admin.a.deleteAria', { name: item.title })}
                        onClick={() =>
                          setDeleting({ kind: 'announcement', id: item.id, label: item.title })
                        }
                        className="rounded-lg p-1.5 text-coral-500 hover:bg-coral-50"
                      >
                        <Trash2 className="h-4 w-4" aria-hidden="true" />
                      </button>
                    </li>
                  ))}
                </ul>
              )}
            </Card>
          )}

          {tab === 'testimonials' && (
            <Card className="p-0">
              <div className="flex items-center justify-between border-b-2 border-ink-100 p-4">
                <h2 className="font-display text-lg">{t('admin.web.tab.testimonials')}</h2>
                <Button
                  size="sm"
                  onClick={() => {
                    setTestimonialVi({});
                    setEditingTestimonial({
                      author_name: '',
                      author_role: 'Parent',
                      quote: '',
                      rating: 5,
                      is_published: true,
                    });
                  }}
                >
                  <Plus className="h-4 w-4" aria-hidden="true" />
                  {t('admin.a.add')}
                </Button>
              </div>
              {testimonials.length === 0 ? (
                <p className="p-6 text-center text-sm text-ink-500">{t('admin.web.noTestimonials')}</p>
              ) : (
                <ul className="divide-y divide-ink-100">
                  {testimonials.map((item) => (
                    <li key={item.id} className="flex flex-wrap items-start gap-3 px-4 py-3">
                      <div className="min-w-0 flex-1">
                        <p className="font-semibold text-ink-900">
                          {item.author_name}{' '}
                          <span className="font-normal text-ink-500">— {item.author_role}</span>
                        </p>
                        <p className="mt-0.5 line-clamp-2 text-sm text-ink-600">“{label(item, 'quote')}”</p>
                      </div>
                      <Badge tone="sun">{'★'.repeat(item.rating)}</Badge>
                      {item.is_featured && <Badge tone="brand">{t('admin.a.featured')}</Badge>}
                      {!item.is_published && <Badge tone="coral">{t('admin.a.hidden')}</Badge>}
                      <Button
                        size="sm"
                        variant="ghost"
                        onClick={() => {
                          setTestimonialVi(
                            translationDraft(
                              (item as { translations?: Record<string, Record<string, unknown>> })
                                .translations,
                              TESTIMONIAL_FIELDS,
                            ),
                          );
                          setEditingTestimonial(item);
                        }}
                      >{t('admin.a.edit')}</Button>
                      <button
                        type="button"
                        aria-label={t('admin.web.deleteTestimonialAria', { name: item.author_name })}
                        onClick={() =>
                          setDeleting({
                            kind: 'testimonial',
                            id: item.id,
                            label: item.author_name,
                          })
                        }
                        className="rounded-lg p-1.5 text-coral-500 hover:bg-coral-50"
                      >
                        <Trash2 className="h-4 w-4" aria-hidden="true" />
                      </button>
                    </li>
                  ))}
                </ul>
              )}
            </Card>
          )}
        </>
      )}

      {/* section editor */}
      <Modal
        open={editingSection !== null}
        onClose={() => setEditingSection(null)}
        title={editingSection?.label ?? 'Section'}
        description={t('admin.web.sectionHint')}
        size="lg"
        footer={
          editingSection && (
            <>
              <Button variant="ghost" onClick={() => setEditingSection(null)}>{t('admin.a.cancel')}</Button>
              <Button
                variant="outline"
                onClick={async () => {
                  const ok = await run(
                    () => adminApi.cms.updateSection(editingSection.id, { content: sectionDraft }),
                    'Draft saved',
                  );
                  if (ok) {
                    setEditingSection(null);
                    await load();
                  }
                }}
              >{t('admin.web.saveDraft')}</Button>
              <Button
                onClick={async () => {
                  const saved = await run(() =>
                    adminApi.cms.updateSection(editingSection.id, { content: sectionDraft }),
                  );
                  if (!saved) return;
                  const ok = await run(
                    () => adminApi.cms.publishSection(editingSection.id),
                    t('admin.web.publishedToast'),
                  );
                  if (ok) {
                    setEditingSection(null);
                    await load();
                  }
                }}
              >
                <Upload className="h-4 w-4" aria-hidden="true" />{t('admin.web.saveAndPublish')}</Button>
            </>
          )
        }
      >
        {editingSection && (
          <div className="space-y-4">
            {Object.keys(sectionDraft).length === 0 && (
              <p className="text-sm text-ink-500">{t('admin.web.noFields')}</p>
            )}
            {Object.entries(sectionDraft).map(([key, value]) => (
              <FormRow key={key} label={enumLabel(key)} htmlFor={`sec-${key}`}>
                {value.length > 80 || key.includes('body') || key.includes('subtitle') ? (
                  <TextAreaField
                    id={`sec-${key}`}
                    rows={4}
                    value={value}
                    onChange={(event) =>
                      setSectionDraft({ ...sectionDraft, [key]: event.target.value })
                    }
                  />
                ) : (
                  <TextField
                    id={`sec-${key}`}
                    value={value}
                    onChange={(event) =>
                      setSectionDraft({ ...sectionDraft, [key]: event.target.value })
                    }
                  />
                )}
              </FormRow>
            ))}
            {editingSection.has_unpublished_changes && (
              <Alert tone="info">{t('admin.web.stillShowing')}</Alert>
            )}
          </div>
        )}
      </Modal>

      {/* FAQ editor */}
      <Modal
        open={editingFaq !== null}
        onClose={() => setEditingFaq(null)}
        title={editingFaq?.id ? t('admin.web.editQuestion') : t('admin.web.newQuestion')}
        footer={
          <>
            <Button variant="ghost" onClick={() => setEditingFaq(null)}>{t('admin.a.cancel')}</Button>
            <Button
              onClick={async () => {
                if (!editingFaq?.question?.trim() || !editingFaq.answer?.trim()) {
                  notify(t('admin.web.qaRequired'), 'error');
                  return;
                }
                const body = {
                  question: editingFaq.question,
                  answer: editingFaq.answer,
                  category: editingFaq.category ?? 'general',
                  is_published: editingFaq.is_published ?? true,
                  // FAQs are one row per language rather than a translation blob, so the row is
                  // only ever shown to readers of the language stored here.
                  locale: editingFaq.locale ?? locale,
                };
                const ok = await run(
                  () =>
                    editingFaq.id
                      ? adminApi.cms.updateFaq(editingFaq.id, body)
                      : adminApi.cms.createFaq(body),
                  t('admin.a.saved'),
                );
                if (ok) {
                  setEditingFaq(null);
                  await load();
                }
              }}
            >{t('admin.a.save')}</Button>
          </>
        }
      >
        {editingFaq && (
          <div className="space-y-4">
            <FormRow label={t('admin.web.questionLabel')} required htmlFor="faq-q">
              <TextField
                id="faq-q"
                value={editingFaq.question ?? ''}
                onChange={(e) => setEditingFaq({ ...editingFaq, question: e.target.value })}
              />
            </FormRow>
            <FormRow label={t('admin.web.answer')} required htmlFor="faq-a">
              <TextAreaField
                id="faq-a"
                rows={5}
                value={editingFaq.answer ?? ''}
                onChange={(e) => setEditingFaq({ ...editingFaq, answer: e.target.value })}
              />
            </FormRow>
            <FormRow label={t('admin.web.locale')} htmlFor="faq-locale">
              <SelectField
                id="faq-locale"
                value={editingFaq.locale ?? locale}
                onChange={(e) => setEditingFaq({ ...editingFaq, locale: e.target.value })}
              >
                <option value="vi">{t('admin.web.localeVi')}</option>
                <option value="en">{t('admin.web.localeEn')}</option>
              </SelectField>
              <p className="mt-1 text-xs text-ink-500">{t('admin.web.localeHint')}</p>
            </FormRow>
            <FormRow label={t('admin.a.category')} htmlFor="faq-c">
              <SelectField
                id="faq-c"
                value={editingFaq.category ?? 'general'}
                onChange={(e) => setEditingFaq({ ...editingFaq, category: e.target.value })}
              >
                <option value="general">{t('admin.st.general')}</option>
                <option value="pricing">{t('admin.st.pricing')}</option>
                <option value="learning">{t('admin.st.learning')}</option>
                <option value="schedule">{t('admin.st.schedule')}</option>
              </SelectField>
            </FormRow>
            <CheckboxField
              label={t('admin.a.published')}
              checked={editingFaq.is_published ?? true}
              onChange={(value) => setEditingFaq({ ...editingFaq, is_published: value })}
            />
          </div>
        )}
      </Modal>

      {/* announcement editor */}
      <Modal
        open={editingAnnouncement !== null}
        onClose={() => setEditingAnnouncement(null)}
        title={editingAnnouncement?.id ? t('admin.web.editAnnouncement') : t('admin.web.newAnnouncement')}
        footer={
          <>
            <Button variant="ghost" onClick={() => setEditingAnnouncement(null)}>{t('admin.a.cancel')}</Button>
            <Button
              onClick={async () => {
                if (!editingAnnouncement?.title?.trim()) {
                  notify(t('admin.a.titleRequired'), 'error');
                  return;
                }
                const body = {
                  title: editingAnnouncement.title,
                  body: editingAnnouncement.body || null,
                  kind: editingAnnouncement.kind ?? 'banner',
                  tone: editingAnnouncement.tone ?? 'brand',
                  link_url: editingAnnouncement.link_url || null,
                  link_label: editingAnnouncement.link_label || null,
                  image_url: editingAnnouncement.image_url || null,
                  starts_at: editingAnnouncement.starts_at || null,
                  ends_at: editingAnnouncement.ends_at || null,
                  is_published: editingAnnouncement.is_published ?? false,
                };
                const ok = await run(
                  () =>
                    editingAnnouncement.id
                      ? adminApi.cms.updateAnnouncement(editingAnnouncement.id, body)
                      : adminApi.cms.createAnnouncement(body),
                  t('admin.a.saved'),
                );
                if (ok) {
                  setEditingAnnouncement(null);
                  await load();
                }
              }}
            >{t('admin.a.save')}</Button>
          </>
        }
      >
        {editingAnnouncement && (
          <div className="grid gap-4 sm:grid-cols-2">
            <FormRow label={t('admin.a.title')} required htmlFor="an-title" className="sm:col-span-2">
              <TextField
                id="an-title"
                value={editingAnnouncement.title ?? ''}
                onChange={(e) =>
                  setEditingAnnouncement({ ...editingAnnouncement, title: e.target.value })
                }
              />
            </FormRow>
            <FormRow label={t('admin.web.locale')} htmlFor="an-locale">
              <SelectField
                id="an-locale"
                value={editingAnnouncement.locale ?? locale}
                onChange={(e) =>
                  setEditingAnnouncement({ ...editingAnnouncement, locale: e.target.value })
                }
              >
                <option value="vi">{t('admin.web.localeVi')}</option>
                <option value="en">{t('admin.web.localeEn')}</option>
              </SelectField>
              <p className="mt-1 text-xs text-ink-500">{t('admin.web.localeHint')}</p>
            </FormRow>
            <FormRow label={t('admin.web.body')} htmlFor="an-body" className="sm:col-span-2">
              <TextAreaField
                id="an-body"
                value={editingAnnouncement.body ?? ''}
                onChange={(e) =>
                  setEditingAnnouncement({ ...editingAnnouncement, body: e.target.value })
                }
              />
            </FormRow>
            <FormRow label={t('admin.web.kind')} htmlFor="an-kind">
              <SelectField
                id="an-kind"
                value={editingAnnouncement.kind ?? 'banner'}
                onChange={(e) =>
                  setEditingAnnouncement({ ...editingAnnouncement, kind: e.target.value })
                }
              >
                <option value="banner">{t('admin.st.banner')}</option>
                <option value="announcement">{t('admin.st.announcement')}</option>
                <option value="promotion">{t('admin.st.promotion')}</option>
              </SelectField>
            </FormRow>
            <FormRow label={t('admin.web.tone')} htmlFor="an-tone">
              <SelectField
                id="an-tone"
                value={editingAnnouncement.tone ?? 'brand'}
                onChange={(e) =>
                  setEditingAnnouncement({ ...editingAnnouncement, tone: e.target.value })
                }
              >
                <option value="brand">{t('admin.web.toneBrand')}</option>
                <option value="coral">{t('admin.web.toneAttention')}</option>
                <option value="teal">{t('admin.web.tonePositive')}</option>
                <option value="sun">{t('admin.web.toneWarning')}</option>
              </SelectField>
            </FormRow>
            <FormRow label={t('admin.web.linkUrl')} htmlFor="an-url">
              <TextField
                id="an-url"
                value={editingAnnouncement.link_url ?? ''}
                onChange={(e) =>
                  setEditingAnnouncement({ ...editingAnnouncement, link_url: e.target.value })
                }
              />
            </FormRow>
            <FormRow label={t('admin.web.linkLabel')} htmlFor="an-label">
              <TextField
                id="an-label"
                value={editingAnnouncement.link_label ?? ''}
                onChange={(e) =>
                  setEditingAnnouncement({ ...editingAnnouncement, link_label: e.target.value })
                }
              />
            </FormRow>
            <FormRow label={t('admin.web.startsLabel')} htmlFor="an-start" hint={t('admin.web.startsHint')}>
              <TextField
                id="an-start"
                type="datetime-local"
                value={editingAnnouncement.starts_at?.slice(0, 16) ?? ''}
                onChange={(e) =>
                  setEditingAnnouncement({
                    ...editingAnnouncement,
                    starts_at: e.target.value ? `${e.target.value}:00Z` : null,
                  })
                }
              />
            </FormRow>
            <FormRow label={t('admin.web.endsLabel')} htmlFor="an-end" hint={t('admin.web.endsHint')}>
              <TextField
                id="an-end"
                type="datetime-local"
                value={editingAnnouncement.ends_at?.slice(0, 16) ?? ''}
                onChange={(e) =>
                  setEditingAnnouncement({
                    ...editingAnnouncement,
                    ends_at: e.target.value ? `${e.target.value}:00Z` : null,
                  })
                }
              />
            </FormRow>
            <div className="sm:col-span-2">
              <CheckboxField
                label={t('admin.a.published')}
                hint={t('admin.web.publishedHint2')}
                checked={editingAnnouncement.is_published ?? false}
                onChange={(value) =>
                  setEditingAnnouncement({ ...editingAnnouncement, is_published: value })
                }
              />
            </div>
          </div>
        )}
      </Modal>

      {/* testimonial editor */}
      <Modal
        open={editingTestimonial !== null}
        onClose={() => setEditingTestimonial(null)}
        title={editingTestimonial?.id ? t('admin.web.editTestimonial') : t('admin.web.newTestimonial')}
        footer={
          <>
            <Button variant="ghost" onClick={() => setEditingTestimonial(null)}>{t('admin.a.cancel')}</Button>
            <Button
              onClick={async () => {
                if (!editingTestimonial?.author_name?.trim() || !editingTestimonial.quote?.trim()) {
                  notify(t('admin.web.authorQuoteRequired'), 'error');
                  return;
                }
                const body = {
                  author_name: editingTestimonial.author_name,
                  author_role: editingTestimonial.author_role ?? 'Parent',
                  quote: editingTestimonial.quote,
                  rating: editingTestimonial.rating ?? 5,
                  is_published: editingTestimonial.is_published ?? true,
                  is_featured: editingTestimonial.is_featured ?? false,
                  // /vi reads the quote through ``localise``; without this the testimonial
                  // stays English there however the rest of the page is set.
                  translations: translationsPayload(testimonialVi),
                };
                const ok = await run(
                  () =>
                    editingTestimonial.id
                      ? adminApi.cms.updateTestimonial(editingTestimonial.id, body)
                      : adminApi.cms.createTestimonial(body),
                  t('admin.a.saved'),
                );
                if (ok) {
                  setEditingTestimonial(null);
                  await load();
                }
              }}
            >{t('admin.a.save')}</Button>
          </>
        }
      >
        {editingTestimonial && (
          <div className="grid gap-4 sm:grid-cols-2">
            <FormRow label={t('admin.web.authorName')} required htmlFor="te-name">
              <TextField
                id="te-name"
                value={editingTestimonial.author_name ?? ''}
                onChange={(e) =>
                  setEditingTestimonial({ ...editingTestimonial, author_name: e.target.value })
                }
              />
            </FormRow>
            <FormRow label={t('admin.web.authorRole')} htmlFor="te-role">
              <TextField
                id="te-role"
                value={editingTestimonial.author_role ?? ''}
                onChange={(e) =>
                  setEditingTestimonial({ ...editingTestimonial, author_role: e.target.value })
                }
                placeholder={t('admin.web.authorRolePlaceholder')}
              />
            </FormRow>
            <FormRow label={t('admin.web.quote')} required htmlFor="te-quote" className="sm:col-span-2">
              <TextAreaField
                id="te-quote"
                rows={4}
                value={editingTestimonial.quote ?? ''}
                onChange={(e) =>
                  setEditingTestimonial({ ...editingTestimonial, quote: e.target.value })
                }
              />
            </FormRow>
            <div className="sm:col-span-2">
              <TranslationPanel
                fields={[
                  { name: 'quote', label: t('admin.web.quote'), multiline: true },
                  { name: 'author_role', label: t('admin.web.authorRole') },
                ]}
                value={testimonialVi}
                onChange={setTestimonialVi}
              />
            </div>
            <FormRow label={t('admin.web.rating')} htmlFor="te-rating">
              <SelectField
                id="te-rating"
                value={editingTestimonial.rating ?? 5}
                onChange={(e) =>
                  setEditingTestimonial({
                    ...editingTestimonial,
                    rating: Number(e.target.value),
                  })
                }
              >
                {[5, 4, 3, 2, 1].map((value) => (
                  <option key={value} value={value}>
                    {'★'.repeat(value)}
                  </option>
                ))}
              </SelectField>
            </FormRow>
            <div className="space-y-2 sm:col-span-2">
              <CheckboxField
                label={t('admin.a.published')}
                checked={editingTestimonial.is_published ?? true}
                onChange={(value) =>
                  setEditingTestimonial({ ...editingTestimonial, is_published: value })
                }
              />
              <CheckboxField
                label={t('admin.a.featureOnHome')}
                checked={editingTestimonial.is_featured ?? false}
                onChange={(value) =>
                  setEditingTestimonial({ ...editingTestimonial, is_featured: value })
                }
              />
            </div>
          </div>
        )}
      </Modal>

      <ConfirmDialog
        open={deleting !== null}
        onClose={() => setDeleting(null)}
        title={t('admin.a.deleteQ', { name: deleting?.label ?? '' })}
        message={t('admin.web.deleteBody')}
        onConfirm={async () => {
          if (!deleting) return;
          const remove =
            deleting.kind === 'faq'
              ? adminApi.cms.removeFaq
              : deleting.kind === 'announcement'
                ? adminApi.cms.removeAnnouncement
                : adminApi.cms.removeTestimonial;
          const ok = await run(() => remove(deleting.id), t('admin.a.deleted'));
          if (ok !== undefined) await load();
        }}
      />
    </AdminShell>
  );
}
