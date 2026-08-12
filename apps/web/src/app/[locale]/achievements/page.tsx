'use client';

import { Lock, Trophy } from 'lucide-react';
import { useEffect, useState } from 'react';

import { Badge, Card, ProgressBar, Spinner } from '@hietedu/ui';

import { AppShell } from '@/components/app/app-shell';
import { api, type Dashboard } from '@/lib/api';
import { useRequireAuth } from '@/lib/auth';
import { useI18n } from '@/lib/i18n';

/**
 * All achievements the platform defines, so a student can see what is still available.
 *
 * The criteria are duplicated here purely as display copy — the server remains the sole authority
 * on whether one has been earned, and the earned list comes from the API.
 */
const CATALOGUE = [
  { slug: 'first-steps', name: 'First Steps', description: 'Answer your first question', tier: 'bronze' },
  { slug: 'getting-going', name: 'Getting Going', description: 'Answer 25 questions', tier: 'bronze' },
  { slug: 'century', name: 'Century', description: 'Answer 100 questions', tier: 'silver' },
  { slug: 'sharp-shooter', name: 'Sharp Shooter', description: 'Get 50 questions correct', tier: 'silver' },
  { slug: 'first-mastery', name: 'Skill Unlocked', description: 'Master your first skill', tier: 'bronze' },
  { slug: 'five-skills', name: 'Building Momentum', description: 'Master 5 skills', tier: 'silver' },
  { slug: 'twenty-skills', name: 'Serious Progress', description: 'Master 20 skills', tier: 'gold' },
  { slug: 'three-day-streak', name: 'Three in a Row', description: 'Practise three days running', tier: 'bronze' },
  { slug: 'week-streak', name: 'Week Warrior', description: 'Practise seven days running', tier: 'silver' },
  { slug: 'month-streak', name: 'Unstoppable', description: 'Practise thirty days running', tier: 'gold' },
  { slug: 'level-five', name: 'Level 5', description: 'Reach level 5', tier: 'silver' },
  { slug: 'level-ten', name: 'Level 10', description: 'Reach level 10', tier: 'gold' },
];

const TIER_STYLES: Record<string, string> = {
  gold: 'bg-sun-200 text-sun-900 border-sun-400',
  silver: 'bg-ink-200 text-ink-800 border-ink-300',
  bronze: 'bg-coral-100 text-coral-800 border-coral-300',
};

export default function AchievementsPage({ params }: { params: Promise<{ locale: string }> }) {
  const { t, locale, formatDate } = useI18n();
  const { user, loading: authLoading } = useRequireAuth(locale, ['student']);

  const [data, setData] = useState<Dashboard | null>(null);

  useEffect(() => {
    if (!user) return;
    let cancelled = false;
    api.progress
      .dashboard()
      .then((result) => !cancelled && setData(result))
      .catch(() => undefined);
    return () => {
      cancelled = true;
    };
  }, [user]);

  if (authLoading || !user) return <AppShell role="student" loading />;

  const earned = new Map((data?.achievements ?? []).map((item) => [item.slug, item]));

  return (
    <AppShell role="student">
      <div className="mx-auto w-full max-w-5xl px-5 py-8 sm:px-8 lg:py-10">
        <h1 className="font-display text-3xl sm:text-4xl">{t('dashboard.achievements')}</h1>

        {!data ? (
          <div className="flex justify-center py-24">
            <Spinner className="h-8 w-8 text-brand-500" />
            <span className="sr-only">{t('common.loading')}</span>
          </div>
        ) : (
          <>
            <Card className="mt-6 border-ink-900 shadow-pop">
              <div className="flex flex-wrap items-center justify-between gap-4">
                <div>
                  <p className="text-sm font-semibold text-ink-500">{t('dashboard.level')}</p>
                  <p className="font-display text-4xl">{data.student.level}</p>
                </div>
                <div className="min-w-[14rem] flex-1">
                  <ProgressBar
                    value={
                      data.student.xp_for_next_level > 0
                        ? (data.student.xp_into_level / data.student.xp_for_next_level) * 100
                        : 100
                    }
                    label={t('dashboard.xpToNext', {
                      amount: Math.max(
                        0,
                        data.student.xp_for_next_level - data.student.xp_into_level,
                      ),
                      level: data.student.level + 1,
                    })}
                    tone="sun"
                    size="lg"
                  />
                </div>
                <div className="text-right">
                  <p className="text-sm font-semibold text-ink-500">{t('dashboard.xp')}</p>
                  <p className="font-display text-3xl">{data.student.xp_total}</p>
                </div>
              </div>
            </Card>

            <p className="mt-8 text-ink-600">
              {earned.size} / {CATALOGUE.length}
            </p>

            <ul className="mt-4 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
              {CATALOGUE.map((achievement) => {
                const unlocked = earned.get(achievement.slug);
                return (
                  <li key={achievement.slug}>
                    <Card
                      className={`h-full ${unlocked ? '' : 'border-dashed bg-ink-50/60 opacity-70'}`}
                    >
                      <div className="flex items-start gap-3">
                        <span
                          className={`inline-flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl border-2 ${
                            unlocked
                              ? TIER_STYLES[achievement.tier]
                              : 'border-ink-200 bg-white text-ink-300'
                          }`}
                        >
                          {unlocked ? (
                            <Trophy className="h-6 w-6" aria-hidden="true" />
                          ) : (
                            <Lock className="h-5 w-5" aria-hidden="true" />
                          )}
                        </span>
                        <div className="min-w-0">
                          <p className="font-display text-lg">{achievement.name}</p>
                          <p className="mt-0.5 text-sm text-ink-600">{achievement.description}</p>
                          {unlocked?.earned_at && (
                            <Badge tone="teal" className="mt-2">
                              {formatDate(unlocked.earned_at)}
                            </Badge>
                          )}
                        </div>
                      </div>
                    </Card>
                  </li>
                );
              })}
            </ul>
          </>
        )}
      </div>
    </AppShell>
  );
}
