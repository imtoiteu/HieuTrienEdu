'use client';

import { Eye, RefreshCw, Search } from 'lucide-react';
import { useCallback, useEffect, useState } from 'react';

import { Alert, Badge, Button, Card, Input, MathText, Select, Spinner } from '@hietedu/ui';

import { AppShell } from '@/components/app/app-shell';
import { api } from '@/lib/api';
import { useRequireAuth } from '@/lib/auth';
import { useI18n } from '@/lib/i18n';

interface QuestionRow {
  id: number;
  slug: string;
  prompt: string;
  question_type: string;
  difficulty: number;
  subject_slug: string;
  grade: number;
  topic_slug: string;
  status: string;
  is_parametric: boolean;
  times_served: number;
  times_correct: number;
  success_rate: number | null;
}

interface Preview {
  seed: number;
  variable_values: Record<string, unknown>;
  rendered: Record<string, unknown>;
  answer: Record<string, unknown>;
  hints: { text?: string }[];
  solution: { text?: string; math?: string }[];
}

export default function QuestionBankPage({ params }: { params: Promise<{ locale: string }> }) {
  const { t, locale } = useI18n();
  const { user, loading: authLoading } = useRequireAuth(locale, ['teacher', 'admin']);

  const [rows, setRows] = useState<QuestionRow[] | null>(null);
  const [total, setTotal] = useState(0);
  const [filters, setFilters] = useState({ subject: '', grade: '', difficulty: '', search: '' });
  const [preview, setPreview] = useState<{ id: number; data: Preview } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loadingPreview, setLoadingPreview] = useState(false);

  const load = useCallback(async () => {
    const result = await api.teacher.questions({
      subject: filters.subject || undefined,
      grade: filters.grade || undefined,
      difficulty: filters.difficulty || undefined,
      search: filters.search || undefined,
      page_size: 30,
    });
    setRows(result.items as unknown as QuestionRow[]);
    setTotal(result.total);
  }, [filters]);

  useEffect(() => {
    if (!user) return;
    load().catch((caught) => setError((caught as Error).message));
  }, [user, load]);

  async function showPreview(id: number, seed?: number) {
    setLoadingPreview(true);
    setError(null);
    try {
      const data = (await api.teacher.previewQuestion(id, seed)) as unknown as Preview;
      setPreview({ id, data });
    } catch (caught) {
      setError((caught as Error).message);
    } finally {
      setLoadingPreview(false);
    }
  }

  if (authLoading || !user) return <AppShell role="teacher" loading />;

  return (
    <AppShell role="teacher">
      <div className="mx-auto w-full max-w-6xl px-5 py-8 sm:px-8 lg:py-10">
        <header className="flex flex-wrap items-end justify-between gap-4">
          <div>
            <h1 className="font-display text-3xl sm:text-4xl">{t('teacher.questionBank')}</h1>
            <p className="mt-1 text-ink-600">{total} questions</p>
          </div>
        </header>

        {/* filters */}
        <Card className="mt-6">
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <label className="block">
              <span className="mb-1.5 block text-xs font-bold text-ink-700">
                {t('common.subject')}
              </span>
              <Select
                value={filters.subject}
                onChange={(event) =>
                  setFilters((current) => ({ ...current, subject: event.target.value }))
                }
              >
                <option value="">{t('common.all')}</option>
                <option value="mathematics">{t('subject.mathematics.title')}</option>
                <option value="physics">{t('subject.physics.title')}</option>
              </Select>
            </label>
            <label className="block">
              <span className="mb-1.5 block text-xs font-bold text-ink-700">
                {t('common.grade')}
              </span>
              <Select
                value={filters.grade}
                onChange={(event) =>
                  setFilters((current) => ({ ...current, grade: event.target.value }))
                }
              >
                <option value="">{t('common.all')}</option>
                {[6, 7, 8, 9].map((grade) => (
                  <option key={grade} value={grade}>
                    {grade}
                  </option>
                ))}
              </Select>
            </label>
            <label className="block">
              <span className="mb-1.5 block text-xs font-bold text-ink-700">
                {t('common.difficulty')}
              </span>
              <Select
                value={filters.difficulty}
                onChange={(event) =>
                  setFilters((current) => ({ ...current, difficulty: event.target.value }))
                }
              >
                <option value="">{t('common.all')}</option>
                {[1, 2, 3, 4, 5].map((level) => (
                  <option key={level} value={level}>
                    {level}
                  </option>
                ))}
              </Select>
            </label>
            <label className="block">
              <span className="mb-1.5 block text-xs font-bold text-ink-700">
                {t('common.search')}
              </span>
              <div className="relative">
                <Search
                  className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-ink-400"
                  aria-hidden="true"
                />
                <Input
                  className="pl-9"
                  value={filters.search}
                  onChange={(event) =>
                    setFilters((current) => ({ ...current, search: event.target.value }))
                  }
                />
              </div>
            </label>
          </div>
        </Card>

        {error && (
          <Alert tone="error" className="mt-5">
            {error}
          </Alert>
        )}

        {!rows && !error && (
          <div className="flex justify-center py-24">
            <Spinner className="h-8 w-8 text-brand-500" />
          </div>
        )}

        {rows && (
          <div className="mt-6 grid gap-6 lg:grid-cols-[1.3fr_0.7fr]">
            <Card className="p-0">
              <div className="scroll-x">
                <table className="w-full min-w-[40rem] text-left text-sm">
                  <thead className="bg-ink-50">
                    <tr>
                      {['Question', 'Type', 'Diff', 'Served', 'Success', ''].map(
                        (heading, index) => (
                          <th key={index} scope="col" className="px-4 py-3 font-display">
                            {heading}
                          </th>
                        ),
                      )}
                    </tr>
                  </thead>
                  <tbody>
                    {rows.map((question) => (
                      <tr key={question.id} className="border-t border-ink-100 align-top">
                        <td className="max-w-sm px-4 py-3">
                          <p className="line-clamp-2 text-ink-800">{question.prompt}</p>
                          <div className="mt-1.5 flex flex-wrap gap-1.5">
                            <Badge
                              tone={question.subject_slug === 'physics' ? 'teal' : 'brand'}
                            >
                              {question.grade}
                            </Badge>
                            {question.is_parametric && <Badge tone="sun">parametric</Badge>}
                            {question.status !== 'published' && (
                              <Badge tone="danger">{question.status}</Badge>
                            )}
                          </div>
                        </td>
                        <td className="px-4 py-3 text-xs text-ink-600">
                          {question.question_type.replace(/_/g, ' ')}
                        </td>
                        <td className="px-4 py-3 tabular-nums">{question.difficulty}</td>
                        <td className="px-4 py-3 tabular-nums">{question.times_served}</td>
                        <td className="px-4 py-3">
                          {question.success_rate === null
                            ? '—'
                            : `${Math.round(question.success_rate * 100)}%`}
                        </td>
                        <td className="px-4 py-3">
                          <Button
                            size="sm"
                            variant="outline"
                            onClick={() => showPreview(question.id)}
                          >
                            <Eye className="h-3.5 w-3.5" aria-hidden="true" />
                            {t('teacher.previewQuestion')}
                          </Button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </Card>

            {/* preview panel */}
            <div className="lg:sticky lg:top-6 lg:self-start">
              <Card className="border-ink-900 shadow-pop">
                <div className="flex items-center justify-between gap-3">
                  <h2 className="font-display text-xl">{t('teacher.previewQuestion')}</h2>
                  {preview && (
                    <Button
                      size="sm"
                      variant="ghost"
                      loading={loadingPreview}
                      onClick={() => showPreview(preview.id)}
                      aria-label={t('a11y.regenerateSeed')}
                    >
                      <RefreshCw className="h-4 w-4" aria-hidden="true" />
                    </Button>
                  )}
                </div>

                {!preview ? (
                  <p className="mt-4 text-sm text-ink-500">
                    Choose a question to see a freshly generated variant, with its answer and
                    worked solution.
                  </p>
                ) : (
                  <div className="mt-4 space-y-4 text-sm">
                    <div>
                      <p className="text-xs font-bold uppercase tracking-widest text-ink-500">{t('admin.blk.f.prompt')}</p>
                      <p className="mt-1 text-ink-900">
                        <MathText>{String(preview.data.rendered.prompt ?? '')}</MathText>
                      </p>
                    </div>

                    {Array.isArray(preview.data.rendered.choices) && (
                      <ul className="space-y-1.5">
                        {(preview.data.rendered.choices as { id: string; label: string }[]).map(
                          (choice) => (
                            <li
                              key={choice.id}
                              className={`rounded-xl border-2 px-3 py-2 ${
                                choice.id === preview.data.answer.choice_id
                                  ? 'border-teal-400 bg-teal-50'
                                  : 'border-ink-200'
                              }`}
                            >
                              <span className="font-bold uppercase">{choice.id}.</span>{' '}
                              <MathText>{choice.label}</MathText>
                            </li>
                          ),
                        )}
                      </ul>
                    )}

                    <div className="rounded-xl bg-teal-50 p-3">
                      <p className="text-xs font-bold uppercase tracking-widest text-teal-700">{t('admin.web.answer')}</p>
                      <pre className="mt-1 whitespace-pre-wrap break-words font-mono text-xs text-ink-800">
                        {JSON.stringify(preview.data.answer, null, 2)}
                      </pre>
                    </div>

                    <div className="rounded-xl bg-ink-50 p-3">
                      <p className="text-xs font-bold uppercase tracking-widest text-ink-500">
                        Variables (seed {preview.data.seed})
                      </p>
                      <pre className="mt-1 whitespace-pre-wrap break-words font-mono text-xs text-ink-700">
                        {JSON.stringify(preview.data.variable_values, null, 2)}
                      </pre>
                    </div>

                    {preview.data.solution.length > 0 && (
                      <div>
                        <p className="text-xs font-bold uppercase tracking-widest text-ink-500">
                          {t('exercise.solution')}
                        </p>
                        <ol className="mt-2 space-y-2">
                          {preview.data.solution.map((step, index) => (
                            <li key={index} className="text-ink-700">
                              {step.text && <MathText>{step.text}</MathText>}
                              {step.math && (
                                <span className="block">
                                  <MathText>{`$${step.math}$`}</MathText>
                                </span>
                              )}
                            </li>
                          ))}
                        </ol>
                      </div>
                    )}
                  </div>
                )}
              </Card>
            </div>
          </div>
        )}
      </div>
    </AppShell>
  );
}
