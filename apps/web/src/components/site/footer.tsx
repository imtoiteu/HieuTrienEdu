'use client';

import Link from 'next/link';
import { Mail, MapPin, Phone } from 'lucide-react';

import { Logo, Squiggle } from '@hietedu/ui';

import { useI18n } from '@/lib/i18n';

const COLUMNS: { titleKey: string; links: { labelKey: string; href: string }[] }[] = [
  {
    titleKey: 'footer.learn',
    links: [
      { labelKey: 'nav.mathematics', href: '/mathematics' },
      { labelKey: 'nav.physics', href: '/physics' },
      { labelKey: 'nav.courses', href: '/courses' },
      { labelKey: 'nav.methods', href: '/learning-methods' },
      { labelKey: 'nav.blog', href: '/blog' },
    ],
  },
  {
    titleKey: 'footer.tutoring',
    links: [
      { labelKey: 'nav.oneToOne', href: '/tutoring/one-to-one' },
      { labelKey: 'nav.groupClasses', href: '/tutoring/group' },
      { labelKey: 'nav.onlineClasses', href: '/tutoring/online' },
      { labelKey: 'nav.liveClasses', href: '/tutoring/live' },
      { labelKey: 'nav.recordedCourses', href: '/tutoring/recorded' },
      { labelKey: 'nav.pricing', href: '/pricing' },
    ],
  },
  {
    titleKey: 'footer.company',
    links: [
      { labelKey: 'nav.about', href: '/about' },
      { labelKey: 'nav.teachers', href: '/teachers' },
      { labelKey: 'nav.testimonials', href: '/testimonials' },
      { labelKey: 'nav.contact', href: '/contact' },
    ],
  },
];

export function SiteFooter() {
  const { t, locale } = useI18n();
  const href = (path: string) => `/${locale}${path}`;
  const year = new Date().getFullYear();

  return (
    <footer className="mt-auto border-t-2 border-ink-100 bg-white">
      <Squiggle className="h-3 w-full text-brand-300" tone="#CFC2FF" />
      <div className="mx-auto w-full max-w-7xl px-5 py-14 sm:px-8 lg:px-12">
        <div className="grid gap-10 lg:grid-cols-[1.4fr_repeat(3,1fr)]">
          <div>
            <Logo />
            <p className="mt-4 max-w-xs text-sm leading-relaxed text-ink-600">
              {t('footer.tagline')}
            </p>
            <ul className="mt-5 space-y-2 text-sm text-ink-600">
              <li className="flex items-center gap-2">
                <MapPin className="h-4 w-4 shrink-0 text-brand-500" aria-hidden="true" />
                Hà Nội, Việt Nam
              </li>
              <li className="flex items-center gap-2">
                <Phone className="h-4 w-4 shrink-0 text-brand-500" aria-hidden="true" />
                <a href="tel:+842412345678" className="hover:text-brand-700 hover:underline">
                  +84 24 1234 5678
                </a>
              </li>
              <li className="flex items-center gap-2">
                <Mail className="h-4 w-4 shrink-0 text-brand-500" aria-hidden="true" />
                <a
                  href="mailto:hello@hietrieneducation.vn"
                  className="hover:text-brand-700 hover:underline"
                >
                  hello@hietrieneducation.vn
                </a>
              </li>
            </ul>
          </div>

          {COLUMNS.map((column) => (
            <nav key={column.titleKey} aria-label={t(column.titleKey)}>
              <h2 className="font-display text-sm font-extrabold uppercase tracking-widest text-ink-900">
                {t(column.titleKey)}
              </h2>
              <ul className="mt-4 space-y-2.5">
                {column.links.map((link) => (
                  <li key={link.href}>
                    <Link
                      href={href(link.href)}
                      className="text-sm text-ink-600 transition-colors hover:text-brand-700 hover:underline"
                    >
                      {t(link.labelKey)}
                    </Link>
                  </li>
                ))}
              </ul>
            </nav>
          ))}
        </div>

        <div className="mt-12 flex flex-col gap-3 border-t-2 border-ink-100 pt-6 text-sm text-ink-500 sm:flex-row sm:items-center sm:justify-between">
          <p>
            © {year} {t('brand.name')}. {t('footer.rights')}
          </p>
          <p className="text-ink-400">{t('footer.builtWith')}</p>
        </div>
      </div>
    </footer>
  );
}
