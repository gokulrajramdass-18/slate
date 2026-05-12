# Multi-stage Dockerfile for Slate Frontend
# Optimized for production deployment with Next.js

# Stage 1: Dependencies
FROM node:20-alpine AS deps

WORKDIR /app

# Copy package files
COPY package*.json ./

# Install dependencies
RUN npm ci --only=production

# Stage 2: Builder
FROM node:20-alpine AS builder

WORKDIR /app

# Copy dependencies from deps stage
COPY --from=deps /app/node_modules ./node_modules

# Copy source files and create public directory if it doesn't exist
COPY . ./
RUN mkdir -p public

# Build the application with API URL
ARG NEXT_PUBLIC_API_URL
ARG NEXT_PUBLIC_XSUAA_ENABLED
ENV NEXT_TELEMETRY_DISABLED 1
ENV NEXT_PUBLIC_API_URL=${NEXT_PUBLIC_API_URL}
ENV NEXT_PUBLIC_XSUAA_ENABLED=${NEXT_PUBLIC_XSUAA_ENABLED}
RUN npm run build

# Stage 3: Runner
FROM node:20-alpine AS runner

WORKDIR /app

# Set NODE_ENV
ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED 1

# Create non-root user
RUN addgroup --system --gid 1001 nodejs && \
    adduser --system --uid 1001 nextjs

# Copy necessary files from builder (public directory may be empty)
COPY --from=builder /app/public ./public
COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static

# Switch to non-root user
USER nextjs

# Expose port
EXPOSE 3000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD node -e "require('http').get('http://localhost:3000', (res) => process.exit(res.statusCode === 200 ? 0 : 1))"

# Set environment variables
ENV PORT=3000 \
    HOSTNAME=0.0.0.0

# Start the application
CMD ["node", "server.js"]
