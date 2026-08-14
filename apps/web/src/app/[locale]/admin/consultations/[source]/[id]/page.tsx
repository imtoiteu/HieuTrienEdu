'use client';

import Link from 'next/link';
import { Mail, MessageSquarePlus, Phone, Trash2, UserPlus } from 'lucide-react';
import { use, useCallback, useEffect, useState } from 'react';

import { Alert, Badge, Button, Card } from '@hietedu/ui';

import { AdminShell } from '@/components/admin/admin-shell';
import { ConfirmDialog, Modal } from '@/components/admin/dialog';
import {
  FormRow,
  SelectField,
  StatusBadge,
  TextAreaField,
  TextField,
  useEnumLabel,
} from '@/components/admin/form';
import { useToast } from '@/components/admin/toast';
import { useContentLabel } from '@/lib/content-label';
import {
  adminApi,
  type AdminClass,
  type LeadDetail,
  type LeadStatus,
  type StaffMember,
} from '@/lib/admin-api';
import { useRequireAuth } from '@/lib/auth';
import { useI18n } from '@/lib/i18n';

const STATUSES: LeadStatus[] = [
  'new',
  'contacted',
  'consulting',
  'interested',
  'enrolled',
  'completed',
  'rejected',
  'no_response',
];

const NOTE_KINDS = ['note', 'call', 'email', 'meeting'];

export default function ConsultationDetailPage({
  params,
}: {
  params: Promise<{ locale: string; source: string; id: string }>;
}) {
  const { source, id } = use(params);
  const leadId = Number(id);
  const { t, locale, formatDateTime } = useI18n();
  const enumLabel = useEnumLabel();
  const label = useContentLabel();
  const { user, loading: authLoading } = useRequireAuth(locale, ['admin']);
  const { run, notify } = useToast();

  const [lead, setLead] = useState<LeadDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [staff, setStaff] = useState<StaffMember[]>([]);
  const [classes, setClasses] = useState<AdminClass[]>([]);
  const [noteBody, setNoteBody] = useState('');
  const [noteKind, setNoteKind] = useState('note');
  const [savingNote, setSavingNote] = useState(false);
  const [result, setResult] = useState('');
  const [converting, setConverting] = useState(false);
  const [conversion, setConversion] = useState({
    full_name: '',
    email: '',
    grade: 6,
    phone: '',
    class_group_id: 0,
    enrollment_notes: '',
  });
  const [converted, setConverted] = useState<{
    student_id: number;
    student_name: string | null;
    enrollment_id: number | null;
    temporary_password: string | null;
  } | null>(null);
  const [deleting, setDeleting] = useState(false);

  const href = (path: string) => `/${locale}${path}`;

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const result = await adminApi.leads.get(source, leadId);
      setLead(result);
      setResult(result.consultation_result ?? '');
      setConversion((current) => ({
        ...current,
        full_name: result.student_name || result.name,
        email: result.email,
        grade: result.grade ?? 6,
        phone: result.phone ?? '',
      }));
    } catch (caught) {
      notify((caught as Error).message, 'error');
    } finally {
      setLoading(false);
    }
  }, [source, leadId, notify]);

  useEffect(() => {
    if (user) void load();
  }, [user, load]);

  useEffect(() => {
    if (!user) return;
    adminApi.staff().then(setStaff).catch(() => undefined);
    adminApi.classes
      .list({ page_size: 100 })
      .then((page) => setClasses(page.items))
      .catch(() => undefined);
  }, [user]);

  async function patch(body: Record<string, unknown>, message: string) {
    const updated = await run(() => adminApi.leads.update(source, leadId, body), message);
    if (updated) setLead(updated);
  }

  async function addNote() {
    if (!noteBody.trim()) return;
    setSavingNote(true);
    const ok = await run(
      () => adminApi.leads.addNote(source, leadId, { body: noteBody, kind: noteKind }),
      t('admin.con.noteAdded'),
    );
    setSavingNote(false);
    if (ok) {
      setNoteBody('');
      await load();
    }
  }

  if (authLoading || !user) return <AdminShell loading />;

  return (
    <AdminShell
      title={lead?.name ?? t('admin.a.consultation')}
      description={
        lead
          ? t('admin.con.metaLine', {
              interest:
                enumLabel(lead.interest) +
                (lead.grade ? ` · ${t('admin.a.gradeN', { n: lead.grade })}` : ''),
              date: formatDateTime(lead.created_at),
            })
          : undefined
      }
      breadcrumbs={[
        { label: t('admin.a.adminCrumb'), href: '/admin' },
        { label: t('admin.con.title'), href: '/admin/consultations' },
        { label: lead?.name ?? '…' },
      ]}
      actions={
        lead && (
          <>
            {!lead.converted_student_id && (
              <Button onClick={() => setConverting(true)}>
                <UserPlus className="h-4 w-4" aria-hidden="true" />{t('admin.con.convert')}</Button>
            )}
            <Button variant="ghost" onClick={() => setDeleting(true)}>
              <Trash2 className="h-4 w-4 text-coral-600" aria-hidden="true" />
            </Button>
          </>
        )
      }
    >
      {loading || !lead ? (
        <p className="py-16 text-center text-sm text-ink-500">{t('admin.a.loading')}</p>
      ) : (
        <div className="grid gap-6 lg:grid-cols-[1fr_22rem]">
          <div className="min-w-0 space-y-6">
            {lead.converted_student_id && (
              <Alert tone="success" title={t('admin.con.converted')}>
                {t('admin.con.convertedLeadIn')}{' '}
                <Link
                  href={href(`/admin/students/${lead.converted_student_id}`)}
                  className="font-bold underline"
                >
                  {lead.converted_student_name ??
                    t('admin.a.studentRef', { id: lead.converted_student_id ?? '' })}
                </Link>
                {lead.converted_at &&
                  ` ${t('admin.con.convertedOn', { date: formatDateTime(lead.converted_at) })}`}
                .
              </Alert>
            )}

            {/* what they asked for */}
            <Card>
              <h2 className="font-display text-lg">{t('admin.con.enquiry')}</h2>
              <dl className="mt-4 grid gap-4 sm:grid-cols-2">
                <Detail label={t('admin.con.contactName')} value={lead.name} />
                <Detail
                  label={t('admin.a.email')}
                  value={
                    <a href={`mailto:${lead.email}`} className="text-brand-600 hover:underline">
                      {lead.email}
                    </a>
                  }
                />
                <Detail
                  label={t('admin.a.phone')}
                  value={
                    lead.phone ? (
                      <a href={`tel:${lead.phone}`} className="text-brand-600 hover:underline">
                        {lead.phone}
                      </a>
                    ) : (
                      '—'
                    )
                  }
                />
                <Detail label={t('admin.con.studentName')} value={lead.student_name ?? '—'} />
                <Detail label={t('admin.con.parent')} value={lead.parent_name ?? '—'} />
                <Detail label={t('admin.con.parentPhone')} value={lead.parent_phone ?? '—'} />
                <Detail label={t('admin.a.subject')} value={lead.subject_slug ?? '—'} />
                <Detail label={t('admin.a.grade')} value={lead.grade ? t('admin.a.gradeN', { n: lead.grade }) : '—'} />
                <Detail
                  label={t('admin.con.preferredFormat')}
                  value={lead.preferred_format ? enumLabel(lead.preferred_format) : '—'}
                />
                <Detail
                  label={t('admin.con.preferredDelivery')}
                  value={lead.preferred_delivery ? enumLabel(lead.preferred_delivery) : '—'}
                />
                {lead.school !== undefined && <Detail label={t('admin.con.schoolLabel')} value={lead.school ?? '—'} />}
                {lead.sessions_requested !== undefined && (
                  <Detail label={t('admin.con.sessionsRequested')} value={String(lead.sessions_requested)} />
                )}
                {lead.preferred_teacher && (
                  <Detail label={t('admin.con.preferredTeacher')} value={lead.preferred_teacher.name ?? '—'} />
                )}
                {lead.interested_course && (
                  <Detail label={t('admin.con.interestedCourse')} value={lead.interested_course.title} />
                )}
                {lead.interested_product && (
                  <Detail label={t('admin.con.interestedProgram')} value={lead.interested_product.name} />
                )}
                <Detail label={t('admin.con.submittedFrom')} value={lead.source_page ?? '—'} />
              </dl>

              {lead.preferred_schedule && (
                <div className="mt-4">
                  <p className="text-xs font-bold text-ink-500">{t('admin.con.preferredSchedule')}</p>
                  <p className="mt-1 whitespace-pre-wrap text-sm text-ink-800">
                    {lead.preferred_schedule}
                  </p>
                </div>
              )}

              {lead.preferred_slots && lead.preferred_slots.length > 0 && (
                <div className="mt-4">
                  <p className="text-xs font-bold text-ink-500">{t('admin.con.preferredTimes')}</p>
                  <ul className="mt-1 flex flex-wrap gap-1.5">
                    {lead.preferred_slots.map((slot, index) => (
                      <li key={index}>
                        <Badge tone="neutral">
                          {['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'][slot.weekday % 7]}{' '}
                          {slot.start}–{slot.end}
                        </Badge>
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {lead.message && (
                <div className="mt-4 rounded-2xl bg-ink-50 p-4">
                  <p className="text-xs font-bold text-ink-500">{t('admin.con.theirMessage')}</p>
                  <p className="mt-1 whitespace-pre-wrap text-sm text-ink-800">{lead.message}</p>
                </div>
              )}
            </Card>

            {/* consultation result */}
            <Card>
              <h2 className="font-display text-lg">{t('admin.con.result')}</h2>
              <p className="mt-1 text-sm text-ink-600">{t('admin.con.resultHint')}</p>
              <TextAreaField
                className="mt-3"
                rows={4}
                value={result}
                onChange={(event) => setResult(event.target.value)}
                placeholder={t('admin.con.resultPlaceholder')}
              />
              <div className="mt-2 flex justify-end">
                <Button
                  size="sm"
                  onClick={() => patch({ consultation_result: result }, t('admin.con.resultSaved'))}
                >{t('admin.con.saveResult')}</Button>
              </div>
            </Card>

            {/* timeline */}
            <Card>
              <h2 className="font-display text-lg">{t('admin.con.history')}</h2>

              <div className="mt-4 rounded-2xl border-2 border-ink-100 p-3">
                <div className="flex flex-wrap gap-2">
                  {NOTE_KINDS.map((kind) => (
                    <button
                      key={kind}
                      type="button"
                      onClick={() => setNoteKind(kind)}
                      className={`rounded-full border-2 px-3 py-1 text-xs font-bold ${
                        noteKind === kind
                          ? 'border-brand-500 bg-brand-500 text-white'
                          : 'border-ink-200 text-ink-700'
                      }`}
                    >
                      {enumLabel(kind)}
                    </button>
                  ))}
                </div>
                <TextAreaField
                  className="mt-2"
                  rows={3}
                  value={noteBody}
                  onChange={(event) => setNoteBody(event.target.value)}
                  placeholder={t('admin.con.notePlaceholder')}
                />
                <div className="mt-2 flex justify-end">
                  <Button size="sm" loading={savingNote} onClick={addNote} disabled={!noteBody.trim()}>
                    <MessageSquarePlus className="h-4 w-4" aria-hidden="true" />{t('admin.con.addNote')}</Button>
                </div>
              </div>

              {lead.notes.length === 0 ? (
                <p className="mt-4 text-sm text-ink-500">
                  {t('admin.con.noContactYet')}
                </p>
              ) : (
                <ol className="mt-4 space-y-3">
                  {lead.notes.map((note) => (
                    <li key={note.id} className="flex gap-3">
                      <span className="mt-1 h-2 w-2 shrink-0 rounded-full bg-brand-400" />
                      <div className="min-w-0 flex-1">
                        <div className="flex flex-wrap items-center gap-2">
                          <Badge tone={note.kind === 'status_change' ? 'neutral' : 'brand'}>
                            {enumLabel(note.kind)}
                          </Badge>
                          <span className="text-xs text-ink-500">
                            {note.author_name ?? t('admin.con.system')} · {formatDateTime(note.created_at)}
                          </span>
                        </div>
                        <p className="mt-1 whitespace-pre-wrap text-sm text-ink-800">
                          {note.body}
                        </p>
                      </div>
                    </li>
                  ))}
                </ol>
              )}
            </Card>
          </div>

          {/* sidebar */}
          <aside className="space-y-4">
            <Card>
              <h2 className="font-display text-lg">{t('admin.a.status')}</h2>
              <div className="mt-3">
                <StatusBadge value={lead.status} kind="lead" />
              </div>
              <FormRow label={t('admin.con.moveTo')} htmlFor="lead-status" className="mt-4">
                <SelectField
                  id="lead-status"
                  value={lead.status}
                  onChange={(event) =>
                    patch({ status: event.target.value }, t('admin.con.movedTo', { status: enumLabel(event.target.value) }))
                  }
                >
                  {STATUSES.map((status) => (
                    <option key={status} value={status}>
                      {enumLabel(status)}
                    </option>
                  ))}
                </SelectField>
              </FormRow>

              <FormRow label={t('admin.con.assignedTo')} htmlFor="lead-assignee" className="mt-4">
                <SelectField
                  id="lead-assignee"
                  value={lead.assigned_to_id ?? ''}
                  onChange={(event) =>
                    patch(
                      { assigned_to_id: event.target.value ? Number(event.target.value) : null },
                      t('admin.con.assignmentUpdated'),
                    )
                  }
                >
                  <option value="">{t('admin.con.unassigned')}</option>
                  {staff.map((member) => (
                    <option key={member.id} value={member.id}>
                      {member.full_name} ({member.role})
                    </option>
                  ))}
                </SelectField>
              </FormRow>

              <FormRow label={t('admin.con.followUp')} htmlFor="lead-followup" className="mt-4">
                <TextField
                  id="lead-followup"
                  type="date"
                  value={lead.next_follow_up_at?.slice(0, 10) ?? ''}
                  onChange={(event) =>
                    patch(
                      {
                        next_follow_up_at: event.target.value
                          ? `${event.target.value}T09:00:00Z`
                          : null,
                      },
                      t('admin.con.followUpSet'),
                    )
                  }
                />
              </FormRow>

              {lead.last_contacted_at && (
                <p className="mt-3 text-xs text-ink-500">
                  {t('admin.con.lastContacted', {
                    date: formatDateTime(lead.last_contacted_at),
                  })}
                </p>
              )}
            </Card>

            <Card>
              <h2 className="font-display text-lg">{t('admin.con.contactThem')}</h2>
              <div className="mt-3 space-y-2">
                {lead.phone && (
                  <a href={`tel:${lead.phone}`} className="block">
                    <Button variant="outline" className="w-full justify-start">
                      <Phone className="h-4 w-4" aria-hidden="true" />
                      {lead.phone}
                    </Button>
                  </a>
                )}
                <a href={`mailto:${lead.email}`} className="block">
                  <Button variant="outline" className="w-full justify-start">
                    <Mail className="h-4 w-4" aria-hidden="true" />
                    {lead.email}
                  </Button>
                </a>
                <Button
                  variant="ghost"
                  className="w-full justify-start"
                  onClick={() => patch({ mark_contacted: true }, t('admin.con.markedContacted'))}
                >{t('admin.con.markContacted')}</Button>
              </div>
            </Card>
          </aside>
        </div>
      )}

      {/* conversion */}
      <Modal
        open={converting}
        onClose={() => setConverting(false)}
        title={t('admin.con.convertTitle')}
        description={t('admin.con.convertHint')}
        footer={
          <>
            <Button variant="ghost" onClick={() => setConverting(false)}>{t('admin.a.cancel')}</Button>
            <Button
              onClick={async () => {
                const outcome = await run(
                  () =>
                    adminApi.leads.convert(source, leadId, {
                      full_name: conversion.full_name,
                      email: conversion.email,
                      grade: conversion.grade,
                      phone: conversion.phone || null,
                      class_group_id: conversion.class_group_id || null,
                      enrollment_notes: conversion.enrollment_notes || null,
                    }),
                  t('admin.con.converted'),
                );
                if (outcome) {
                  setConverting(false);
                  setConverted(outcome);
                  await load();
                }
              }}
            >{t('admin.st.convert')}</Button>
          </>
        }
      >
        <div className="grid gap-4 sm:grid-cols-2">
          <FormRow label={t('admin.con.studentNameLabel')} required htmlFor="conv-name" className="sm:col-span-2">
            <TextField
              id="conv-name"
              value={conversion.full_name}
              onChange={(event) => setConversion({ ...conversion, full_name: event.target.value })}
            />
          </FormRow>
          <FormRow
            label={t('admin.a.email')}
            required
            htmlFor="conv-email"
            hint={t('admin.con.emailHint')}
            className="sm:col-span-2"
          >
            <TextField
              id="conv-email"
              type="email"
              value={conversion.email}
              onChange={(event) => setConversion({ ...conversion, email: event.target.value })}
            />
          </FormRow>
          <FormRow label={t('admin.a.grade')} htmlFor="conv-grade">
            <SelectField
              id="conv-grade"
              value={conversion.grade}
              onChange={(event) =>
                setConversion({ ...conversion, grade: Number(event.target.value) })
              }
            >
              {Array.from({ length: 12 }, (_, index) => index + 1).map((grade) => (
                <option key={grade} value={grade}>
                  Grade {grade}
                </option>
              ))}
            </SelectField>
          </FormRow>
          <FormRow label={t('admin.a.phone')} htmlFor="conv-phone">
            <TextField
              id="conv-phone"
              value={conversion.phone}
              onChange={(event) => setConversion({ ...conversion, phone: event.target.value })}
            />
          </FormRow>
          <FormRow
            label={t('admin.con.enrolInClass')}
            htmlFor="conv-class"
            hint={t('admin.con.enrolHint')}
            className="sm:col-span-2"
          >
            <SelectField
              id="conv-class"
              value={conversion.class_group_id}
              onChange={(event) =>
                setConversion({ ...conversion, class_group_id: Number(event.target.value) })
              }
            >
              <option value={0}>{t('admin.con.dontEnrol')}</option>
              {classes.map((group) => (
                <option key={group.id} value={group.id}>
                  {label(group, 'name')} ({t('admin.con.placesLeft', { count: group.seats_available })})
                </option>
              ))}
            </SelectField>
          </FormRow>
          <FormRow label={t('admin.con.enrolNotes')} htmlFor="conv-notes" className="sm:col-span-2">
            <TextAreaField
              id="conv-notes"
              value={conversion.enrollment_notes}
              onChange={(event) =>
                setConversion({ ...conversion, enrollment_notes: event.target.value })
              }
            />
          </FormRow>
        </div>
      </Modal>

      {/* conversion outcome — the temporary password is shown exactly once */}
      <Modal
        open={converted !== null}
        onClose={() => setConverted(null)}
        title={t('admin.con.studentCreated')}
        size="sm"
      >
        {converted && (
          <div className="space-y-3">
            <p className="text-sm">
              {t('admin.con.nowHasAccount', { name: converted.student_name ?? '' })}
            </p>
            {converted.enrollment_id && (
              <p className="text-sm">{t('admin.con.alsoEnrolled')}</p>
            )}
            {converted.temporary_password && (
              <Alert tone="warning" title={t('admin.a.tempPassword')}>
                <code className="select-all font-mono text-base font-bold">
                  {converted.temporary_password}
                </code>
                <p className="mt-1 text-xs">
                  {t('admin.con.passwordOnce')}
                </p>
              </Alert>
            )}
            <Link href={href(`/admin/students/${converted.student_id}`)}>
              <Button className="w-full">{t('admin.con.openStudent')}</Button>
            </Link>
          </div>
        )}
      </Modal>

      <ConfirmDialog
        open={deleting}
        onClose={() => setDeleting(false)}
        title={t('admin.con.deleteQ')}
        message={t('admin.con.deleteBody')}
        onConfirm={async () => {
          const ok = await run(() => adminApi.leads.remove(source, leadId), t('admin.con.deletedToast'));
          if (ok !== undefined) window.location.href = href('/admin/consultations');
        }}
      />
    </AdminShell>
  );
}

function Detail({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="min-w-0">
      <dt className="text-xs font-bold text-ink-500">{label}</dt>
      <dd className="mt-0.5 break-words text-sm text-ink-800">{value}</dd>
    </div>
  );
}
