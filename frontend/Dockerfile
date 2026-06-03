# ── Frontend production stage ────────────────────────────────────────────────
FROM oven/bun:1.2-alpine

WORKDIR /app

# Copy manifests first for better layer caching
COPY package.json bun.lock bunfig.toml ./

# Install all deps
RUN bun install --frozen-lockfile

# Copy source
COPY . .

# Expose API URL at build time (overrideable via docker-compose build args)
ARG VITE_API_BASE_URL=http://localhost:8000
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL

# Build the TanStack Start app
RUN bun run build

# Set environment variables for the Nitro server
ENV HOST=0.0.0.0
ENV PORT=3000

EXPOSE 3000

# Run the preview server
CMD ["bun", "run", "preview"]
