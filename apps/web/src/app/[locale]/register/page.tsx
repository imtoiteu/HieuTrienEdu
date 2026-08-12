'use client';

import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useState, type FormEvent } from 'react';

import { Alert, Button, Card, Field, Input, Logo, Select } from '@hietedu/ui';

import { ApiError } from '@/lib/api';
import { useAuth } from '@/lib/auth';
import { useI18n } from '@/lib/i18n';

export default function RegisterPage() {
  const { t, locale } = useI18n();
  const { register } = useAuth();
  const router = useRouter();

  const [form, setForm] = useState({
    full_name: '',
    email: '',
    password: '',
    role: 'student',
    grade: '7',
  });
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const update = (key: string) => (event: { target: { value: string } }) =>
    setForm((current) => ({ ...current, [key]: event.target.value }));

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      const user = await register({
        full_name: form.full_name.trim(),
        email: form.email.trim(),
        password: form.password,
        role: form.role,
        locale,
        ...(form.role === 'student' ? { grade: Number(form.grade) } : {}),
      });
      router.push(user.role === 'parent' ? `/${locale}/parent` : `/${locale}/dashboard`);
    } catch (caught) {
      if (caught instanceof ApiError) {
        setError(
          caught.isOffline
            ? t('error.offline')
            : caught.status === 409
              ? t('auth.error.exists')
              : caught.message,
        );
      } else {
        setError(t('auth.error.generic'));
      }
      setSubmitting(false);
    }
  }

  return (
    <main className="flex min-h-screen items-center justify-center bg-lavender px-5 py-12">
      <div className="w-full max-w-md">
        <Link href={`/${locale}`} className="mb-8 flex justify-center">
          <Logo />
        </Link>

        <Card className="border-ink-900 shadow-pop">
          <h1 className="font-display text-3xl">{t('auth.register.title')}</h1>
          <p className="mt-2 text-ink-600">{t('auth.register.subtitle')}</p>

          <form onSubmit={handleSubmit} className="mt-7 space-y-5" noValidate>
            {error && <Alert tone="error">{error}</Alert>}

            <Field label={t('auth.fullName')} htmlFor="full_name" required>
              <Input
                id="full_name"
                name="full_name"
                autoComplete="name"
                required
                value={form.full_name}
                onChange={update('full_name')}
              />
            </Field>

            <Field label={t('auth.email')} htmlFor="email" required>
              <Input
                id="email"
                name="email"
                type="email"
                autoComplete="email"
                required
                value={form.email}
                onChange={update('email')}
              />
            </Field>

            <Field
              label={t('auth.password')}
              htmlFor="password"
              hint={t('auth.passwordHint')}
              required
            >
              <Input
                id="password"
                name="password"
                type="password"
                autoComplete="new-password"
                minLength={8}
                required
                value={form.password}
                onChange={update('password')}
                aria-describedby="password-hint"
              />
            </Field>

            <Field label={t('auth.role')} htmlFor="role" required>
              <Select id="role" name="role" value={form.role} onChange={update('role')}>
                <option value="student">{t('auth.role.student')}</option>
                <option value="parent">{t('auth.role.parent')}</option>
              </Select>
            </Field>

            {form.role === 'student' && (
              <Field label={t('auth.grade')} htmlFor="grade" required>
                <Select id="grade" name="grade" value={form.grade} onChange={update('grade')}>
                  {[6, 7, 8, 9].map((grade) => (
                    <option key={grade} value={grade}>
                      {t('common.grade')} {grade}
                    </option>
                  ))}
                </Select>
              </Field>
            )}

            <Button type="submit" fullWidth size="lg" variant="coral" loading={submitting}>
              {t('auth.register.submit')}
            </Button>
          </form>

          <p className="mt-6 text-center text-sm text-ink-600">
            {t('auth.register.hasAccount')}{' '}
            <Link href={`/${locale}/login`} className="font-bold text-brand-700 hover:underline">
              {t('common.login')}
            </Link>
          </p>
        </Card>
      </div>
    </main>
  );
}
