'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import {
  BarChart3,
  BookOpen,
  CalendarDays,
  ClipboardList,
  Home,
  LayoutDashboard,
  LogOut,
  Settings,
  Trophy,
  Users,
} from 'lucide-react';
import type { ReactNode } from 'react';

import { Avatar, Logo, Spinner, cn } from '@hietedu/ui';

import { useAuth } from '@/lib/auth';
import { useI18n } from '@/lib/i18n';

interface NavLink {
  href: string;
  labelKey: string;
  icon: typeof Home;
}

const NAV_BY_ROLE: Record<string, NavLink[]> = {
  student: [
    { href: '/dashboard', labelKey: 'nav.dashboard', icon: LayoutDashboard },
    { href: '/courses', labelKey: 'nav.courses', icon: BookOpen },
    { href: '/progress', labelKey: 'nav.progress', icon: BarChart3 },
    { href: '/achievements', labelKey: 'nav.achievements', icon: Trophy },
  ],
  teacher: [
    { href: '/teacher', labelKey: 'nav.dashboard', icon: LayoutDashboard },
    { href: '/teacher/questions', labelKey: 'teacher.questionBank', icon: ClipboardList },
    { href: '/courses', labelKey: 'nav.courses', icon: BookOpen },
  ],
  admin: [
    { href: '/admin', labelKey: 'admin.overview', icon: LayoutDashboard },
    { href: '/teacher/questions', labelKey: 'teacher.questionBank', icon: ClipboardList },
    { href: '/courses', labelKey: 'nav.courses', icon: BookOpen },
  ],
  parent: [
    { href: '/parent', labelKey: 'parent.children', icon: Users },
    { href: '/parent/payments', labelKey: 'parent.payments', icon: CalendarDays },
  ],
};

/**
 * Shell for every signed-in area of the product.
 *
 * On desktop the navigation is a persistent sidebar; on mobile it collapses to a bottom bar,
 * because students overwhelmingly use phones and a hamburger menu costs a tap on every
 * navigation.
 */
export function AppShell({
  children,
  role,
  loading,
}: {
  /** Optional so a page can render `<AppShell role=… loading />` while auth resolves. */
  children?: ReactNode;
  role: string;
  loading?: boolean;
}) {
  const { t, locale } = useI18n();
  const { user, logout } = useAuth();
  const pathname = usePathname();

  const links = NAV_BY_ROLE[role] ?? NAV_BY_ROLE.student;
  const href = (path: string) => `/${locale}${path}`;
  const isActive = (path: string) => pathname === href(path);

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-cream">
        <Spinner className="h-8 w-8 text-brand-500" />
        <span className="sr-only">{t('common.loading')}</span>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-cream lg:flex">
      {/* desktop sidebar */}
      <aside className="hidden w-64 shrink-0 border-r-2 border-ink-100 bg-white lg:flex lg:flex-col">
        <div className="border-b-2 border-ink-100 p-5">
          <Link href={href('')} aria-label={t('brand.name')}>
            <Logo />
          </Link>
        </div>

        <nav aria-label={t('admin.dash.title')} className="flex-1 space-y-1 p-4">
          {links.map((link) => (
            <Link
              key={link.href}
              href={href(link.href)}
              aria-current={isActive(link.href) ? 'page' : undefined}
              className={cn(
                'flex items-center gap-3 rounded-2xl px-3.5 py-3 text-sm font-bold transition-colors',
                isActive(link.href)
                  ? 'bg-brand-500 text-white shadow-pop-sm'
                  : 'text-ink-700 hover:bg-ink-100',
              )}
            >
              <link.icon className="h-5 w-5 shrink-0" aria-hidden="true" />
              {t(link.labelKey)}
            </Link>
          ))}
        </nav>

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
          <div className="space-y-1">
            <Link
              href={href('/settings')}
              className="flex items-center gap-3 rounded-2xl px-3.5 py-2.5 text-sm font-semibold text-ink-600 transition-colors hover:bg-ink-100"
            >
              <Settings className="h-4 w-4" aria-hidden="true" />
              {t('nav.settings')}
            </Link>
            <button
              type="button"
              onClick={logout}
              className="flex w-full items-center gap-3 rounded-2xl px-3.5 py-2.5 text-sm font-semibold text-ink-600 transition-colors hover:bg-ink-100"
            >
              <LogOut className="h-4 w-4" aria-hidden="true" />
              {t('common.logout')}
            </button>
          </div>
        </div>
      </aside>

      {/* mobile top bar */}
      <header className="sticky top-0 z-40 flex h-16 items-center justify-between border-b-2 border-ink-100 bg-white px-5 lg:hidden">
        <Link href={href('')} aria-label={t('brand.name')}>
          <Logo showWordmark={false} />
        </Link>
        <div className="flex items-center gap-2">
          {user && <Avatar name={user.full_name} src={user.avatar_url} size="sm" />}
          <button
            type="button"
            onClick={logout}
            aria-label={t('common.logout')}
            className="rounded-xl p-2 text-ink-500 hover:bg-ink-100"
          >
            <LogOut className="h-4 w-4" aria-hidden="true" />
          </button>
        </div>
      </header>

      <div className="flex-1 pb-24 lg:pb-0">
        <main id="main">{children}</main>
      </div>

      {/* mobile bottom navigation */}
      <nav
        aria-label={t('admin.dash.title')}
        className="fixed inset-x-0 bottom-0 z-40 border-t-2 border-ink-100 bg-white lg:hidden"
      >
        <ul className="flex">
          {links.slice(0, 5).map((link) => (
            <li key={link.href} className="flex-1">
              <Link
                href={href(link.href)}
                aria-current={isActive(link.href) ? 'page' : undefined}
                className={cn(
                  'flex flex-col items-center gap-1 px-1 py-3 text-[0.65rem] font-bold',
                  isActive(link.href) ? 'text-brand-600' : 'text-ink-500',
                )}
              >
                <link.icon className="h-5 w-5" aria-hidden="true" />
                <span className="truncate">{t(link.labelKey)}</span>
              </Link>
            </li>
          ))}
        </ul>
      </nav>
    </div>
  );
}
