#!/usr/bin/env bash
# Uruchom serwer Paper w tle (jeśli nie działa).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SERVER="$ROOT/server"
LOG="$ROOT/logs/mc_server.log"
PIDFILE="$ROOT/logs/mc_server.pid"
mkdir -p "$ROOT/logs"

if [[ -f "$PIDFILE" ]]; then
  old_pid="$(cat "$PIDFILE")"
  if kill -0 "$old_pid" 2>/dev/null; then
    echo "Serwer już działa (pid $old_pid)"
    exit 0
  fi
fi

if python3 -c "import socket; s=socket.create_connection(('127.0.0.1',5555),2); s.close()" 2>/dev/null; then
  echo "Bridge :5555 już otwarty — serwer prawdopodobnie działa"
  exit 0
fi

cd "$SERVER"
JAR="paper-1.20.4-499.jar"
if [[ ! -f "$JAR" ]]; then
  echo "Brak $JAR w $SERVER"
  exit 1
fi
nohup java -Xms2G -Xmx4G -jar "$JAR" --nogui >>"$LOG" 2>&1 &
echo $! >"$PIDFILE"
echo "Serwer startuje w tle (pid $(cat "$PIDFILE")), log: $LOG"
