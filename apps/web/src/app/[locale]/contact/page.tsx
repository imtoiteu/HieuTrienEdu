'use client';

import { CheckCircle2, Mail, MapPin, Phone } from 'lucide-react';
import { useState, type FormEvent } from 'react';

import { Alert, Button, Card, Container, Field, Input, Section, Select, Textarea } from '@hietedu/ui';

import { PageHeader } from '@/components/site/page-header';
import { MarketingShell } from '@/components/site/marketing-shell';
import { ApiError, api } from '@/lib/api';
import { useI18n } from '@/lib/i18n';

export default function ContactPage() {
  const { t } = useI18n();

  const [form, setForm] = useState({
    name: '',
    email: '',
    phone: '',
    subject_slug: '',
    grade: '',
    interest: 'assessment',
    message: '',
  });
  const [status, setStatus] = useState<'idle' | 'sending' | 'sent' | 'error'>('idle');
  const [error, setError] = useState<string | null>(null);

  const update = (key: string) => (event: { target: { value: string } }) =>
    setForm((current) => ({ ...current, [key]: event.target.value }));

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setStatus('sending');
    setError(null);
    try {
      await api.site.contact({
        name: form.name.trim(),
        email: form.email.trim(),
        phone: form.phone.trim() || null,
        subject_slug: form.subject_slug || null,
        grade: form.grade ? Number(form.grade) : null,
        interest: form.interest,
        message: form.message.trim() || null,
        source_page: typeof window !== 'undefined' ? window.location.pathname : null,
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

  return (
    <MarketingShell>
      <PageHeader
        eyebrow={t('nav.contact')}
        title={t('contact.title')}
        subtitle={t('contact.subtitle')}
        tone="coral"
      />

      <Section className="pt-10">
        <Container>
          <div className="grid gap-8 lg:grid-cols-[1.2fr_0.8fr]">
            <Card className="border-ink-900 shadow-pop">
              {status === 'sent' ? (
                <div className="py-8 text-center">
                  <span className="mx-auto inline-flex h-16 w-16 items-center justify-center rounded-3xl bg-teal-100">
                    <CheckCircle2 className="h-8 w-8 text-teal-600" aria-hidden="true" />
                  </span>
                  <p className="mt-5 font-display text-2xl">{t('contact.form.success')}</p>
                  <Button
                    className="mt-6"
                    variant="outline"
                    onClick={() => {
                      setStatus('idle');
                      setForm({
                        name: '',
                        email: '',
                        phone: '',
                        subject_slug: '',
                        grade: '',
                        interest: 'assessment',
                        message: '',
                      });
                    }}
                  >
                    {t('contact.form.send')}
                  </Button>
                </div>
              ) : (
                <form onSubmit={handleSubmit} className="space-y-5" noValidate>
                  {error && <Alert tone="error">{error}</Alert>}

                  <div className="grid gap-5 sm:grid-cols-2">
                    <Field label={t('contact.form.name')} htmlFor="name" required>
                      <Input
                        id="name"
                        required
                        autoComplete="name"
                        value={form.name}
                        onChange={update('name')}
                      />
                    </Field>
                    <Field label={t('contact.form.email')} htmlFor="email" required>
                      <Input
                        id="email"
                        type="email"
                        required
                        autoComplete="email"
                        value={form.email}
                        onChange={update('email')}
                      />
                    </Field>
                  </div>

                  <div className="grid gap-5 sm:grid-cols-2">
                    <Field label={`${t('contact.form.phone')} (${t('common.optional')})`} htmlFor="phone">
                      <Input
                        id="phone"
                        type="tel"
                        autoComplete="tel"
                        value={form.phone}
                        onChange={update('phone')}
                      />
                    </Field>
                    <Field label={t('contact.form.interest')} htmlFor="interest">
                      <Select id="interest" value={form.interest} onChange={update('interest')}>
                        <option value="assessment">{t('contact.interest.assessment')}</option>
                        <option value="one_to_one">{t('contact.interest.oneToOne')}</option>
                        <option value="group">{t('contact.interest.group')}</option>
                        <option value="online">{t('contact.interest.online')}</option>
                        <option value="general">{t('contact.interest.general')}</option>
                      </Select>
                    </Field>
                  </div>

                  <div className="grid gap-5 sm:grid-cols-2">
                    <Field label={`${t('contact.form.subject')} (${t('common.optional')})`} htmlFor="subject">
                      <Select id="subject" value={form.subject_slug} onChange={update('subject_slug')}>
                        <option value="">{t('common.all')}</option>
                        <option value="mathematics">{t('subject.mathematics.title')}</option>
                        <option value="physics">{t('subject.physics.title')}</option>
                      </Select>
                    </Field>
                    <Field label={`${t('contact.form.grade')} (${t('common.optional')})`} htmlFor="grade">
                      <Select id="grade" value={form.grade} onChange={update('grade')}>
                        <option value="">—</option>
                        {[6, 7, 8, 9].map((grade) => (
                          <option key={grade} value={grade}>
                            {t('common.grade')} {grade}
                          </option>
                        ))}
                      </Select>
                    </Field>
                  </div>

                  <Field label={`${t('contact.form.message')} (${t('common.optional')})`} htmlFor="message">
                    <Textarea id="message" value={form.message} onChange={update('message')} />
                  </Field>

                  <Button
                    type="submit"
                    size="lg"
                    variant="coral"
                    fullWidth
                    loading={status === 'sending'}
                  >
                    {status === 'sending' ? t('contact.form.sending') : t('contact.form.send')}
                  </Button>
                </form>
              )}
            </Card>

            <aside className="space-y-5">
              <Card>
                <h2 className="font-display text-xl">{t('contact.visitTitle')}</h2>
                <ul className="mt-4 space-y-3 text-sm text-ink-700">
                  <li className="flex items-start gap-3">
                    <MapPin className="mt-0.5 h-4 w-4 shrink-0 text-brand-500" aria-hidden="true" />{t('contact.centreAddress')}</li>
                  <li className="flex items-start gap-3">
                    <Phone className="mt-0.5 h-4 w-4 shrink-0 text-brand-500" aria-hidden="true" />
                    <a href="tel:+842412345678" className="hover:underline">
                      +84 24 1234 5678
                    </a>
                  </li>
                  <li className="flex items-start gap-3">
                    <Mail className="mt-0.5 h-4 w-4 shrink-0 text-brand-500" aria-hidden="true" />
                    <a href="mailto:hello@hietrieneducation.vn" className="hover:underline">
                      hello@hietrieneducation.vn
                    </a>
                  </li>
                </ul>
              </Card>

              <Card className="bg-brand-50">
                <h2 className="font-display text-xl">{t('contact.assessmentTitle')}</h2>
                <ol className="mt-3 space-y-2.5 text-sm text-ink-700">
                  {[
                    'A 15-minute adaptive test, taken online at home.',
                    'A written report showing exactly which skills are secure and which are not.',
                    'A 20-minute conversation with the teacher who would take the lessons.',
                    'No obligation, and no charge.',
                  ].map((step, index) => (
                    <li key={step} className="flex items-start gap-2.5">
                      <span className="inline-flex h-5 w-5 shrink-0 items-center justify-center rounded-lg bg-brand-200 text-xs font-extrabold text-brand-800">
                        {index + 1}
                      </span>
                      {step}
                    </li>
                  ))}
                </ol>
              </Card>
            </aside>
          </div>
        </Container>
      </Section>
    </MarketingShell>
  );
}
