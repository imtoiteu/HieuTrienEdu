/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,

  // Emits a self-contained server bundle so the Docker runtime image does not need node_modules.
  // Required by docker/web.Dockerfile.
  output: 'standalone',
  // In a monorepo, Next needs to be told where the workspace root is, or the standalone trace
  // misses files hoisted above apps/web.
  outputFileTracingRoot: new URL('../../', import.meta.url).pathname,

  // The workspace packages ship raw TypeScript rather than a build step, so Next compiles them
  // as part of the app. This keeps the monorepo free of a separate build pipeline per package.
  transpilePackages: [
    '@hietedu/ui',
    '@hietedu/curriculum',
    '@hietedu/exercise-engine',
    '@hietedu/localization',
    '@hietedu/analytics',
    '@hietedu/ai',
  ],

  env: {
    NEXT_PUBLIC_PLATFORM_NAME: process.env.NEXT_PUBLIC_PLATFORM_NAME ?? 'HieuTrienEducation',
  },

  async redirects() {
    return [
      // The site is locale-prefixed; bare paths land on the default locale.
      { source: '/', destination: '/en', permanent: false },
    ];
  },
};

export default nextConfig;
