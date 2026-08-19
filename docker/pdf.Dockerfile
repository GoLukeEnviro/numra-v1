# mcr.microsoft.com/playwright ships Chromium + all system deps preinstalled, matched
# to the pinned @playwright/... version below.
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
