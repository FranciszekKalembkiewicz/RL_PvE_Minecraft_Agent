#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

PAPER_VERSION="1.20.4"
BUILD="499"
JAR="paper-${PAPER_VERSION}-${BUILD}.jar"

if [[ ! -f "$JAR" ]]; then
  echo "Brak $JAR — uruchom ./setup_server.sh"
  exit 1
fi

exec java -Xms2G -Xmx4G -jar "$JAR" --nogui
