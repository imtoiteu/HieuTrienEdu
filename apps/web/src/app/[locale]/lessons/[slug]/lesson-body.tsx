'use client';

import Link from 'next/link';
import { CheckCircle2, ChevronLeft, Clock, Target } from 'lucide-react';
import { useEffect, useState } from 'react';

import { Alert, Badge, Button, Card, Spinner } from '@hietedu/ui';

import { LessonBlocks } from '@/components/lesson/lesson-blocks';
import { LessonResources } from '@/components/lesson/lesson-resources';
import { api, type LessonDetail } from '@/lib/api';
import { useAuth } from '@/lib/auth';
import { useI18n } from '@/lib/i18n';

/** The interactive half of the lesson page — see the note in `page.tsx`. */
export function LessonBody({
  params,
}: {
  params: Promise<{ locale: string; slug: string }>;
}) {
  const { t, locale } = useI18n();
  const { user, loading: authLoading } = useAuth();

  const [slug, setSlug] = useState<string | null>(null);
  const [lesson, setLesson] = useState<LessonDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [marking, setMarking] = useState(false);

  useEffect(() => {
    params.then((resolved) => setSlug(resolved.slug));
  }, [params]);

  useEffect(() => {
    if (!slug || authLoading) return;
    let cancelled = false;
    api.curriculum
      .lesson(slug)
      .then((result) => !cancelled && setLesson(result))
      .catch((caught) => !cancelled && setError((caught as Error).message));
    return () => {
      cancelled = true;
    };
  }, [slug, authLoading]);

  async function markComplete() {
    if (!lesson) return;
    setMarking(true);
    try {
      const updated = await api.curriculum.updateLessonProgress(lesson.slug, {
        progress_percent: 100,
        completed: true,
      });
      setLesson(updated);
    } catch (caught) {
      setError((caught as Error).message);
    } finally {
      setMarking(false);
    }
  }

  return (
    <>
      <div className="mx-auto w-full max-w-3xl px-5 py-8 sm:px-8 sm:py-12">
        <Link
          href={`/${locale}/courses`}
          className="inline-flex items-center gap-1.5 text-sm font-bold text-ink-600 hover:text-brand-700"
        >
          <ChevronLeft className="h-4 w-4" aria-hidden="true" />
          {t('courses.title')}
        </Link>

        {!lesson && !error && (
          <div className="flex justify-center py-24">
            <Spinner className="h-8 w-8 text-brand-500" />
            <span className="sr-only">{t('common.loading')}</span>
          </div>
        )}

        {error && (
          <Alert tone="error" className="mt-6">
            {error}
          </Alert>
        )}

        {lesson && (
          <article className="mt-6">
            <header>
              <div className="flex flex-wrap items-center gap-2">
                {lesson.topic_title && <Badge tone="brand">{lesson.topic_title}</Badge>}
                <Badge tone="neutral">
                  <Clock className="h-3.5 w-3.5" aria-hidden="true" />
                  {t('lesson.estimatedTime', { minutes: lesson.estimated_minutes })}
                </Badge>
                {lesson.completed && (
                  <Badge tone="teal">
                    <CheckCircle2 className="h-3.5 w-3.5" aria-hidden="true" />
                    {t('lesson.completed')}
                  </Badge>
                )}
              </div>

              <h1 className="mt-4 font-display text-4xl">{lesson.title}</h1>
              {lesson.summary && <p className="mt-3 text-lg text-ink-600">{lesson.summary}</p>}
            </header>

            {lesson.objectives.length > 0 && (
              <Card className="mt-7 border-brand-200 bg-brand-50">
                <p className="flex items-center gap-2 font-display text-lg">
                  <Target className="h-5 w-5 text-brand-600" aria-hidden="true" />
                  {t('lesson.objectives')}
                </p>
                <ul className="mt-3 space-y-2">
                  {lesson.objectives.map((objective) => (
                    <li key={objective} className="flex items-start gap-2.5 text-ink-700">
                      <span
                        className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-brand-400"
                        aria-hidden="true"
                      />
                      {objective}
                    </li>
                  ))}
                </ul>
              </Card>
            )}

            {lesson.video?.playback_url && (
              <div className="mt-8 overflow-hidden rounded-3xl border-2 border-ink-900 shadow-pop">
                <div className="aspect-video">
                  <iframe
                    src={lesson.video.playback_url}
                    title={lesson.video.title}
                    allow="accelerometer; clipboard-write; encrypted-media; picture-in-picture"
                    allowFullScreen
                    className="h-full w-full"
                  />
                </div>
              </div>
            )}

            <div className="mt-8">
              <LessonBlocks blocks={lesson.blocks} locale={locale} />
            </div>

            <LessonResources resources={lesson.resources ?? []} />

            {lesson.attribution && (
              <p className="mt-10 border-t-2 border-ink-100 pt-4 text-xs text-ink-500">
                {t('lesson.attribution')}: {lesson.attribution}
                {lesson.license ? ` (${lesson.license})` : ''}
              </p>
            )}

            {/* Completion is only offered to signed-in students — there is nowhere to record it
                otherwise, and a button that silently does nothing is worse than no button. */}
            {user?.role === 'student' && (
              <div className="mt-10 flex flex-wrap items-center gap-3">
                <Button
                  onClick={markComplete}
                  loading={marking}
                  disabled={Boolean(lesson.completed)}
                  variant={lesson.completed ? 'outline' : 'primary'}
                  size="lg"
                >
                  <CheckCircle2 className="h-5 w-5" aria-hidden="true" />
                  {lesson.completed ? t('lesson.completed') : t('lesson.markComplete')}
                </Button>
                {lesson.skill_slug && (
                  <Link href={`/${locale}/practice/${lesson.skill_slug}`}>
                    <Button variant="coral" size="lg">
                      {t('lesson.practice')}
                    </Button>
                  </Link>
                )}
              </div>
            )}

            {!user && lesson.skill_slug && (
              <div className="mt-10">
                <Link href={`/${locale}/register`}>
                  <Button variant="coral" size="lg">
                    {t('common.getStarted')}
                  </Button>
                </Link>
              </div>
            )}
          </article>
        )}
      </div>
    </>
  );
}
