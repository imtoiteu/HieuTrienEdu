import Link from 'next/link';

/**
 * Root not-found page.
 *
 * Next.js uses the *root* `not-found.tsx` for URLs that match no route at all; the one inside
 * `[locale]/` only handles explicit `notFound()` calls from within that segment. Without this
 * file, an unknown URL falls back to Next's unstyled default page.
 *
 * It is a server component with no translation context, because a URL that matched no route has
 * no locale to read. The copy is therefore English, with links into the localised site.
 */
export const metadata = { title: 'Page not found' };

export default function RootNotFound() {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center bg-cream px-5 py-20 text-center">
      <p className="font-display text-8xl font-extrabold text-brand-300">404</p>

      <svg aria-hidden="true" viewBox="0 0 200 24" className="mt-2 h-4 w-40">
        <path
          d="M0 12 Q 12.5 0, 25 12 T 50 12 T 75 12 T 100 12 T 125 12 T 150 12 T 175 12 T 200 12"
          fill="none"
          stroke="#FFC53D"
          strokeWidth="5"
          strokeLinecap="round"
        />
      </svg>

      <h1 className="mt-6 font-display text-3xl font-extrabold text-ink-900 sm:text-4xl">We cannot find that page</h1>
      <p className="mt-3 max-w-md text-ink-600">The link may be out of date, or the page may have moved.</p>

      <div className="mt-8 flex flex-wrap justify-center gap-3">
        <Link
          href="/en"
          className="inline-flex h-12 items-center rounded-2xl border-2 border-ink-900 bg-brand-500 px-6 font-bold text-white shadow-pop transition-all hover:bg-brand-600 active:translate-x-[3px] active:translate-y-[3px] active:shadow-none"
        >Back to the home page</Link>
        <Link
          href="/en/courses"
          className="inline-flex h-12 items-center rounded-2xl border-2 border-ink-900 bg-white px-6 font-bold text-ink-900 shadow-pop-sm transition-all hover:bg-ink-50"
        >Courses</Link>
      </div>
    </div>
  );
}
