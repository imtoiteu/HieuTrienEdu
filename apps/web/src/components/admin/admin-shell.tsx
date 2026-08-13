'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import {
  Bell,
  BookOpen,
  CalendarDays,
  ChevronRight,
  ClipboardList,
  FileText,
  FolderTree,
  GraduationCap,
  Image as ImageIcon,
  LayoutDashboard,
  LogOut,
  Menu,
  MessageSquare,
  Package,
  ScrollText,
  Search,
  Settings,
  UserCheck,
  Users,
  X,
} from 'lucide-react';
import { useCallback, useEffect, useState, type ReactNode } from 'react';

import { Avatar, Logo, Spinner, cn } from '@hietedu/ui';

import { adminApi } from '@/lib/admin-api';
import { useAuth } from '@/lib/auth';
import { useI18n } from '@/lib/i18n';

interface NavItem {
  href: string;
  /** Dictionary key, resolved at render time so the sidebar follows the active locale. */
  labelKey: string;
  icon: typeof LayoutDashboard;
  /** Key into the badge counts returned by the overview endpoint. */
  badge?: 'consultations' | 'enrollments' | 'review';
}

interface NavGroup {
  titleKey: string;
  items: NavItem[];
}

/**
 * The admin navigation.
 *
 * Grouped by the job being done rather than by database table: someone dealing with a parent
 * enquiry does not care that consultations and enrolments live in different tables, but they do
 * care that both are "people wanting to join".
 */
const NAV: NavGroup[] = [
  {
    titleKey: 'admin.shell.group.overview',
    items: [{ href: '/admin', labelKey: 'admin.nav.dashboard', icon: LayoutDashboard }],
  },
  {
    titleKey: 'admin.shell.group.admissions',
    items: [
      {
        href: '/admin/consultations',
        labelKey: 'admin.nav.consultations',
        icon: MessageSquare,
        badge: 'consultations',
      },
      {
        href: '/admin/enrollments',
        labelKey: 'admin.nav.enrollments',
        icon: UserCheck,
        badge: 'enrollments',
      },
    ],
  },
  {
    titleKey: 'admin.shell.group.people',
    items: [
      { href: '/admin/students', labelKey: 'admin.nav.students', icon: Users },
      { href: '/admin/teachers', labelKey: 'admin.nav.teachers', icon: GraduationCap },
    ],
  },
  {
    titleKey: 'admin.shell.group.teaching',
    items: [
      { href: '/admin/courses', labelKey: 'admin.nav.courses', icon: BookOpen },
      { href: '/admin/lessons', labelKey: 'admin.nav.lessons', icon: FileText },
      {
        href: '/admin/exercises',
        labelKey: 'admin.nav.exercises',
        icon: ClipboardList,
        badge: 'review',
      },
      { href: '/admin/classes', labelKey: 'admin.nav.classes', icon: CalendarDays },
    ],
  },
  {
    titleKey: 'admin.shell.group.website',
    items: [
      { href: '/admin/categories', labelKey: 'admin.nav.categories', icon: FolderTree },
      { href: '/admin/programs', labelKey: 'admin.nav.programs', icon: Package },
      { href: '/admin/website', labelKey: 'admin.nav.website', icon: Settings },
      { href: '/admin/media', labelKey: 'admin.nav.media', icon: ImageIcon },
    ],
  },
  {
    titleKey: 'admin.shell.group.system',
    items: [{ href: '/admin/audit', labelKey: 'admin.nav.audit', icon: ScrollText }],
  },
];

export interface Breadcrumb {
  label: string;
  href?: string;
}

export function AdminShell({
  children,
  title,
  description,
  breadcrumbs,
  actions,
  loading,
}: {
  children?: ReactNode;
  title?: string;
  description?: string;
  breadcrumbs?: Breadcrumb[];
  actions?: ReactNode;
  loading?: boolean;
}) {
  const { locale, t } = useI18n();
  const { user, logout } = useAuth();
  const pathname = usePathname();

  const [mobileOpen, setMobileOpen] = useState(false);
  const [unread, setUnread] = useState(0);
  const [badges, setBadges] = useState({ consultations: 0, enrollments: 0, review: 0 });
  const [searchOpen, setSearchOpen] = useState(false);
  const [searchTerm, setSearchTerm] = useState('');
  const [searchResults, setSearchResults] = useState<Record<string, { id: number }[]>>({});

  const href = useCallback((path: string) => `/${locale}${path}`, [locale]);
  const isActive = (path: string) =>
    path === '/admin' ? pathname === href('/admin') : pathname.startsWith(href(path));

  // Sidebar badges: counts the administrator needs to see without opening each screen.
  useEffect(() => {
    if (!user) return;
    let cancelled = false;
    Promise.all([adminApi.overview(), adminApi.notifications.unreadCount()])
      .then(([overview, notifications]) => {
        if (cancelled) return;
        setBadges({
          consultations: overview.pending_consultations + overview.pending_registrations,
          enrollments: overview.pending_enrollments,
          review: overview.pending_review_questions,
        });
        setUnread(notifications.unread);
      })
      .catch(() => {
        // A failed badge fetch must not blank the whole admin area; the counts simply stay at 0.
      });
    return () => {
      cancelled = true;
    };
  }, [user, pathname]);

  useEffect(() => {
    setMobileOpen(false);
  }, [pathname]);

  // Global search, debounced.
  useEffect(() => {
    if (searchTerm.trim().length < 2) {
      setSearchResults({});
      return;
    }
    const timer = window.setTimeout(() => {
      adminApi
        .search(searchTerm)
        .then(setSearchResults)
        .catch(() => setSearchResults({}));
    }, 250);
    return () => window.clearTimeout(timer);
  }, [searchTerm]);

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-cream">
        <Spinner className="h-8 w-8 text-brand-500" />
        <span className="sr-only">{t('common.loading')}</span>
      </div>
    );
  }

  const sidebar = (
    <nav aria-label={t('admin.nav.admin')} className="flex h-full flex-col">
      <div className="flex items-center justify-between border-b-2 border-ink-100 p-5">
        <Link href={href('/admin')} aria-label={t('admin.nav.admin')}>
          <Logo />
        </Link>
        <button
          type="button"
          onClick={() => setMobileOpen(false)}
          className="rounded-xl p-2 text-ink-500 hover:bg-ink-100 lg:hidden"
          aria-label={t('admin.shell.closeMenu')}
        >
          <X className="h-5 w-5" aria-hidden="true" />
        </button>
      </div>

      <div className="flex-1 space-y-5 overflow-y-auto p-4">
        {NAV.map((group) => (
          <div key={group.titleKey}>
            <p className="px-3 pb-1.5 text-[0.65rem] font-extrabold uppercase tracking-widest text-ink-400">
              {t(group.titleKey)}
            </p>
            <ul className="space-y-0.5">
              {group.items.map((item) => {
                const count = item.badge ? badges[item.badge] : 0;
                return (
                  <li key={item.href}>
                    <Link
                      href={href(item.href)}
                      aria-current={isActive(item.href) ? 'page' : undefined}
                      className={cn(
                        'flex items-center gap-3 rounded-2xl px-3 py-2.5 text-sm font-bold transition-colors',
                        isActive(item.href)
                          ? 'bg-brand-500 text-white shadow-pop-sm'
                          : 'text-ink-700 hover:bg-ink-100',
                      )}
                    >
                      <item.icon className="h-4.5 w-4.5 shrink-0" aria-hidden="true" />
                      <span className="min-w-0 flex-1 truncate">{t(item.labelKey)}</span>
                      {count > 0 && (
                        <span
                          className={cn(
                            'rounded-full px-2 py-0.5 text-[0.65rem] font-extrabold tabular-nums',
                            isActive(item.href)
                              ? 'bg-white/25 text-white'
                              : 'bg-coral-500 text-white',
                          )}
                        >
                          {count > 99 ? '99+' : count}
                        </span>
                      )}
                    </Link>
                  </li>
                );
              })}
            </ul>
          </div>
        ))}
      </div>

      <div className="border-t-2 border-ink-100 p-4">
        {user && (
          <div className="mb-3 flex items-center gap-3">
            <Avatar name={user.full_name} src={user.avatar_url} size="md" />
            <div className="min-w-0">
              <p className="truncate text-sm font-bold text-ink-900">{user.full_name}</p>
              <p className="truncate text-xs capitalize text-ink-500">{user.role}</p>
            </div>
          </div>
        )}
        <div className="space-y-0.5">
          <Link
            href={href('/')}
            className="flex items-center gap-3 rounded-2xl px-3 py-2 text-sm font-semibold text-ink-600 hover:bg-ink-100"
          >
            <ChevronRight className="h-4 w-4" aria-hidden="true" />
            {t('admin.shell.viewSite')}
          </Link>
          <button
            type="button"
            onClick={logout}
            className="flex w-full items-center gap-3 rounded-2xl px-3 py-2 text-sm font-semibold text-ink-600 hover:bg-ink-100"
          >
            <LogOut className="h-4 w-4" aria-hidden="true" />
            {t('admin.shell.signOut')}
          </button>
        </div>
      </div>
    </nav>
  );

  return (
    <div className="min-h-screen bg-cream lg:flex">
      <aside className="hidden w-64 shrink-0 border-r-2 border-ink-100 bg-white lg:block">
        <div className="sticky top-0 h-screen">{sidebar}</div>
      </aside>

      {mobileOpen && (
        <div className="fixed inset-0 z-50 lg:hidden">
          <button
            type="button"
            aria-label={t('admin.shell.closeMenu')}
            className="absolute inset-0 bg-ink-900/40"
            onClick={() => setMobileOpen(false)}
          />
          <div className="relative h-full w-72 max-w-[85vw] bg-white">{sidebar}</div>
        </div>
      )}

      <div className="min-w-0 flex-1">
        <header className="sticky top-0 z-40 flex h-16 items-center gap-3 border-b-2 border-ink-100 bg-white/95 px-4 backdrop-blur sm:px-6">
          <button
            type="button"
            onClick={() => setMobileOpen(true)}
            aria-label={t('admin.shell.openMenu')}
            className="rounded-xl p-2 text-ink-600 hover:bg-ink-100 lg:hidden"
          >
            <Menu className="h-5 w-5" aria-hidden="true" />
          </button>

          <div className="relative min-w-0 flex-1 sm:max-w-md">
            <Search
              className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-ink-400"
              aria-hidden="true"
            />
            <input
              type="search"
              value={searchTerm}
              onChange={(event) => setSearchTerm(event.target.value)}
              onFocus={() => setSearchOpen(true)}
              onBlur={() => window.setTimeout(() => setSearchOpen(false), 150)}
              placeholder={t('admin.shell.searchPlaceholder')}
              aria-label={t('admin.shell.searchAria')}
              className="w-full rounded-xl border-2 border-ink-200 py-2 pl-9 pr-3 text-sm outline-none focus:border-brand-400"
            />
            {searchOpen && Object.values(searchResults).some((list) => list.length > 0) && (
              <div className="absolute left-0 right-0 top-full z-50 mt-1 max-h-80 overflow-y-auto rounded-2xl border-2 border-ink-200 bg-white p-2 shadow-pop-sm">
                {Object.entries(searchResults).map(([group, items]) =>
                  items.length === 0 ? null : (
                    <div key={group} className="mb-2 last:mb-0">
                      <p className="px-2 py-1 text-[0.65rem] font-extrabold uppercase tracking-widest text-ink-400">
                        {group}
                      </p>
                      {items.map((item) => (
                        <Link
                          key={`${group}-${item.id}`}
                          href={href(`/admin/${group}/${item.id}`)}
                          className="block truncate rounded-xl px-2 py-1.5 text-sm hover:bg-brand-50"
                        >
                          {String(
                            (item as Record<string, unknown>).name ??
                              (item as Record<string, unknown>).title ??
                              item.id,
                          )}
                        </Link>
                      ))}
                    </div>
                  ),
                )}
              </div>
            )}
          </div>

          <Link
            href={href('/admin/notifications')}
            className="relative rounded-xl p-2 text-ink-600 hover:bg-ink-100"
            aria-label={
              unread
                ? t('admin.shell.notificationsUnread', { count: unread })
                : t('admin.shell.notifications')
            }
          >
            <Bell className="h-5 w-5" aria-hidden="true" />
            {unread > 0 && (
              <span className="absolute right-1 top-1 flex h-4 min-w-4 items-center justify-center rounded-full bg-coral-500 px-1 text-[0.6rem] font-extrabold text-white">
                {unread > 9 ? '9+' : unread}
              </span>
            )}
          </Link>
        </header>

        <main id="main" className="mx-auto w-full max-w-7xl px-4 py-6 sm:px-6 lg:py-8">
          {(breadcrumbs || title) && (
            <div className="mb-6">
              {breadcrumbs && breadcrumbs.length > 0 && (
                <nav aria-label={t('admin.a.breadcrumb')} className="mb-2">
                  <ol className="flex flex-wrap items-center gap-1 text-xs text-ink-500">
                    {breadcrumbs.map((crumb, index) => (
                      <li key={`${crumb.label}-${index}`} className="flex items-center gap-1">
                        {index > 0 && (
                          <ChevronRight className="h-3 w-3 shrink-0" aria-hidden="true" />
                        )}
                        {crumb.href ? (
                          <Link
                            href={href(crumb.href)}
                            className="font-semibold hover:text-brand-600 hover:underline"
                          >
                            {crumb.label}
                          </Link>
                        ) : (
                          <span aria-current="page" className="font-semibold text-ink-700">
                            {crumb.label}
                          </span>
                        )}
                      </li>
                    ))}
                  </ol>
                </nav>
              )}
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div className="min-w-0">
                  {title && <h1 className="font-display text-2xl sm:text-3xl">{title}</h1>}
                  {description && (
                    <p className="mt-1 max-w-2xl text-sm text-ink-600">{description}</p>
                  )}
                </div>
                {actions && <div className="flex flex-wrap gap-2">{actions}</div>}
              </div>
            </div>
          )}
          {children}
        </main>
      </div>
    </div>
  );
}
