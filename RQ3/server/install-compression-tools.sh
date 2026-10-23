#!/usr/bin/env bash
#
# install_compression_tools.sh
#
# Installs the CLI tools needed to decompress the packages
# on Debian/Ubuntu:
#   - gzip     (DEFLATE)
#   - xz       (LZMA2)
#   - zstd     (Zstandard)
#   - brotli   (Brotli)
#   - zopfli
#
# Run with: bash install_compression_tools.sh

set -euo pipefail

log() { printf '\n\033[1;32m==> %s\033[0m\n' "$1"; }

log "Installing gzip, xz-utils, zstd, brotli, zopfli..."
sudo apt-get install -y gzip xz-utils zstd brotli zopfli

log "Verifying installations..."

MISSING=0
for tool in gzip xz zstd brotli zopfli; do
  if command -v "$tool" >/dev/null 2>&1; then
    printf '  %-8s -> %s\n' "$tool" "$(command -v "$tool")"
  else
    printf '  %-8s -> NOT FOUND\n' "$tool"
    MISSING=1
  fi
done

if [ "$MISSING" -eq 1 ]; then
  echo ""
  echo "One or more tools failed to install. Check the output above." >&2
  exit 1
fi

log "All tools installed successfully."
