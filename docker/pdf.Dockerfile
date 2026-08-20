# mcr.microsoft.com/playwright ships Chromium pre-installed for the EXACT version in
# its tag -- nothing else. apps/pdf/package.json's own "playwright" dependency MUST
# stay pinned to that exact same version (no ^ range): this `npm install` only sees
# package.json, never pnpm-lock.yaml, so a caret range genuinely floats forward as
# newer 1.x releases hit the registry, with nothing here to catch the drift. A
# mismatch doesn't fail this build -- it fails at render time instead, with
# Playwright refusing to launch the (now version-mismatched) pre-installed browser
# ("Executable doesn't exist ... Looks like Playwright was just updated"). Confirmed
# the hard way via a real docker-compose-e2e run: package.json had drifted to
# resolving 1.62.1 against this image's baked-in 1.56.1 browser, and every PDF
# export failed fast (not a timeout -- a real fixed bug immune to waiting longer).
FROM mcr.microsoft.com/playwright:v1.56.1-jammy AS base
WORKDIR /app

COPY apps/pdf/package.json ./
RUN npm install --omit=dev

COPY apps/pdf/src ./src

RUN addgroup --system numra && adduser --system --ingroup numra numra
USER numra

EXPOSE 4300
HEALTHCHECK --interval=10s --timeout=5s --start-period=15s --retries=5 \
  CMD node -e "fetch('http://127.0.0.1:4300/health/ready').then(r=>process.exit(r.ok?0:1)).catch(()=>process.exit(1))"
CMD ["node", "src/server.js"]
