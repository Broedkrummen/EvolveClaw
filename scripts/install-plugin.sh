#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PLUGIN_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

if [[ "${1:-}" == "--clawhub" ]]; then
    openclaw plugins install clawhub:evolveclaw --accept-capabilities
else
    cd "$PLUGIN_DIR"
    if [[ -f package-lock.json ]]; then
        npm ci --ignore-scripts
        npm run build
    elif [[ ! -f dist/index.js ]]; then
        echo "Missing built plugin. Use a source checkout or the release package."
        exit 1
    fi
    openclaw plugins install --link "$PLUGIN_DIR" --force --accept-capabilities
fi

# Conversation access is necessary for trace learning, and prompt access for injection.
openclaw config set plugins.entries.evolveclaw.hooks.allowConversationAccess true
openclaw config set plugins.entries.evolveclaw.hooks.allowPromptInjection true
openclaw plugins enable evolveclaw
openclaw plugins inspect evolveclaw --runtime --json

echo "EvolveClaw installed and enabled. Verify learning with a conversation turn."
echo "For a separately managed sidecar, run scripts/start-server.sh."
