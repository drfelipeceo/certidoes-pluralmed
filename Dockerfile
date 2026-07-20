FROM python:3.11-slim

# ── Dependências mínimas + Tor ─────────────────────────────────────────────────
RUN apt-get update && apt-get install -y --no-install-recommends \
        wget ca-certificates curl tor \
        libgl1 libglib2.0-0 libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# ── Google Chrome Stable (bypassa ShieldSquare via TLS fingerprint no Mac) ─────
RUN wget -q -O /tmp/chrome.deb \
        "https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb" \
    && apt-get update \
    && apt-get install -y /tmp/chrome.deb \
    && rm /tmp/chrome.deb \
    && rm -rf /var/lib/apt/lists/*

# ── App ───────────────────────────────────────────────────────────────────────
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

RUN playwright install --with-deps chromium

COPY . .

RUN chmod +x start.sh

EXPOSE 8501

CMD ["./start.sh"]
