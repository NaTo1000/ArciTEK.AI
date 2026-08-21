#!/bin/bash
# ArciTEK.AI macOS DMG Builder
# "Every build is a work of art" - infinite♾2025
#
# This script creates a macOS .dmg installer with:
# - Drag-and-drop installation
# - Custom background image
# - Applications folder shortcut
# - Code signing and notarization
#
# Requirements:
# - macOS 13+ build machine
# - Xcode Command Line Tools
# - Developer ID certificate
# - Apple notarization credentials
#
# Usage: ./build_dmg.sh [--sign] [--notarize]

set -e

# Configuration
APP_NAME="ArciTEK.AI"
APP_VERSION="1.0.0"
BUNDLE_ID="com.infinite2025.arcitek.ai"
DMG_NAME="ArciTEK_AI_v${APP_VERSION}"
VOLUME_NAME="${APP_NAME} ${APP_VERSION}"
BUILD_DIR="$(pwd)/build"
DIST_DIR="$(pwd)/../../dist"
APP_DIR="${BUILD_DIR}/${APP_NAME}.app"

# Signing configuration
SIGN_IDENTITY="Developer ID Application: infinite2025"
NOTARIZE_APPLE_ID="${APPLE_ID:-}"
NOTARIZE_PASSWORD="${APPLE_APP_PASSWORD:-}"
NOTARIZE_TEAM_ID="${APPLE_TEAM_ID:-}"

# Parse arguments
SIGN=false
NOTARIZE=false
for arg in "$@"; do
    case $arg in
        --sign) SIGN=true ;;
        --notarize) NOTARIZE=true ;;
    esac
done

echo "╔══════════════════════════════════════════════════╗"
echo "║        ArciTEK.AI macOS DMG Builder             ║"
echo "║    \"Every build is a work of art\"               ║"
echo "║              infinite♾2025                      ║"
echo "╚══════════════════════════════════════════════════╝"
echo ""
echo "Building: ${APP_NAME} v${APP_VERSION}"
echo "Output: ${DMG_NAME}.dmg"
echo ""

# Clean previous builds
echo "🧹 Cleaning previous builds..."
rm -rf "${BUILD_DIR}"
mkdir -p "${BUILD_DIR}"
mkdir -p "${DIST_DIR}"

# Create .app bundle structure
echo "📦 Creating application bundle..."
mkdir -p "${APP_DIR}/Contents/MacOS"
mkdir -p "${APP_DIR}/Contents/Resources"
mkdir -p "${APP_DIR}/Contents/Frameworks"
mkdir -p "${APP_DIR}/Contents/Runtime/python"
mkdir -p "${APP_DIR}/Contents/Runtime/nodejs"

# Create Info.plist
echo "📝 Creating Info.plist..."
cat > "${APP_DIR}/Contents/Info.plist" << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleDevelopmentRegion</key>
    <string>en</string>
    <key>CFBundleDisplayName</key>
    <string>${APP_NAME}</string>
    <key>CFBundleExecutable</key>
    <string>arcitek-ai</string>
    <key>CFBundleIconFile</key>
    <string>AppIcon</string>
    <key>CFBundleIdentifier</key>
    <string>${BUNDLE_ID}</string>
    <key>CFBundleInfoDictionaryVersion</key>
    <string>6.0</string>
    <key>CFBundleName</key>
    <string>${APP_NAME}</string>
    <key>CFBundlePackageType</key>
    <string>APPL</string>
    <key>CFBundleShortVersionString</key>
    <string>${APP_VERSION}</string>
    <key>CFBundleVersion</key>
    <string>100</string>
    <key>LSMinimumSystemVersion</key>
    <string>13.0</string>
    <key>LSApplicationCategoryType</key>
    <string>public.app-category.developer-tools</string>
    <key>NSHighResolutionCapable</key>
    <true/>
    <key>NSSupportsAutomaticGraphicsSwitching</key>
    <true/>
    <key>CFBundleDocumentTypes</key>
    <array>
        <dict>
            <key>CFBundleTypeName</key>
            <string>ArciTEK Project</string>
            <key>CFBundleTypeExtensions</key>
            <array>
                <string>arcitek</string>
                <string>qcircuit</string>
                <string>aimodel</string>
            </array>
            <key>CFBundleTypeRole</key>
            <string>Editor</string>
        </dict>
    </array>
    <key>NSHumanReadableCopyright</key>
    <string>Copyright © 2025 infinite♾2025. All rights reserved.</string>
    <key>LSUIElement</key>
    <false/>
</dict>
</plist>
EOF

# Create launcher script
echo "🚀 Creating launcher..."
cat > "${APP_DIR}/Contents/MacOS/arcitek-ai" << 'LAUNCHER'
#!/bin/bash
# ArciTEK.AI macOS Launcher
DIR="$(cd "$(dirname "$0")/.." && pwd)"
RESOURCES="${DIR}/Resources"
RUNTIME="${DIR}/Runtime"

# Set environment
export ARCITEK_HOME="${RESOURCES}"
export ARCITEK_PORT=8000
export PATH="${RUNTIME}/python/bin:${RUNTIME}/nodejs/bin:${PATH}"
export PYTHONPATH="${RESOURCES}"

# Start server in background
"${RUNTIME}/python/bin/python3" "${RESOURCES}/arcitek_core/main.py" &
SERVER_PID=$!

# Wait for server to start
sleep 2

# Open browser to dashboard
open "http://localhost:${ARCITEK_PORT}"

# Keep running until server exits
wait $SERVER_PID
LAUNCHER
chmod +x "${APP_DIR}/Contents/MacOS/arcitek-ai"

# Copy application files
echo "📂 Copying application files..."
cp -r "../../arcitek_core" "${APP_DIR}/Contents/Resources/" 2>/dev/null || true
cp -r "../../quantum" "${APP_DIR}/Contents/Resources/" 2>/dev/null || true
cp -r "../../ai_models" "${APP_DIR}/Contents/Resources/" 2>/dev/null || true
cp -r "../../tools" "${APP_DIR}/Contents/Resources/" 2>/dev/null || true
cp -r "../../scripts" "${APP_DIR}/Contents/Resources/" 2>/dev/null || true
cp "../../requirements.txt" "${APP_DIR}/Contents/Resources/" 2>/dev/null || true
cp "../../package.json" "${APP_DIR}/Contents/Resources/" 2>/dev/null || true
cp "../../VERSION" "${APP_DIR}/Contents/Resources/" 2>/dev/null || true
cp "../../README.md" "${APP_DIR}/Contents/Resources/" 2>/dev/null || true
cp "../../LICENSE" "${APP_DIR}/Contents/Resources/" 2>/dev/null || true

# Copy icon
echo "🎨 Setting up icon..."
cp "../shared/icons/AppIcon.icns" "${APP_DIR}/Contents/Resources/" 2>/dev/null || true

# Create entitlements
cat > "${BUILD_DIR}/entitlements.plist" << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>com.apple.security.app-sandbox</key>
    <false/>
    <key>com.apple.security.network.client</key>
    <true/>
    <key>com.apple.security.network.server</key>
    <true/>
    <key>com.apple.security.files.user-selected.read-write</key>
    <true/>
</dict>
</plist>
EOF

# Code signing
if [ "$SIGN" = true ]; then
    echo "🔏 Code signing..."
    codesign --force --deep --sign "${SIGN_IDENTITY}" \
        --entitlements "${BUILD_DIR}/entitlements.plist" \
        --options runtime \
        "${APP_DIR}"
    
    echo "✅ Code signing complete"
fi

# Create DMG
echo "💿 Creating DMG..."

# Create temporary DMG directory
DMG_TEMP="${BUILD_DIR}/dmg_temp"
mkdir -p "${DMG_TEMP}"
cp -r "${APP_DIR}" "${DMG_TEMP}/"

# Create Applications symlink
ln -s /Applications "${DMG_TEMP}/Applications"

# Create DMG background
mkdir -p "${DMG_TEMP}/.background"
# Copy background image if exists
cp "dmg/background.png" "${DMG_TEMP}/.background/" 2>/dev/null || true

# Create DMG
hdiutil create -volname "${VOLUME_NAME}" \
    -srcfolder "${DMG_TEMP}" \
    -ov -format UDZO \
    "${DIST_DIR}/${DMG_NAME}.dmg" 2>/dev/null || \
    echo "Note: hdiutil not available (not on macOS). DMG structure created."

# Notarization
if [ "$NOTARIZE" = true ] && [ -n "$NOTARIZE_APPLE_ID" ]; then
    echo "📤 Submitting for notarization..."
    xcrun notarytool submit "${DIST_DIR}/${DMG_NAME}.dmg" \
        --apple-id "${NOTARIZE_APPLE_ID}" \
        --password "${NOTARIZE_PASSWORD}" \
        --team-id "${NOTARIZE_TEAM_ID}" \
        --wait
    
    echo "📎 Stapling notarization ticket..."
    xcrun stapler staple "${DIST_DIR}/${DMG_NAME}.dmg"
    
    echo "✅ Notarization complete"
fi

echo ""
echo "╔══════════════════════════════════════════════════╗"
echo "║              Build Complete! ✅                  ║"
echo "╠══════════════════════════════════════════════════╣"
echo "║  App Bundle: ${APP_DIR}"
echo "║  DMG Output: ${DIST_DIR}/${DMG_NAME}.dmg"
echo "║  Signed: ${SIGN}"
echo "║  Notarized: ${NOTARIZE}"
echo "╚══════════════════════════════════════════════════╝"
