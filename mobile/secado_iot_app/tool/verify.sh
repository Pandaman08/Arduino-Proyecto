#!/usr/bin/env bash
# Isolate generated files and avoid Flutter LSP Unicode-path failures.
set -euo pipefail
mobile_root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
check_dir=$(mktemp -d /tmp/secado-iot-check.XXXXXX)
trap 'rm -rf -- "$check_dir"' EXIT
flutter_bin=${FLUTTER_BIN:-flutter}
# Absolute path keeps a caller-supplied SDK usable after changing directories.
flutter_bin=$(command -v "$flutter_bin")
tar -C "$mobile_root" --exclude='./build' --exclude='./.dart_tool' \
  --exclude='./android/.gradle' --exclude='./android/.kotlin' \
  --exclude='./android/local.properties' --exclude='./.flutter-plugins-dependencies' -cf - . |
  tar -C "$check_dir" -xf -
cd "$check_dir"
"$flutter_bin" pub get
"$flutter_bin" analyze
"$flutter_bin" test --reporter expanded
"$flutter_bin" build apk --debug
mkdir -p "$mobile_root/build/app/outputs/flutter-apk"
cp build/app/outputs/flutter-apk/app-debug.apk "$mobile_root/build/app/outputs/flutter-apk/"
printf 'APK: %s/build/app/outputs/flutter-apk/app-debug.apk\n' "$mobile_root"
