import { redirect } from 'next/navigation';

import { isLocale } from '@hietedu/localization';

/**
 * `/tutoring` has no page of its own — the five formats under it do.
 *
 * It is still a real destination, because the header's "Tutoring" menu is a link as well as a
 * dropdown, so anyone who clicks the parent rather than hovering for the submenu landed on a 404.
 * Redirecting to one-to-one rather than inventing an index page keeps the dropdown as the single
 * description of what the formats are; one-to-one is the entry point the centre leads with.
 */
export default async function TutoringIndex({
  params,
}: {
  params: Promise<{ locale: string }>;
}) {
  const { locale: raw } = await params;
  redirect(`/${isLocale(raw) ? raw : 'vi'}/tutoring/one-to-one`);
}
