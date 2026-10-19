#!/bin/sh
# Re-apply the redesigned panel UI (premiere-pro-mcp --update overwrites it).
# Only index.html/styles.css change; main.js and the bridge logic stay upstream.
set -e
dest="$HOME/Library/Application Support/Adobe/CEP/extensions/MCPBridgeCEP"
here="$(cd "$(dirname "$0")" && pwd)"
cp "$here/index.html" "$here/styles.css" "$dest/"
echo "Panel UI installed. Close and reopen the panel in Premiere (Window > Extensions)."
