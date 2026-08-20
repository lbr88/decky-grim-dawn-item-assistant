#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
target="/home/deck/homebrew/plugins/decky-grim-dawn-item-assistant"

if [[ "$(id -u)" -eq 0 || "${HOME:-}" != "/home/deck" ]]; then
    echo "Run this as the deck user, not root." >&2
    exit 1
fi
if [[ ! -f "${repo_root}/dist/index.js" ]]; then
    echo "Missing dist/index.js; run pnpm run build first." >&2
    exit 1
fi
if [[ "${target}" != "/home/deck/homebrew/plugins/decky-grim-dawn-item-assistant" ]]; then
    echo "Refusing unexpected plugin target: ${target}" >&2
    exit 1
fi

sudo -v
sudo install -d -m 0755 "${target}/backend" "${target}/dist" "${target}/assets"
sudo install -m 0644 "${repo_root}/dist/index.js" "${target}/dist/index.js"
sudo install -m 0644 "${repo_root}/main.py" "${target}/main.py"
sudo install -m 0644 "${repo_root}/plugin.json" "${target}/plugin.json"
sudo install -m 0644 "${repo_root}/package.json" "${target}/package.json"
sudo install -m 0644 "${repo_root}/README.md" "${target}/README.md"
sudo install -m 0644 "${repo_root}/LICENSE" "${target}/LICENSE"
sudo install -m 0644 "${repo_root}/THIRD_PARTY_NOTICES.md" \
    "${target}/THIRD_PARTY_NOTICES.md"
sudo install -m 0644 "${repo_root}/assets/logo.svg" "${target}/assets/logo.svg"

for module in __init__ bridge controller inventory models paths processes; do
    sudo install -m 0644 "${repo_root}/backend/${module}.py" \
        "${target}/backend/${module}.py"
done

echo "Installed the local Decky plugin at ${target}"
echo "The Item Assistant bridge must be installed separately for transfers."
