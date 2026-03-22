#!/bin/bash
# Lokales Build-Skript für Hasi's ID3-Tag-Editor
# Erzeugt eine standalone .app im dist/ Ordner

set -e

echo "=== Hasi's ID3-Tag-Editor — Build ==="
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
pyinstaller HasisTagEditor.spec --noconfirm

echo "→ Erstelle ZIP..."
cd dist
zip -r "../Hasis-ID3-Tag-Editor-macOS.zip" "Hasi's ID3-Tag-Editor.app"
cd ..

echo ""
echo "=== Fertig! ==="
echo "App:  dist/Hasi's ID3-Tag-Editor.app"
echo "ZIP:  Hasis-ID3-Tag-Editor-macOS.zip"
echo ""
echo "Zum Starten: open \"dist/Hasi's ID3-Tag-Editor.app\""
