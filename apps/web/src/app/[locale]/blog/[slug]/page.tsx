import Link from 'next/link';
import { notFound } from 'next/navigation';
import { ChevronLeft, Clock } from 'lucide-react';

import { formatDate, isLocale } from '@hietedu/localization';
import { Badge, Container, Section } from '@hietedu/ui';

import { ArticleBody } from '@/components/site/article-body';
import { MarketingShell } from '@/components/site/marketing-shell';
import { api } from '@/lib/api';
import { getTranslator } from '@/lib/dictionaries';

export const dynamic = 'force-dynamic';

export async function generateMetadata({
  params,
}: {
  params: Promise<{ locale: string; slug: string }>;
}) {
  const { slug } = await params;
  try {
    const post = await api.site.post(slug);
    return { title: post.title, description: post.excerpt };
  } catch {
    return { title: 'Article' };
  }
}

export default async function BlogPostPage({
  params,
}: {
  params: Promise<{ locale: string; slug: string }>;
}) {
  const { locale: raw, slug } = await params;
  const locale = isLocale(raw) ? raw : 'en';
  const t = getTranslator(locale);

  let post;
  try {
    post = await api.site.post(slug);
  } catch {
    notFound();
  }

  return (
    <MarketingShell>
      <Section className="pb-6 pt-10">
        <div className="mx-auto w-full max-w-3xl px-5 sm:px-8">
          <Link
            href={`/${locale}/blog`}
            className="inline-flex items-center gap-1.5 text-sm font-bold text-ink-600 hover:text-brand-700"
          >
            <ChevronLeft className="h-4 w-4" aria-hidden="true" />
            {t('blog.backToBlog')}
          </Link>

          <div className="mt-6 flex flex-wrap items-center gap-2">
            <Badge tone="brand">{post.category}</Badge>
            <span className="flex items-center gap-1 text-xs text-ink-500">
              <Clock className="h-3.5 w-3.5" aria-hidden="true" />
              {t('blog.readingTime', { minutes: post.reading_minutes })}
            </span>
            {post.published_at && (
              <span className="text-xs text-ink-500">{formatDate(post.published_at, locale)}</span>
            )}
          </div>

          <h1 className="mt-4 font-display text-4xl sm:text-5xl">{post.title}</h1>
          <p className="mt-4 text-lg text-ink-600">{post.excerpt}</p>
          <p className="mt-4 text-sm font-semibold text-ink-500">{post.author_name}</p>
        </div>
      </Section>

      <Section className="pt-0">
        <Container>
          <div className="mx-auto max-w-3xl">
            <ArticleBody markdown={post.body_markdown} />
            {post.tags.length > 0 && (
              <ul className="mt-10 flex flex-wrap gap-2 border-t-2 border-ink-100 pt-6">
                {post.tags.map((tag) => (
                  <li key={tag}>
                    <Badge tone="neutral">#{tag}</Badge>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </Container>
      </Section>
    </MarketingShell>
  );
}
