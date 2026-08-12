import { render, type RenderOptions } from '@testing-library/react';
import type { ReactElement, ReactNode } from 'react';

import en from '@/messages/en.json';
import { I18nProvider } from '@/lib/i18n';

/**
 * Render a component inside the providers it expects.
 *
 * Uses the real English dictionary rather than a stub, so a test that asserts on visible text is
 * also asserting that the translation key exists — a missing key would surface as the raw key.
 */
export function renderWithProviders(ui: ReactElement, options?: Omit<RenderOptions, 'wrapper'>) {
  function Wrapper({ children }: { children: ReactNode }) {
    return (
      <I18nProvider locale="en" dictionary={en as Record<string, string>} fallback={en as Record<string, string>}>
        {children}
      </I18nProvider>
    );
  }
  return render(ui, { wrapper: Wrapper, ...options });
}

export * from '@testing-library/react';
