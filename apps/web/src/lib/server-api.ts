/**
 * Server-side data fetching for marketing pages.
 *
 * Marketing pages render on the server for SEO, which means a page render depends on the API
 * being reachable. `safe()` makes that dependency non-fatal: if the API is down, the page still
 * renders with whatever fallback the caller supplies rather than returning a 500.
 *
 * The fallbacks are always *structural* (an empty list, a null) — never invented content. A page
 * that cannot load teachers shows no teachers, it does not show made-up ones.
 */

export const dynamic = 'force-dynamic';

export async function safe<T>(promise: Promise<T>, fallback: T): Promise<T> {
  try {
    return await promise;
  } catch (error) {
    if (process.env.NODE_ENV !== 'production') {
      console.warn('[server-api] request failed, using fallback:', (error as Error).message);
    }
    return fallback;
  }
}

/**
 * Fetch several resources, tolerating individual failures.
 *
 * The result type is driven by `fallbacks` rather than by `requests`, so a caller can widen a
 * value at the fallback (e.g. `null as SiteStats | null`) and have that widening flow through
 * to the returned type.
 */
export async function safeAll<F extends Record<string, unknown>>(
  requests: { [K in keyof F]: Promise<F[K]> },
  fallbacks: F,
): Promise<F> {
  const entries = await Promise.all(
    Object.entries(requests).map(async ([key, promise]) => {
      try {
        return [key, await promise] as const;
      } catch (error) {
        if (process.env.NODE_ENV !== 'production') {
          console.warn(`[server-api] "${key}" failed:`, (error as Error).message);
        }
        return [key, fallbacks[key as keyof F]] as const;
      }
    }),
  );
  return Object.fromEntries(entries) as F;
}
