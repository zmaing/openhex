#!/bin/bash

# openhex macOS App Build Script
# This script builds openhex as a standalone macOS application

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "======================================"
echo "openhex Build Script"
echo "======================================"

# Check Python version
PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
echo "Python version: $PYTHON_VERSION"

# Install dependencies
echo ""
echo "Installing dependencies..."
pip install -q PyQt6>=6.6.0

# Clean old builds
echo ""
echo "Cleaning old builds..."
rm -rf dist build

# Build with PyInstaller
echo ""
echo "Building application..."

# Create spec file content
cat > openhex.spec << 'EOF'
# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['openhex.py'],
    pathex=['.'],
    binaries=[],
    datas=[('config', 'config'), ('src/utils', 'src/utils')],
    hiddenimports=['PyQt6.QtCore', 'PyQt6.QtGui', 'PyQt6.QtWidgets'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = AEXYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='openhex',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch='universal2',
    codesign_identity=None,
    entitlements_file=None,
    icon='resources/icon.icns',
)
EOF

# Create resources directory
mkdir -p resources

# Try to build
if [ -f "requirements.txt" ]; then
    echo "Using PyInstaller to build..."
    pip install -q pyinstaller
    pyinstaller --onefile --windowed --name openhex --osx-bundle-identifier io.openhex.app openhex.py
fi

echo ""
echo "Build complete!"
echo "Output: dist/openhex.app"

# Create DMG if requested
if [ "$1" == "--dmg" ]; then
    echo ""
    echo "Creating DMG..."
    hdiutil create -volname 'openhex' \
        -srcfolder dist/openhex.app \
        -ov -format UDZO dist/openhex.dmg
    echo "DMG created: dist/openhex.dmg"
fi

echo ""
echo "Done!"
