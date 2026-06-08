#!/usr/bin/env bash
# Wymaga Maven: brew install maven
set -euo pipefail
cd "$(dirname "$0")"
mvn package -q -DskipTests
JAR=$(ls target/WaveArena-*.jar | head -1)
mkdir -p ../../plugins
cp "$JAR" ../../plugins/
echo "Skopiowano: ../../plugins/$(basename "$JAR")"
