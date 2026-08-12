import Link from 'next/link';
import { ArrowRight, Clock } from 'lucide-react';

import { formatDate, isLocale } from '@hietedu/localization';
import { Badge, Card, Container, Section } from '@hietedu/ui';

import { PageHeader } from '@/components/site/page-header';
import { MarketingShell } from '@/components/site/marketing-shell';
import { api, type BlogPostSummary } from '@/lib/api';
import { getTranslator } from '@/lib/dictionaries';
import { safe } from '@/lib/server-api';

export const dynamic = 'force-dynamic';
export const metadata = { title: 'Resources' };

export default async function BlogPage({ params }: { params: Promise<{ locale: string }> }) {
  const { locale: raw } = await params;
  const locale = isLocale(raw) ? raw : 'en';
  const t = getTranslator(locale);

  const posts = await safe(api.site.posts(), [] as BlogPostSummary[]);

  return (
    <MarketingShell>
      <PageHeader eyebrow={t('nav.blog')} title={t('blog.title')} subtitle={t('blog.subtitle')} />

      <Section className="pt-10">
        <Container>
          {posts.length === 0 ? (
            <Card className="text-center">
              <p className="text-ink-600">{t('common.emptyState')}</p>
            </Card>
          ) : (
            <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
              {posts.map((post) => (
                <Link key={post.id} href={`/${locale}/blog/${post.slug}`}>
                  <Card interactive className="flex h-full flex-col">
                    <div className="flex flex-wrap items-center gap-2">
                      <Badge tone="brand">{post.category}</Badge>
                      <span className="flex items-center gap-1 text-xs text-ink-500">
                        <Clock className="h-3.5 w-3.5" aria-hidden="true" />
                        {t('blog.readingTime', { minutes: post.reading_minutes })}
                      </span>
                    </div>
                    <h2 className="mt-3 font-display text-xl">{post.title}</h2>
                    <p className="mt-2 flex-1 text-sm leading-relaxed text-ink-600">
                      {post.excerpt}
                    </p>
                    <footer className="mt-5 flex items-center justify-between border-t-2 border-ink-100 pt-4">
                      <span className="text-xs text-ink-500">
                        {post.published_at ? formatDate(post.published_at, locale) : ''}
                      </span>
                      <span className="inline-flex items-center gap-1.5 text-sm font-bold text-brand-700">
                        {t('common.readMore')}
                        <ArrowRight className="h-4 w-4" aria-hidden="true" />
                      </span>
                    </footer>
                  </Card>
                </Link>
              ))}
            </div>
          )}
        </Container>
      </Section>
    </MarketingShell>
  );
}
