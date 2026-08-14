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

/**
 * Site footer.
 *
 * Contact details come from admin-managed settings rather than being hard-coded, with the
 * previous constants kept as fallbacks so the footer still renders if the API is unreachable.
 */
export function SiteFooter({
  settings = {},
}: {
  settings?: Record<string, Record<string, string>>;
}) {
  const { t, locale } = useI18n();
  const setting = (key: string, fallback: string) => settings[key]?.text || fallback;
  const address = setting('contact.address', '6A Thái Phiên, TP Vinh, Nghệ An');
  const phone = setting('contact.phone', '+84 24 1234 5678');
  const email = setting('contact.email', 'hello@hietrieneducation.vn');
  const tagline = setting('footer.tagline', '');
  const social = Object.entries(settings)
    .filter(([key, value]) => key.startsWith('social.') && value?.text)
    .map(([key, value]) => ({ name: key.replace('social.', ''), url: value.text }));
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
              {tagline || t('footer.tagline')}
            </p>
            <ul className="mt-5 space-y-2 text-sm text-ink-600">
              <li className="flex items-start gap-2">
                <MapPin className="mt-0.5 h-4 w-4 shrink-0 text-brand-500" aria-hidden="true" />
                {address}
              </li>
              <li className="flex items-center gap-2">
                <Phone className="h-4 w-4 shrink-0 text-brand-500" aria-hidden="true" />
                <a
                  href={`tel:${phone.replace(/\s/g, '')}`}
                  className="hover:text-brand-700 hover:underline"
                >
                  {phone}
                </a>
              </li>
              <li className="flex items-center gap-2">
                <Mail className="h-4 w-4 shrink-0 text-brand-500" aria-hidden="true" />
                <a href={`mailto:${email}`} className="hover:text-brand-700 hover:underline">
                  {email}
                </a>
              </li>
            </ul>
            {social.length > 0 && (
              <ul className="mt-4 flex flex-wrap gap-3">
                {social.map((link) => (
                  <li key={link.name}>
                    <a
                      href={link.url}
                      target="_blank"
                      rel="noreferrer"
                      className="text-sm font-bold capitalize text-brand-600 hover:underline"
                    >
                      {link.name}
                    </a>
                  </li>
                ))}
              </ul>
            )}
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
            {settings['footer.copyright']?.text ??
              `© ${year} ${t('brand.name')}. ${t('footer.rights')}`}
          </p>
          <p className="text-ink-400">{t('footer.builtWith')}</p>
        </div>
      </div>
    </footer>
  );
}
