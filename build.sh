#!/usr/bin/env bash
# Gera vocab_miner.zip pronto para instalar no Anki.
# O config.json dentro do zip é gerado a partir do config.example.json
# (sem API keys), independente do config.json local.
set -euo pipefail

OUTFILE="vocab_miner.zip"
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT

echo "Copiando arquivos..."
cp vocab_miner.py "$TMP/"
cp __init__.py    "$TMP/"
cp manifest.json  "$TMP/"
cp config.example.json "$TMP/config.json"

echo "Gerando $OUTFILE..."
(cd "$TMP" && zip -q "$OUTFILE" vocab_miner.py __init__.py manifest.json config.json)
mv "$TMP/$OUTFILE" "./$OUTFILE"

echo "Pronto: $OUTFILE"
