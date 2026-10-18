# SoilSentinel Production Container
# Fully compatible with IBM LinuxONE (s390x) and AMD64 / ARM64 architectures

FROM node:22-bookworm-slim

WORKDIR /app

# Install Python 3 runtime and build essentials
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 \
    python3-pip \
    python3-venv \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Set up dedicated Python virtual environment
ENV VIRTUAL_ENV=/opt/venv
RUN python3 -m venv $VIRTUAL_ENV
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

# Install Python core dependencies (NumPy, Pandas, scikit-learn, requests)
COPY requirements-core.txt ./
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements-core.txt

# Install Node.js dependencies
# Note: node:sqlite (built into Node 22+) provides zero-compilation SQLite database support on s390x
COPY package.json package-lock.json ./
RUN npm ci --omit=optional

# Copy application source code, models, data, and configuration
COPY . .

# Set default production environment variables
ENV NODE_ENV=production
ENV PORT=3000
ENV PYTHON_PORT=5001
ENV PYTHON_CMD=python3
ENV DATA_DIR=data/
ENV SESSION_SECRET=soilsentinel-production-zseries-2026

# Expose web server and Python bridge ports
EXPOSE 3000
EXPOSE 5001

# Health check against Node.js Express & Python bridge status
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:3000/api/health || exit 1

# Start the unified backend
CMD ["node", "server.js"]
