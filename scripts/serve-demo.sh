#!/usr/bin/env bash
# Start the API and the web app for a demo server that people reach over the network.
#
# Running both from a plain `npm start` / `uvicorn` works only when the browser is on the same
# machine, because two settings default to loopback:
#
#   NEXT_PUBLIC_API_URL  is the address the *browser* calls. It defaults to 127.0.0.1:8000,
#                        which for a visitor resolves to their own computer, where nothing is
#                        listening. It is also inlined into the client bundle at build time, so
#                        changing it requires a rebuild, not just a restart.
#   CORS_ORIGINS         must list the origin the browser is on. If it does not, the API still
#                        answers 200 but omits Access-Control-Allow-Origin, the browser discards
#                        the response, and the page reports a network error — indistinguishable
#                        from the API being down.
#
# Both failures surface as "Cannot reach the server", and only on client-side calls such as
# login; server-rendered pages keep working, which makes it easy to miss.
#
# Set PUBLIC_HOST (or put the values in .env) and run this instead of starting the two by hand.
set -euo pipefail

cd "$(dirname "$0")/.."

# .env is gitignored and holds this host's public address.
if [[ -f .env ]]; then
  set -a; . ./.env; set +a
fi

PUBLIC_HOST="${PUBLIC_HOST:-127.0.0.1}"
WEB_PORT="${WEB_PORT:-3100}"
API_PORT="${API_PORT:-8000}"
: "${NEXT_PUBLIC_API_URL:=http://${PUBLIC_HOST}:${API_PORT}}"
: "${CORS_ORIGINS:=http://${PUBLIC_HOST}:${WEB_PORT},http://localhost:${WEB_PORT},http://127.0.0.1:${WEB_PORT}}"
export NEXT_PUBLIC_API_URL CORS_ORIGINS

echo "API  → http://${PUBLIC_HOST}:${API_PORT}"
echo "Web  → http://${PUBLIC_HOST}:${WEB_PORT}"
echo "browser calls the API at ${NEXT_PUBLIC_API_URL}"
echo "API allows origins: ${CORS_ORIGINS}"

# The built bundle carries whatever NEXT_PUBLIC_API_URL was set at build time, so a stale build
# silently keeps pointing at the old address. Rebuild unless told not to.
if [[ "${SKIP_BUILD:-0}" != "1" ]]; then
  echo "building web (NEXT_PUBLIC_API_URL is baked in at build time) ..."
  npm run build --workspace=@hietedu/web
fi

pkill -f "uvicorn app.main:app" 2>/dev/null || true
pkill -f "next start" 2>/dev/null || true
sleep 2

mkdir -p .run
( cd services/api && setsid nohup .venv/bin/python -m uvicorn app.main:app \
    --host 0.0.0.0 --port "${API_PORT}" > ../../.run/api.log 2>&1 & )
( cd apps/web && setsid nohup npx next start -p "${WEB_PORT}" -H 0.0.0.0 \
    > ../../.run/web.log 2>&1 & )

echo "waiting for both to answer ..."
for _ in $(seq 1 30); do
  api_up=$(curl -s -o /dev/null -w '%{http_code}' "http://127.0.0.1:${API_PORT}/api/v1/curriculum/subjects" || true)
  web_up=$(curl -s -o /dev/null -w '%{http_code}' "http://127.0.0.1:${WEB_PORT}/vi" || true)
  [[ "$api_up" == "200" && "$web_up" == "200" ]] && { echo "both up"; exit 0; }
  sleep 2
done

echo "one of them did not come up — see .run/api.log and .run/web.log" >&2
exit 1
