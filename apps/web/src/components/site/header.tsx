'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { ChevronDown, Globe, LayoutDashboard, LogOut, Menu, X } from 'lucide-react';
import { useEffect, useState } from 'react';

import { LOCALES, LOCALE_NAMES } from '@hietedu/localization';
import { Avatar, Button, Logo, cn } from '@hietedu/ui';

import { useAuth } from '@/lib/auth';
import { useI18n } from '@/lib/i18n';

interface NavItem {
  labelKey: string;
  href: string;
  children?: { labelKey: string; href: string }[];
}

/**
 * Six top-level entries, not eight.
 *
 * Eight did not fit. The bar also carries a logo, a locale switcher, a login link and a CTA, and
 * at 1280px — the width of a great many laptops — the total ran about 130px over the available
 * space. The old header absorbed that by letting flex squash the buttons, so "Learning methods"
 * and "Log in" wrapped onto two lines and the CTA was clipped off the right edge.
 *
 * The four items that moved under About are the ones a visitor reads once (who teaches here, how
 * it is taught, articles, how to get in touch) rather than the ones they navigate to repeatedly.
 * Subjects, courses, tutoring formats and pricing — what a parent actually shops for — stay one
 * click away at the top level.
 */
const NAV: NavItem[] = [
  { labelKey: 'nav.mathematics', href: '/mathematics' },
  { labelKey: 'nav.physics', href: '/physics' },
  { labelKey: 'nav.courses', href: '/courses' },
  {
    labelKey: 'nav.tutoring',
    href: '/tutoring',
    children: [
      { labelKey: 'nav.oneToOne', href: '/tutoring/one-to-one' },
      { labelKey: 'nav.groupClasses', href: '/tutoring/group' },
      { labelKey: 'nav.onlineClasses', href: '/tutoring/online' },
      { labelKey: 'nav.liveClasses', href: '/tutoring/live' },
      { labelKey: 'nav.recordedCourses', href: '/tutoring/recorded' },
    ],
  },
  { labelKey: 'nav.pricing', href: '/pricing' },
  {
    labelKey: 'nav.about',
    href: '/about',
    children: [
      // The parent renders as a dropdown trigger rather than a link, so the overview page needs
      // its own entry or it becomes unreachable from the header.
      { labelKey: 'nav.aboutOverview', href: '/about' },
      { labelKey: 'nav.teachers', href: '/teachers' },
      { labelKey: 'nav.methods', href: '/learning-methods' },
      { labelKey: 'nav.blog', href: '/blog' },
      { labelKey: 'nav.contact', href: '/contact' },
    ],
  },
];

/**
 * One sizing treatment shared by every button in the header's action group.
 *
 * The group only reads as a group if its members agree, so login, dashboard and the CTA all take
 * this rather than each inheriting whatever the default `sm` size happens to be.
 *
 * 13px rather than the default 14px: at 14px bold the Vietnamese CTA "Bắt đầu miễn phí" runs wide
 * enough to crowd its own border and pull the whole right-hand side out of balance. Dropping one
 * step keeps the button prominent — it is still the only coral element in the bar — while letting
 * the padding, not the text, define its size.
 *
 * `leading-none` makes the text box exactly the glyph height so the flex centring is optically
 * true. That matters more here than in English: Vietnamese stacks diacritics (ắ, ầ, ễ), and with a
 * default line-height the extra box height pushes the visual centre of the label downwards.
 */
const ACTION_BUTTON = 'h-9 px-[1.125rem] text-[0.8125rem] leading-none';

export function SiteHeader() {
  const { t, locale } = useI18n();
  const { user, logout, loading } = useAuth();
  const pathname = usePathname();
  const [mobileOpen, setMobileOpen] = useState(false);
  const [openDropdown, setOpenDropdown] = useState<string | null>(null);

  const href = (path: string) => `/${locale}${path}`;

  // Close the mobile drawer on navigation, otherwise it stays open over the new page.
  useEffect(() => {
    setMobileOpen(false);
    setOpenDropdown(null);
  }, [pathname]);

  // Prevent the page behind the drawer from scrolling while it is open.
  useEffect(() => {
    document.body.style.overflow = mobileOpen ? 'hidden' : '';
    return () => {
      document.body.style.overflow = '';
    };
  }, [mobileOpen]);

  const dashboardHref = () => {
    if (!user) return href('/login');
    if (user.role === 'teacher') return href('/teacher');
    if (user.role === 'admin') return href('/admin');
    if (user.role === 'parent') return href('/parent');
    return href('/dashboard');
  };

  const isActive = (path: string) => pathname === href(path) || pathname.startsWith(`${href(path)}/`);

  return (
    <header className="sticky top-0 z-50 border-b-2 border-ink-100 bg-cream/90 backdrop-blur-md">
      <a href="#main" className="skip-link">
        {t('common.skipToContent')}
      </a>

      {/* Three-part layout, but only two flex children: a left cluster holding the brand and its
          navigation, and an action group pushed right with ml-auto.

          The previous version made the nav a third sibling under `justify-between`, which
          distributed the free space *between* all three — so the nav floated in the middle of the
          bar, detached from the logo and drifting further right on every wider screen. Grouping
          brand and nav means the nav stays anchored to the logo at any width, and the whitespace
          collects in one deliberate gap before the actions instead of two accidental ones. */}
      <div className="mx-auto flex h-16 w-full max-w-7xl items-center px-5 sm:px-8 lg:px-10">
        {/* No `min-w-0` here on purpose. It would let this cluster shrink below its content, and
            since nav items do not wrap they would simply overflow *underneath* the action group —
            a silent overlap. Left at its natural minimum, any future overflow shows up as a page
            scrollbar instead, which is visible and therefore fixable. */}
        <div className="flex items-center gap-7 2xl:gap-10">
          <Link href={href('')} aria-label={t('brand.name')} className="shrink-0">
            <Logo />
          </Link>

          <nav aria-label="Main" className="hidden items-center gap-0.5 xl:flex">
            {NAV.map((item) =>
              item.children ? (
                <div
                  key={item.href}
                  className="relative"
                  onMouseEnter={() => setOpenDropdown(item.href)}
                  onMouseLeave={() => setOpenDropdown(null)}
                >
                  <button
                    type="button"
                    aria-expanded={openDropdown === item.href}
                    aria-haspopup="true"
                    onClick={() => setOpenDropdown(openDropdown === item.href ? null : item.href)}
                    className={cn(
                      'flex items-center gap-1 rounded-xl px-2.5 py-2 text-sm font-bold transition-colors',
                      isActive(item.href)
                        ? 'bg-brand-100 text-brand-800'
                        : 'text-ink-700 hover:bg-ink-100',
                    )}
                  >
                    {t(item.labelKey)}
                    <ChevronDown className="h-4 w-4" aria-hidden="true" />
                  </button>
                  {openDropdown === item.href && (
                    <div className="absolute left-0 top-full w-60 pt-2">
                      <ul className="animate-pop-in rounded-2xl border-2 border-ink-100 bg-white p-2 shadow-lift">
                        {item.children.map((child) => (
                          <li key={child.href}>
                            <Link
                              href={href(child.href)}
                              className="block rounded-xl px-3 py-2 text-sm font-semibold text-ink-700 hover:bg-brand-50 hover:text-brand-800"
                            >
                              {t(child.labelKey)}
                            </Link>
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>
              ) : (
                <Link
                  key={item.href}
                  href={href(item.href)}
                  aria-current={isActive(item.href) ? 'page' : undefined}
                  className={cn(
                    'rounded-xl px-2.5 py-2 text-sm font-bold transition-colors',
                    isActive(item.href)
                      ? 'bg-brand-100 text-brand-800'
                      : 'text-ink-700 hover:bg-ink-100',
                  )}
                >
                  {t(item.labelKey)}
                </Link>
              ),
            )}
          </nav>
        </div>

        {/* Action group. `shrink-0` keeps the CTA intact if the navigation ever grows wide enough
            to compete for space — a squashed primary button is worse than a tighter nav. */}
        <div className="ml-auto flex shrink-0 items-center gap-1.5 pl-6">
          <LocaleSwitcher />

          {/* A hairline rather than more whitespace: it reads the locale switcher and the session
              actions as one deliberate group, which is what stops the right side looking like
              three unrelated controls that happen to sit near each other. */}
          <span className="mx-1 hidden h-6 w-px bg-ink-200 sm:block" aria-hidden="true" />

          {!loading && user ? (
            <div className="hidden items-center gap-2 sm:flex">
              <Link href={dashboardHref()}>
                <Button size="sm" variant="outline" className={ACTION_BUTTON}>
                  <LayoutDashboard className="h-4 w-4" aria-hidden="true" />
                  <span className="hidden lg:inline">{t('nav.dashboard')}</span>
                </Button>
              </Link>
              <Avatar name={user.full_name} src={user.avatar_url} size="sm" />
              <button
                type="button"
                onClick={logout}
                aria-label={t('common.logout')}
                className="rounded-xl p-2 text-ink-500 transition-colors hover:bg-ink-100 hover:text-ink-900"
              >
                <LogOut className="h-4 w-4" aria-hidden="true" />
              </button>
            </div>
          ) : (
            !loading && (
              <div className="hidden items-center gap-2 sm:flex">
                <Link href={href('/login')}>
                  <Button size="sm" variant="ghost" className={ACTION_BUTTON}>
                    {t('common.login')}
                  </Button>
                </Link>
                <Link href={href('/register')}>
                  <Button size="sm" variant="coral" className={ACTION_BUTTON}>
                    {t('common.getStarted')}
                  </Button>
                </Link>
              </div>
            )
          )}

          <button
            type="button"
            onClick={() => setMobileOpen((open) => !open)}
            aria-expanded={mobileOpen}
            aria-controls="mobile-nav"
            aria-label={mobileOpen ? t('nav.closeMenu') : t('nav.openMenu')}
            className="rounded-xl border-2 border-ink-900 p-2 shadow-pop-sm xl:hidden"
          >
            {mobileOpen ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
          </button>
        </div>
      </div>

      {mobileOpen && (
        <div
          id="mobile-nav"
          className="max-h-[calc(100vh-4rem)] overflow-y-auto border-t-2 border-ink-100 bg-cream px-5 py-4 xl:hidden"
        >
          <nav aria-label="Mobile">
            <ul className="space-y-1">
              {NAV.map((item) => (
                <li key={item.href}>
                  {/* A parent with children is a heading here, not a link. "Tutoring" points at
                      /tutoring, which is not a page — only /tutoring/[format] exists — so linking
                      it sent anyone using the mobile menu to a 404. Every destination is listed
                      below it, including the group's own overview page where there is one. */}
                  {item.children ? (
                    <span className="block px-3 pb-1 pt-3 text-xs font-extrabold uppercase tracking-widest text-ink-400">
                      {t(item.labelKey)}
                    </span>
                  ) : (
                    <Link
                      href={href(item.href)}
                      className="block rounded-xl px-3 py-2.5 font-bold text-ink-800 hover:bg-ink-100"
                    >
                      {t(item.labelKey)}
                    </Link>
                  )}
                  {item.children && (
                    <ul className="ml-3 border-l-2 border-ink-100 pl-3">
                      {item.children.map((child) => (
                        <li key={child.href}>
                          <Link
                            href={href(child.href)}
                            className="block rounded-xl px-3 py-2 text-sm font-semibold text-ink-600 hover:bg-ink-100"
                          >
                            {t(child.labelKey)}
                          </Link>
                        </li>
                      ))}
                    </ul>
                  )}
                </li>
              ))}
            </ul>
          </nav>

          <div className="mt-4 flex flex-col gap-2 border-t-2 border-ink-100 pt-4">
            {user ? (
              <>
                <Link href={dashboardHref()}>
                  <Button fullWidth variant="outline">
                    {t('nav.dashboard')}
                  </Button>
                </Link>
                <Button fullWidth variant="ghost" onClick={logout}>
                  {t('common.logout')}
                </Button>
              </>
            ) : (
              <>
                <Link href={href('/login')}>
                  <Button fullWidth variant="outline">
                    {t('common.login')}
                  </Button>
                </Link>
                <Link href={href('/register')}>
                  <Button fullWidth variant="coral">
                    {t('common.getStarted')}
                  </Button>
                </Link>
              </>
            )}
          </div>
        </div>
      )}
    </header>
  );
}

function LocaleSwitcher() {
  const { locale, t } = useI18n();
  const pathname = usePathname();
  const [open, setOpen] = useState(false);

  // Swap the first path segment, preserving the rest of the route so switching language keeps
  // the reader on the same page.
  const swapLocale = (next: string) => {
    const segments = pathname.split('/').filter(Boolean);
    segments[0] = next;
    return `/${segments.join('/')}`;
  };

  return (
    <div className="relative">
      <button
        type="button"
        onClick={() => setOpen((value) => !value)}
        aria-expanded={open}
        aria-label={t('a11y.languageSwitcher')}
        className="flex items-center gap-1.5 rounded-xl px-2.5 py-2 text-sm font-bold text-ink-700 transition-colors hover:bg-ink-100"
      >
        <Globe className="h-4 w-4" aria-hidden="true" />
        <span className="uppercase">{locale}</span>
      </button>
      {open && (
        <ul className="absolute right-0 top-full z-50 mt-2 w-40 animate-pop-in rounded-2xl border-2 border-ink-100 bg-white p-2 shadow-lift">
          {LOCALES.map((code) => (
            <li key={code}>
              <Link
                href={swapLocale(code)}
                onClick={() => setOpen(false)}
                aria-current={code === locale ? 'true' : undefined}
                className={cn(
                  'block rounded-xl px-3 py-2 text-sm font-semibold',
                  code === locale ? 'bg-brand-100 text-brand-800' : 'text-ink-700 hover:bg-ink-100',
                )}
              >
                {LOCALE_NAMES[code]}
              </Link>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
