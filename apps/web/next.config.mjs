/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,

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
