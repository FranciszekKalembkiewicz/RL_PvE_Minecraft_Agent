#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

PAPER_VERSION="1.20.4"
BUILD="499"
JAR="paper-${PAPER_VERSION}-${BUILD}.jar"

if [[ ! -f "$JAR" ]]; then
  echo "Pobieranie Paper ${PAPER_VERSION}..."
  curl -fsSL "https://api.papermc.io/v2/projects/paper/versions/${PAPER_VERSION}/builds/${BUILD}/downloads/${JAR}" -o "$JAR"
fi

if [[ ! -f eula.txt ]]; then
  echo "eula=true" > eula.txt
  echo "Zaakceptowano EULA (eula=true)."
fi

mkdir -p plugins
echo "Paper gotowy: $JAR"
echo "Skompiluj plugin: cd plugins/WaveArena && mvn package"
echo "Następnie: cp plugins/WaveArena/target/WaveArena-*.jar plugins/"
