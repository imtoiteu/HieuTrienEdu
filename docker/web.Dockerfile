# HieuTrienEducation web app
#
# Uses Next.js standalone output so the runtime image ships only the server and the files it
# actually needs, rather than the whole node_modules tree.
FROM node:20-alpine AS base
ENV NEXT_TELEMETRY_DISABLED=1
WORKDIR /srv

# --- dependencies -----------------------------------------------------------------------
FROM base AS deps

# Workspace manifests only, so a source change does not re-run the install.
COPY package.json package-lock.json* ./
COPY apps/web/package.json apps/web/
COPY packages/ui/package.json packages/ui/
COPY packages/curriculum/package.json packages/curriculum/
COPY packages/exercise-engine/package.json packages/exercise-engine/
COPY packages/localization/package.json packages/localization/
COPY packages/analytics/package.json packages/analytics/
COPY packages/ai/package.json packages/ai/

RUN npm ci --omit=optional --no-audit --no-fund

# --- build ------------------------------------------------------------------------------
FROM base AS builder

COPY --from=deps /srv/node_modules ./node_modules
COPY . .

# NEXT_PUBLIC_* values are inlined at build time, so they must be present here rather than only
# at runtime. Compose passes them through as build args.
ARG NEXT_PUBLIC_API_URL=http://api:8000
ARG NEXT_PUBLIC_GEOGEBRA_ENABLED=false
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL \
    NEXT_PUBLIC_GEOGEBRA_ENABLED=$NEXT_PUBLIC_GEOGEBRA_ENABLED

# Cap V8's heap so the build fits on a memory-constrained host. Left to itself, Node grows the
# old space until the container is killed; a ceiling makes it collect more often and finish
# slower instead of dying. Raise it via --build-arg on a machine with room to spare.
ARG NODE_HEAP_MB=2048
ENV NODE_OPTIONS=--max-old-space-size=$NODE_HEAP_MB

RUN npm run build --workspace=@hietedu/web

# --- runtime ----------------------------------------------------------------------------
FROM base AS runtime

ENV NODE_ENV=production

RUN addgroup --system --gid 10001 nodejs \
    && adduser --system --uid 10001 nextjs

COPY --from=builder --chown=nextjs:nodejs /srv/apps/web/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /srv/apps/web/.next/static ./apps/web/.next/static
COPY --from=builder --chown=nextjs:nodejs /srv/apps/web/public ./apps/web/public

USER nextjs
EXPOSE 3000
ENV PORT=3000 HOSTNAME=0.0.0.0

HEALTHCHECK --interval=15s --timeout=5s --start-period=30s --retries=5 \
    CMD node -e "fetch('http://127.0.0.1:3000/en').then(r=>process.exit(r.ok?0:1)).catch(()=>process.exit(1))"

CMD ["node", "apps/web/server.js"]
