'use client';

import { CheckCircle2 } from 'lucide-react';
import { useState, type FormEvent } from 'react';

import { Alert, Button, Card, Field, Input, Select, Textarea } from '@hietedu/ui';

import { ApiError, api, type TeacherCard } from '@/lib/api';
import { useI18n } from '@/lib/i18n';

const WEEKDAYS = [0, 1, 2, 3, 4, 5, 6].map((value) => ({ value }));

/**
 * The tutoring registration flow: format → teacher → schedule → submit.
 *
 * Deliberately available to signed-out visitors. Requiring an account before a parent can ask
 * about lessons would lose most enquiries, and the API accepts anonymous requests for exactly
 * this reason.
 */
export function TutoringEnquiryForm({
  defaultFormat,
  teachers,
  locale,
}: {
  defaultFormat: string;
  teachers: TeacherCard[];
  locale: string;
}) {
  const { t } = useI18n();

  const [form, setForm] = useState({
    contact_name: '',
    contact_email: '',
    contact_phone: '',
    subject_slug: 'mathematics',
    grade: '7',
    format: defaultFormat,
    delivery_mode: 'online',
    preferred_teacher_id: '',
    sessions_requested: '8',
    goals: '',
  });
  const [slots, setSlots] = useState<{ weekday: number; start: string; end: string }[]>([]);
  const [status, setStatus] = useState<'idle' | 'sending' | 'sent' | 'error'>('idle');
  const [error, setError] = useState<string | null>(null);

  const update = (key: string) => (event: { target: { value: string } }) =>
    setForm((current) => ({ ...current, [key]: event.target.value }));

  const toggleSlot = (weekday: number) => {
    setSlots((current) =>
      current.some((slot) => slot.weekday === weekday)
        ? current.filter((slot) => slot.weekday !== weekday)
        : [...current, { weekday, start: '18:00', end: '19:30' }],
    );
  };

  const eligibleTeachers = teachers.filter(
    (teacher) =>
      teacher.subjects.includes(form.subject_slug) &&
      teacher.grades.includes(Number(form.grade)),
  );

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setStatus('sending');
    setError(null);
    try {
      await api.tutoring.createRequest({
        contact_name: form.contact_name.trim(),
        contact_email: form.contact_email.trim(),
        contact_phone: form.contact_phone.trim() || null,
        subject_slug: form.subject_slug,
        grade: Number(form.grade),
        format: form.format,
        delivery_mode: form.delivery_mode,
        preferred_teacher_id: form.preferred_teacher_id
          ? Number(form.preferred_teacher_id)
          : null,
        preferred_slots: slots,
        sessions_requested: Number(form.sessions_requested),
        goals: form.goals.trim() || null,
      });
      setStatus('sent');
    } catch (caught) {
      setStatus('error');
      setError(
        caught instanceof ApiError && caught.isOffline
          ? t('error.offline')
          : t('contact.form.error'),
      );
    }
  }

  if (status === 'sent') {
    return (
      <Card className="border-teal-300 bg-teal-50 text-center">
        <span className="mx-auto inline-flex h-14 w-14 items-center justify-center rounded-3xl bg-white">
          <CheckCircle2 className="h-7 w-7 text-teal-600" aria-hidden="true" />
        </span>
        <p className="mt-4 font-display text-xl">{t('contact.form.success')}</p>
        <p className="mt-2 text-sm text-ink-600">{t('enquiry.oneToOneNote')}</p>
      </Card>
    );
  }

  return (
    <Card className="border-ink-900 shadow-pop">
      <h2 className="font-display text-2xl">{t('tutoring.register')}</h2>
      <p className="mt-1 text-sm text-ink-600">{t('enquiry.noAccountNeeded')}</p>

      <form onSubmit={handleSubmit} className="mt-6 space-y-4" noValidate>
        {error && <Alert tone="error">{error}</Alert>}

        <Field label={t('contact.form.name')} htmlFor="contact_name" required>
          <Input
            id="contact_name"
            required
            autoComplete="name"
            value={form.contact_name}
            onChange={update('contact_name')}
          />
        </Field>

        <Field label={t('contact.form.email')} htmlFor="contact_email" required>
          <Input
            id="contact_email"
            type="email"
            required
            autoComplete="email"
            value={form.contact_email}
            onChange={update('contact_email')}
          />
        </Field>

        <Field label={`${t('contact.form.phone')} (${t('common.optional')})`} htmlFor="contact_phone">
          <Input
            id="contact_phone"
            type="tel"
            autoComplete="tel"
            value={form.contact_phone}
            onChange={update('contact_phone')}
          />
        </Field>

        <div className="grid gap-4 sm:grid-cols-2">
          <Field label={t('common.subject')} htmlFor="subject_slug" required>
            <Select id="subject_slug" value={form.subject_slug} onChange={update('subject_slug')}>
              <option value="mathematics">{t('subject.mathematics.title')}</option>
              <option value="physics">{t('subject.physics.title')}</option>
            </Select>
          </Field>
          <Field label={t('common.grade')} htmlFor="grade" required>
            <Select id="grade" value={form.grade} onChange={update('grade')}>
              {[6, 7, 8, 9, 10, 11, 12].map((grade) => (
                <option key={grade} value={grade}>
                  {t('common.grade')} {grade}
                </option>
              ))}
            </Select>
          </Field>
        </div>

        <div className="grid gap-4 sm:grid-cols-2">
          <Field label={t('tutoring.chooseFormat')} htmlFor="format" required>
            <Select id="format" value={form.format} onChange={update('format')}>
              <option value="one_to_one">{t('nav.oneToOne')}</option>
              <option value="group">{t('nav.groupClasses')}</option>
              <option value="online_live">{t('nav.onlineClasses')}</option>
              <option value="recorded">{t('nav.recordedCourses')}</option>
              <option value="hybrid">{t('admin.st.hybrid')}</option>
            </Select>
          </Field>
          <Field label={t('enquiry.deliveryLabel')} htmlFor="delivery_mode" required>
            <Select id="delivery_mode" value={form.delivery_mode} onChange={update('delivery_mode')}>
              <option value="online">{t('admin.st.online')}</option>
              <option value="offline">{t('enquiry.deliveryOffline')}</option>
              <option value="hybrid">{t('enquiry.deliveryEither')}</option>
            </Select>
          </Field>
        </div>

        <Field label={t('tutoring.chooseTeacher')} htmlFor="preferred_teacher_id">
          <Select
            id="preferred_teacher_id"
            value={form.preferred_teacher_id}
            onChange={update('preferred_teacher_id')}
          >
            <option value="">{t('tutoring.anyTeacher')}</option>
            {eligibleTeachers.map((teacher) => (
              <option key={teacher.id} value={teacher.id}>
                {teacher.full_name}
                {teacher.headline ? ` — ${teacher.headline}` : ''}
              </option>
            ))}
          </Select>
        </Field>

        <fieldset>
          <legend className="mb-2 block text-sm font-bold text-ink-800">
            {t('tutoring.chooseSchedule')} ({t('common.optional')})
          </legend>
          <div className="flex flex-wrap gap-2">
            {WEEKDAYS.map((day) => {
              const selected = slots.some((slot) => slot.weekday === day.value);
              return (
                <label
                  key={day.value}
                  className={`cursor-pointer rounded-xl border-2 px-3 py-2 text-xs font-bold transition-colors ${
                    selected
                      ? 'border-brand-500 bg-brand-100 text-brand-800'
                      : 'border-ink-200 bg-white text-ink-600 hover:border-brand-300'
                  }`}
                >
                  <input
                    type="checkbox"
                    checked={selected}
                    onChange={() => toggleSlot(day.value)}
                    className="sr-only"
                  />
                  {t(`common.weekdayShort.${day.value}`)}
                </label>
              );
            })}
          </div>
          {slots.length > 0 && (
            <p className="mt-2 text-xs text-ink-500">{t('enquiry.groupNote')}</p>
          )}
        </fieldset>

        <Field label={t('enquiry.sessionsLabel')} htmlFor="sessions_requested">
          <Select
            id="sessions_requested"
            value={form.sessions_requested}
            onChange={update('sessions_requested')}
          >
            {[4, 8, 12, 16, 24].map((count) => (
              <option key={count} value={count}>
                {t('tutoring.sessions', { count })}
              </option>
            ))}
          </Select>
        </Field>

        <Field label={`What would you like help with? (${t('common.optional')})`} htmlFor="goals">
          <Textarea id="goals" value={form.goals} onChange={update('goals')} />
        </Field>

        <Button type="submit" fullWidth size="lg" variant="coral" loading={status === 'sending'}>
          {status === 'sending' ? t('contact.form.sending') : t('tutoring.register')}
        </Button>
      </form>
    </Card>
  );
}
