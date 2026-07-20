FROM python:3.11-slim

# ── Dependências de sistema ────────────────────────────────────────────────────
RUN apt-get update && apt-get install -y --no-install-recommends \
        wget gnupg ca-certificates curl \
        # Chrome deps
        fonts-liberation libasound2 libatk-bridge2.0-0 libatk1.0-0 \
        libcups2 libdbus-1-3 libgdk-pixbuf2.0-0 libgtk-3-0 libnspr4 \
        libnss3 libx11-xcb1 libxcomposite1 libxdamage1 libxrandr2 \
        xdg-utils libxshmfence1 libgbm1 libpangocairo-1.0-0 libxss1 \
        # ddddocr deps
        libgl1 libglib2.0-0 libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# ── Google Chrome Stable (real binary — bypassa ShieldSquare do FGTS) ─────────
RUN wget -q -O /tmp/chrome.deb \
        "https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb" \
    && apt-get install -y --no-install-recommends /tmp/chrome.deb \
    && rm /tmp/chrome.deb \
    && rm -rf /var/lib/apt/lists/*

# ── App ───────────────────────────────────────────────────────────────────────
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Playwright: instalar apenas Chromium (fallback para portais sem anti-bot)
RUN playwright install --with-deps chromium

COPY . .

EXPOSE 8501

# Railway injeta $PORT; Streamlit usa --server.port
CMD ["sh", "-c", "streamlit run app.py --server.port=${PORT:-8501} --server.address=0.0.0.0 --server.headless=true"]
