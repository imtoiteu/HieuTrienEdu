'use client';

import Link from 'next/link';
import { CheckCircle2, Circle, Lock, Play } from 'lucide-react';
import { useEffect, useState, type ReactNode } from 'react';

import { Badge, Card, ProgressBar, Spinner, cn } from '@hietedu/ui';

import { api, type PathNode } from '@/lib/api';
import { useAuth } from '@/lib/auth';
import { useI18n } from '@/lib/i18n';
import { masteryPercent } from '@/lib/utils';

/**
 * The Duolingo-style learning path for one unit.
 *
 * Renders `fallback` for signed-out visitors — a public course page should still show what the
 * unit contains, it just cannot show anyone's progress through it.
 *
 * Locked skills are rendered as non-interactive elements rather than disabled links, so keyboard
 * users do not tab into a destination they cannot use.
 */
export function LearningPath({
  unitSlug,
  locale,
  fallback,
}: {
  unitSlug: string;
  locale: string;
  fallback: ReactNode;
}) {
  const { t } = useI18n();
  const { user, loading: authLoading } = useAuth();
  const [nodes, setNodes] = useState<PathNode[] | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    if (authLoading || !user || user.role !== 'student') return;
    let cancelled = false;
    api.practice
      .path(unitSlug)
      .then((result) => !cancelled && setNodes(result))
      .catch(() => !cancelled && setFailed(true));
    return () => {
      cancelled = true;
    };
  }, [authLoading, user, unitSlug]);

  if (authLoading) {
    return (
      <div className="mt-6 flex justify-center py-8">
        <Spinner className="h-6 w-6 text-brand-400" />
      </div>
    );
  }

  if (!user || user.role !== 'student' || failed) {
    return <>{fallback}</>;
  }

  if (!nodes) {
    return (
      <div className="mt-6 flex justify-center py-8">
        <Spinner className="h-6 w-6 text-brand-400" />
        <span className="sr-only">{t('common.loading')}</span>
      </div>
    );
  }

  if (nodes.length === 0) {
    return <>{fallback}</>;
  }

  return (
    <ol className="mt-6 space-y-3">
      {nodes.map((node, index) => {
        const isLocked = node.status === 'locked';
        const percent = masteryPercent(node.mastery);

        const inner = (
          <Card
            interactive={!isLocked}
            className={cn(
              'flex items-center gap-4',
              isLocked && 'border-dashed bg-ink-50/60 opacity-75',
              node.status === 'mastered' && 'border-teal-200 bg-teal-50/50',
            )}
          >
            <span
              aria-hidden="true"
              className={cn(
                'inline-flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl border-2',
                node.status === 'mastered'
                  ? 'border-teal-500 bg-teal-500 text-white'
                  : node.status === 'in_progress'
                    ? 'border-brand-500 bg-brand-100 text-brand-700'
                    : isLocked
                      ? 'border-ink-200 bg-ink-100 text-ink-400'
                      : 'border-ink-900 bg-white text-ink-800 shadow-pop-sm',
              )}
            >
              {node.status === 'mastered' ? (
                <CheckCircle2 className="h-5 w-5" />
              ) : isLocked ? (
                <Lock className="h-4 w-4" />
              ) : node.status === 'in_progress' ? (
                <Circle className="h-5 w-5" />
              ) : (
                <Play className="h-4 w-4" />
              )}
            </span>

            <div className="min-w-0 flex-1">
              <div className="flex flex-wrap items-center gap-2">
                <p className="font-bold text-ink-900">{node.skill_name}</p>
                <Badge
                  tone={
                    node.status === 'mastered'
                      ? 'teal'
                      : node.status === 'in_progress'
                        ? 'brand'
                        : isLocked
                          ? 'neutral'
                          : 'sun'
                  }
                >
                  {t(
                    node.status === 'mastered'
                      ? 'path.mastered'
                      : node.status === 'in_progress'
                        ? 'path.inProgress'
                        : isLocked
                          ? 'path.locked'
                          : 'path.available',
                  )}
                </Badge>
              </div>

              {isLocked && node.blocked_by.length > 0 ? (
                <p className="mt-1 text-xs text-ink-500">
                  {t('path.lockedReason', { skills: node.blocked_by.join(', ') })}
                </p>
              ) : (
                <ProgressBar
                  className="mt-2"
                  value={percent}
                  tone={node.status === 'mastered' ? 'teal' : 'brand'}
                  size="sm"
                  showValue
                  label={undefined}
                />
              )}
            </div>

            {!isLocked && (
              <span className="shrink-0 text-sm font-bold text-brand-700">
                {node.status === 'mastered'
                  ? t('path.review')
                  : node.attempts > 0
                    ? t('path.practiseAgain')
                    : t('path.startSkill')}
              </span>
            )}
          </Card>
        );

        return (
          <li key={node.skill_id}>
            {isLocked ? (
              <div aria-label={t('a11y.locked')}>{inner}</div>
            ) : (
              <Link href={`/${locale}/practice/${node.skill_slug}`} className="block">
                {inner}
              </Link>
            )}
            {index < nodes.length - 1 && (
              <div aria-hidden="true" className="ml-9 h-3 w-0.5 bg-ink-200" />
            )}
          </li>
        );
      })}
    </ol>
  );
}
