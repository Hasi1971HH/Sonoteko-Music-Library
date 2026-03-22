#!/bin/bash
# Build-Skript für Sonoteko
# Erzeugt eine standalone macOS .app im dist/ Ordner

set -e

echo "=== Sonoteko — Build ==="
echo ""

# Virtuelle Umgebung prüfen/erstellen
if [ ! -d "venv" ]; then
    echo "→ Erstelle virtuelle Umgebung..."
    python3 -m venv venv
fi

echo "→ Aktiviere virtuelle Umgebung..."
source venv/bin/activate

echo "→ Installiere Abhängigkeiten..."
pip install -r requirements.txt pyinstaller --quiet

echo "→ Baue App..."
pyinstaller Sonoteko.spec --noconfirm

echo "→ Erstelle ZIP..."
cd dist
zip -r "../Sonoteko-macOS.zip" "Sonoteko.app"
cd ..

echo ""
echo "=== Fertig! ==="
echo "App:  dist/Sonoteko.app"
echo "ZIP:  Sonoteko-macOS.zip"
echo ""
echo "Zum Starten: open dist/Sonoteko.app"
