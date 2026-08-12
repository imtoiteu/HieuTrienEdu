import '@testing-library/jest-dom/vitest';

// KaTeX injects its stylesheet via CSS import, which jsdom cannot parse. Component tests only
// assert on rendered text, so a no-op stub keeps them focused on behaviour.
vi.mock('katex/dist/katex.min.css', () => ({}));
