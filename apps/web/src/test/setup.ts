import { vi } from 'vitest';

import '@testing-library/jest-dom/vitest';

// KaTeX injects its stylesheet via a CSS import, which jsdom cannot parse. Component tests only
// assert on rendered text, so a no-op stub keeps them focused on behaviour.
//
// `vi` is imported explicitly rather than relying on vitest's globals: this file is inside the
// Next.js tsconfig include, and the production build typechecks it. A bare global would fail the
// build with "Cannot find name 'vi'".
vi.mock('katex/dist/katex.min.css', () => ({}));
