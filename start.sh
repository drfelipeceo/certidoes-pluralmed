#!/bin/sh
# Inicia Tor em background e aguarda SOCKS5 estar disponível
mkdir -p /tmp/tor-data
tor --RunAsDaemon 1 \
    --DataDirectory /tmp/tor-data \
    --Log "warn stderr" \
    --SocksPort 9050 \
    --MaxMemInQueues 10 MB \
    --NumEntryGuards 1 \
    --BandwidthRate 2 MB \
    --BandwidthBurst 4 MB

echo "Aguardando Tor bootstrapar..."
i=0
while [ $i -lt 40 ]; do
    python3 -c "
import socket
s = socket.socket()
s.settimeout(1)
exit(0 if s.connect_ex(('127.0.0.1', 9050)) == 0 else 1)
" 2>/dev/null && echo "Tor pronto." && break
    sleep 1
    i=$((i+1))
done

exec streamlit run app.py \
    --server.port="${PORT:-8501}" \
    --server.address=0.0.0.0 \
    --server.headless=true
