'use client';

import Link from 'next/link';
import {
  ArrowRight,
  CheckCircle2,
  ChevronLeft,
  Flame,
  Lightbulb,
  PartyPopper,
  Sparkles,
  Trophy,
  XCircle,
  Zap,
} from 'lucide-react';
import { useCallback, useEffect, useRef, useState } from 'react';

import { Alert, Badge, Button, Card, MathText, ProgressBar, Spinner, cn } from '@hietedu/ui';

import { AppShell } from '@/components/app/app-shell';
import {
  AnswerInput,
  hasAnswer,
  initialAnswer,
  type AnswerValue,
} from '@/components/exercise/answer-input';
import { ApiError, api, type ServedQuestion, type SubmitResponse } from '@/lib/api';
import { useRequireAuth } from '@/lib/auth';
import { useI18n } from '@/lib/i18n';
import { masteryPercent } from '@/lib/utils';

const TARGET_QUESTIONS = 5;

export default function PracticePage({
  params,
}: {
  params: Promise<{ locale: string; skill: string }>;
}) {
  const { t, locale } = useI18n();
  const { user, loading: authLoading } = useRequireAuth(locale, ['student']);

  const [skillSlug, setSkillSlug] = useState<string | null>(null);
  const [sessionId, setSessionId] = useState<number | null>(null);
  const [question, setQuestion] = useState<ServedQuestion | null>(null);
  const [answer, setAnswer] = useState<AnswerValue>({});
  const [result, setResult] = useState<SubmitResponse | null>(null);
  const [hints, setHints] = useState<string[]>([]);
  const [status, setStatus] = useState<'loading' | 'answering' | 'checking' | 'reviewing' | 'done'>(
    'loading',
  );
  const [error, setError] = useState<string | null>(null);
  const [answered, setAnswered] = useState(0);
  const [correct, setCorrect] = useState(0);

  const startedAt = useRef<number>(Date.now());
  const feedbackRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    params.then(({ skill }) => setSkillSlug(skill));
  }, [params]);

  const loadNextQuestion = useCallback(
    async (session: number) => {
      setStatus('loading');
      setResult(null);
      setHints([]);
      setError(null);
      try {
        const next = await api.practice.nextQuestion(session);
        setQuestion(next);
        setAnswer(initialAnswer(next));
        startedAt.current = Date.now();
        setStatus('answering');
      } catch (caught) {
        setError(
          caught instanceof ApiError && caught.status === 404
            ? t('exercise.noQuestions')
            : (caught as Error).message,
        );
        setStatus('answering');
      }
    },
    [t],
  );

  // Start the session once we know both the student and the skill.
  useEffect(() => {
    if (!user || !skillSlug || sessionId !== null) return;
    let cancelled = false;
    (async () => {
      try {
        const session = await api.practice.startSession({
          skill_slug: skillSlug,
          target_questions: TARGET_QUESTIONS,
        });
        if (cancelled) return;
        setSessionId(session.id);
        await loadNextQuestion(session.id);
      } catch (caught) {
        if (!cancelled) {
          setError((caught as Error).message);
          setStatus('answering');
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [user, skillSlug, sessionId, loadNextQuestion]);

  async function handleSubmit() {
    if (!question || !sessionId) return;
    setStatus('checking');
    setError(null);
    try {
      const response = await api.practice.submit({
        variant_id: question.variant_id,
        answer,
        hints_used: hints.length,
        time_spent_seconds: Math.round((Date.now() - startedAt.current) / 1000),
        session_id: sessionId,
      });
      setResult(response);
      setAnswered((count) => count + 1);
      if (response.is_correct) setCorrect((count) => count + 1);
      setStatus('reviewing');
      // Move focus to the feedback so a screen reader announces the result immediately.
      requestAnimationFrame(() => feedbackRef.current?.focus());
    } catch (caught) {
      setError(
        caught instanceof ApiError && caught.status === 422
          ? caught.message
          : (caught as Error).message,
      );
      setStatus('answering');
    }
  }

  async function handleNext() {
    if (!sessionId) return;
    if (answered >= TARGET_QUESTIONS) {
      try {
        await api.practice.completeSession(sessionId);
      } catch {
        // Completing is a bonus-XP call; failing it must not block the summary screen.
      }
      setStatus('done');
      return;
    }
    await loadNextQuestion(sessionId);
  }

  async function revealHint() {
    if (!question || hints.length >= question.hint_count) return;
    try {
      const hint = await api.practice.hint(question.variant_id, hints.length);
      setHints((current) => [...current, hint.text]);
    } catch {
      setError(t('common.error'));
    }
  }

  const href = (path: string) => `/${locale}${path}`;

  if (authLoading || !user) {
    return <AppShell role="student" loading />;
  }

  return (
    <AppShell role="student">
      <div className="mx-auto w-full max-w-3xl px-5 py-6 sm:px-8 sm:py-10">
        <Link
          href={href('/dashboard')}
          className="inline-flex items-center gap-1.5 text-sm font-bold text-ink-600 hover:text-brand-700"
        >
          <ChevronLeft className="h-4 w-4" aria-hidden="true" />
          {t('exercise.backToPath')}
        </Link>

        {status === 'done' ? (
          <SessionSummary
            answered={answered}
            correct={correct}
            skillSlug={skillSlug}
            onPractiseMore={() => {
              setSessionId(null);
              setAnswered(0);
              setCorrect(0);
              setStatus('loading');
            }}
          />
        ) : (
          <>
            {/* progress */}
            <div className="mt-5">
              <div className="mb-2 flex items-baseline justify-between">
                <p className="text-sm font-bold text-ink-700">
                  {question?.skill.name ?? t('common.loading')}
                </p>
                <p className="text-sm text-ink-500">
                  {t('exercise.questionOf', {
                    current: Math.min(answered + 1, TARGET_QUESTIONS),
                    total: TARGET_QUESTIONS,
                  })}
                </p>
              </div>
              <ProgressBar value={(answered / TARGET_QUESTIONS) * 100} size="sm" />
            </div>

            {error && (
              <Alert tone="error" className="mt-5">
                {error}
                {error === t('exercise.noQuestions') && (
                  <Link href={href('/dashboard')} className="ml-2 font-bold underline">
                    {t('exercise.backToPath')}
                  </Link>
                )}
              </Alert>
            )}

            {status === 'loading' && (
              <div className="flex justify-center py-24">
                <Spinner className="h-8 w-8 text-brand-500" />
                <span className="sr-only">{t('common.loading')}</span>
              </div>
            )}

            {question && status !== 'loading' && (
              <Card className="mt-5 border-ink-900 shadow-pop">
                <div className="flex flex-wrap items-center gap-2">
                  <Badge tone="neutral">
                    {t('common.difficulty')} {question.difficulty}/5
                  </Badge>
                  {question.hint_count > 0 && (
                    <Badge tone="sun">
                      {t('exercise.hintsUsed', {
                        used: hints.length,
                        total: question.hint_count,
                      })}
                    </Badge>
                  )}
                </div>

                <div className="mt-5 text-lg leading-relaxed text-ink-900">
                  <MathText>{question.prompt}</MathText>
                </div>

                {question.image_url && (
                  <img
                    src={question.image_url}
                    alt=""
                    className="mt-5 max-w-full rounded-2xl border-2 border-ink-100"
                  />
                )}

                <div className="mt-7">
                  <AnswerInput
                    question={question}
                    value={answer}
                    onChange={setAnswer}
                    disabled={status !== 'answering'}
                  />
                </div>

                {/* hints */}
                {hints.length > 0 && (
                  <ul className="mt-6 space-y-2">
                    {hints.map((hint, index) => (
                      <li
                        key={index}
                        className="flex items-start gap-2.5 rounded-2xl border-2 border-sun-200 bg-sun-50 p-3.5"
                      >
                        <Lightbulb
                          className="mt-0.5 h-4 w-4 shrink-0 text-sun-600"
                          aria-hidden="true"
                        />
                        <span className="text-sm text-ink-800">
                          <MathText>{hint}</MathText>
                        </span>
                      </li>
                    ))}
                  </ul>
                )}

                {/* actions */}
                <div className="mt-7 flex flex-wrap items-center gap-3">
                  {status === 'answering' && (
                    <>
                      <Button
                        onClick={handleSubmit}
                        disabled={!hasAnswer(question, answer)}
                        size="lg"
                      >
                        {t('exercise.submit')}
                      </Button>
                      {hints.length < question.hint_count && (
                        <Button variant="outline" onClick={revealHint}>
                          <Lightbulb className="h-4 w-4" aria-hidden="true" />
                          {t('exercise.showHint')}
                        </Button>
                      )}
                    </>
                  )}
                  {status === 'checking' && (
                    <Button size="lg" loading>
                      {t('exercise.checking')}
                    </Button>
                  )}
                  {status === 'reviewing' && (
                    <Button size="lg" variant="coral" onClick={handleNext}>
                      {answered >= TARGET_QUESTIONS ? t('exercise.finish') : t('exercise.next')}
                      <ArrowRight className="h-5 w-5" aria-hidden="true" />
                    </Button>
                  )}
                </div>
              </Card>
            )}

            {/* feedback */}
            {result && (
              <div
                ref={feedbackRef}
                tabIndex={-1}
                // Announced politely so it does not interrupt a student mid-read.
                role="status"
                aria-live="polite"
                className="mt-5 focus:outline-none"
              >
                <Card
                  className={cn(
                    'border-2',
                    result.is_correct
                      ? 'border-teal-300 bg-teal-50'
                      : result.score > 0
                        ? 'border-sun-300 bg-sun-50'
                        : 'border-coral-300 bg-coral-50',
                  )}
                >
                  <div className="flex items-start gap-3">
                    {result.is_correct ? (
                      <CheckCircle2 className="h-7 w-7 shrink-0 text-teal-600" aria-hidden="true" />
                    ) : (
                      <XCircle className="h-7 w-7 shrink-0 text-coral-600" aria-hidden="true" />
                    )}
                    <div className="min-w-0 flex-1">
                      <p className="font-display text-xl">
                        {result.is_correct
                          ? t('exercise.correct')
                          : result.score > 0
                            ? t('exercise.partial')
                            : t('exercise.incorrect')}
                      </p>
                      <p className="mt-1 text-ink-700">{result.message}</p>

                      {!result.is_correct && result.correct_answer && (
                        <p className="mt-2 font-bold text-ink-900">
                          {t('exercise.correctAnswer', { answer: result.correct_answer })}
                        </p>
                      )}

                      {/* mastery movement */}
                      <div className="mt-4 rounded-2xl border-2 border-white bg-white/70 p-3">
                        <p className="text-xs font-bold uppercase tracking-widest text-ink-500">
                          {t('dashboard.overallMastery')}
                        </p>
                        <p className="mt-1 font-display text-lg">
                          {t('exercise.masteryUp', {
                            before: masteryPercent(result.mastery.before),
                            after: masteryPercent(result.mastery.after),
                          })}
                        </p>
                        <ProgressBar
                          className="mt-2"
                          value={masteryPercent(result.mastery.after)}
                          tone={result.is_correct ? 'teal' : 'coral'}
                          size="sm"
                        />
                      </div>

                      {/* rewards */}
                      <div className="mt-3 flex flex-wrap gap-2">
                        {result.gamification.xp_awarded > 0 && (
                          <Badge tone="brand">
                            <Zap className="h-3.5 w-3.5" aria-hidden="true" />
                            {t('exercise.xpEarned', {
                              amount: result.gamification.xp_awarded,
                            })}
                          </Badge>
                        )}
                        {result.mastery.newly_mastered && (
                          <Badge tone="teal">
                            <Trophy className="h-3.5 w-3.5" aria-hidden="true" />
                            {t('exercise.skillMastered')}
                          </Badge>
                        )}
                        {result.gamification.levelled_up && (
                          <Badge tone="sun">
                            <Sparkles className="h-3.5 w-3.5" aria-hidden="true" />
                            {t('exercise.levelUp', { level: result.gamification.level_after })}
                          </Badge>
                        )}
                        {result.gamification.streak_extended && (
                          <Badge tone="coral">
                            <Flame className="h-3.5 w-3.5" aria-hidden="true" />
                            {result.gamification.streak_days} {t('dashboard.streak')}
                          </Badge>
                        )}
                      </div>

                      {result.gamification.new_achievements.length > 0 && (
                        <ul className="mt-3 space-y-1.5">
                          {result.gamification.new_achievements.map((achievement) => (
                            <li
                              key={achievement.slug}
                              className="flex items-center gap-2 rounded-xl bg-white px-3 py-2 text-sm"
                            >
                              <PartyPopper
                                className="h-4 w-4 text-sun-600"
                                aria-hidden="true"
                              />
                              <span className="font-bold">{achievement.name}</span>
                              <span className="text-ink-500">— {achievement.description}</span>
                            </li>
                          ))}
                        </ul>
                      )}

                      {/* worked solution */}
                      {result.solution.length > 0 && (
                        <details className="mt-4 rounded-2xl border-2 border-white bg-white/70 p-4">
                          <summary className="cursor-pointer font-bold text-ink-800">
                            {t('exercise.solution')}
                          </summary>
                          <ol className="mt-3 space-y-3">
                            {result.solution.map((step, index) => (
                              <li key={index} className="flex gap-3">
                                <span className="inline-flex h-6 w-6 shrink-0 items-center justify-center rounded-lg bg-brand-100 text-xs font-extrabold text-brand-700">
                                  {index + 1}
                                </span>
                                <div className="min-w-0 flex-1">
                                  {step.text && (
                                    <p className="text-sm text-ink-800">
                                      <MathText>{step.text}</MathText>
                                    </p>
                                  )}
                                  {step.math && (
                                    <p className="mt-1 text-sm">
                                      <MathText>{`$$${step.math}$$`}</MathText>
                                    </p>
                                  )}
                                </div>
                              </li>
                            ))}
                          </ol>
                        </details>
                      )}
                    </div>
                  </div>
                </Card>
              </div>
            )}
          </>
        )}
      </div>
    </AppShell>
  );
}

function SessionSummary({
  answered,
  correct,
  skillSlug,
  onPractiseMore,
}: {
  answered: number;
  correct: number;
  skillSlug: string | null;
  onPractiseMore: () => void;
}) {
  const { t, locale } = useI18n();
  const percentage = answered > 0 ? Math.round((correct / answered) * 100) : 0;

  return (
    <Card className="mt-8 border-ink-900 text-center shadow-pop">
      <span className="mx-auto inline-flex h-16 w-16 items-center justify-center rounded-3xl border-2 border-ink-900 bg-sun-400 shadow-pop-sm">
        <PartyPopper className="h-8 w-8 text-ink-900" aria-hidden="true" />
      </span>
      <h1 className="mt-5 font-display text-3xl">{t('exercise.sessionComplete')}</h1>
      <p className="mt-2 text-lg text-ink-600">
        {t('exercise.sessionScore', { correct, total: answered })}
      </p>
      <ProgressBar
        className="mx-auto mt-6 max-w-sm"
        value={percentage}
        tone={percentage >= 80 ? 'teal' : percentage >= 50 ? 'sun' : 'coral'}
        size="lg"
        showValue
      />
      <div className="mt-8 flex flex-col justify-center gap-3 sm:flex-row">
        <Button variant="coral" size="lg" onClick={onPractiseMore} disabled={!skillSlug}>
          {t('exercise.practiseMore')}
        </Button>
        <Link href={`/${locale}/dashboard`}>
          <Button variant="outline" size="lg" className="w-full sm:w-auto">
            {t('exercise.backToPath')}
          </Button>
        </Link>
      </div>
    </Card>
  );
}
