#!/usr/bin/env bash
set -euo pipefail

repository="lbr88/decky-grim-dawn-item-assistant"
release_base="${GDIA_RELEASE_BASE_URL:-https://github.com/${repository}/releases/latest/download}"
plugin_parent="${GDIA_PLUGIN_ROOT:-/home/deck/homebrew/plugins}"
plugin_name="decky-grim-dawn-item-assistant"
plugin_target="${plugin_parent}/${plugin_name}"
iagd_dir="${GDIA_IAGD_DIR:-/home/deck/.local/share/Steam/steamapps/compatdata/219990/pfx/drive_c/Program Files/IAGD}"
temporary_root="$(mktemp -d /tmp/gdia-decky-install.XXXXXX)"

cleanup() {
    rm -rf -- "${temporary_root}"
}
trap cleanup EXIT

fail() {
    echo "ERROR: $*" >&2
    exit 1
}

if [[ "$(id -u)" -eq 0 ]]; then
    fail "Run this installer as the deck user, not root."
fi
if [[ "${HOME:-}" != "/home/deck" && -z "${GDIA_TEST_MODE:-}" ]]; then
    fail "This installer supports the deck user on SteamOS."
fi

required_commands=(python3 sha256sum)
if [[ -z "${GDIA_TEST_MODE:-}" ]]; then
    required_commands+=(curl sudo)
fi
for command in "${required_commands[@]}"; do
    command -v "${command}" >/dev/null || fail "Missing required command: ${command}"
done

if [[ -z "${GDIA_TEST_MODE:-}" ]] && \
    (pgrep -x "IAGrim.exe" >/dev/null 2>&1 || pgrep -x "Grim Dawn.exe" >/dev/null 2>&1); then
    fail "Close Grim Dawn and Item Assistant before installing."
fi
[[ -f "${iagd_dir}/IAGrim.dll" ]] || fail "Item Assistant was not found at ${iagd_dir}"
[[ -d "${plugin_parent}" ]] || fail "Decky Loader was not found at ${plugin_parent}"

assets=(
    "decky-grim-dawn-item-assistant.zip"
    "iagd-decky-bridge.zip"
    "SHA256SUMS"
)
for asset in "${assets[@]}"; do
    echo "Downloading ${asset}"
    if [[ -n "${GDIA_TEST_MODE:-}" ]]; then
        install -m 0600 "${release_base}/${asset}" "${temporary_root}/${asset}"
    else
        curl --proto '=https' --tlsv1.2 --fail --location --silent --show-error \
            --retry 3 --output "${temporary_root}/${asset}" \
            "${release_base}/${asset}"
    fi
done

verify_asset() {
    local filename="$1"
    local expected
    expected="$(awk -v name="${filename}" '$2 == name { print $1 }' "${temporary_root}/SHA256SUMS")"
    [[ "${expected}" =~ ^[0-9a-f]{64}$ ]] || fail "Missing checksum for ${filename}"
    local actual
    actual="$(sha256sum "${temporary_root}/${filename}" | awk '{ print $1 }')"
    [[ "${actual}" == "${expected}" ]] || fail "Checksum mismatch for ${filename}"
}
verify_asset "decky-grim-dawn-item-assistant.zip"
verify_asset "iagd-decky-bridge.zip"

safe_extract() {
    local archive="$1"
    local destination="$2"
    python3 - "${archive}" "${destination}" <<'PY'
import pathlib
import stat
import sys
import zipfile

archive = pathlib.Path(sys.argv[1])
destination = pathlib.Path(sys.argv[2])
destination.mkdir(parents=True, exist_ok=True)
with zipfile.ZipFile(archive) as source:
    for entry in source.infolist():
        path = pathlib.PurePosixPath(entry.filename)
        mode = entry.external_attr >> 16
        if path.is_absolute() or ".." in path.parts or stat.S_ISLNK(mode):
            raise SystemExit(f"Unsafe archive entry: {entry.filename}")
    source.extractall(destination)
PY
}

safe_extract "${temporary_root}/decky-grim-dawn-item-assistant.zip" \
    "${temporary_root}/plugin"
safe_extract "${temporary_root}/iagd-decky-bridge.zip" \
    "${temporary_root}/bridge"

staged_plugin="${temporary_root}/plugin/${plugin_name}"
staged_dll="${temporary_root}/bridge/IAGrim.dll"
bridge_manifest="${temporary_root}/bridge/bridge-manifest.json"
[[ -f "${staged_plugin}/plugin.json" && -f "${staged_plugin}/main.py" && -f "${staged_plugin}/dist/index.js" ]] \
    || fail "Plugin archive is incomplete"
[[ -f "${staged_dll}" && -f "${bridge_manifest}" ]] \
    || fail "Bridge archive is incomplete"

readarray -t bridge_hashes < <(python3 - "${bridge_manifest}" <<'PY'
import json
import re
import sys

with open(sys.argv[1], encoding="utf-8") as handle:
    manifest = json.load(handle)
if manifest.get("bridgeVersion") != 1 or manifest.get("itemAssistantVersion") != "1.5.9700.13021":
    raise SystemExit("Unsupported bridge manifest")
for key in ("originalDllSha256", "patchedDllSha256"):
    value = manifest.get(key, "")
    if not re.fullmatch(r"[0-9a-f]{64}", value):
        raise SystemExit(f"Invalid {key}")
    print(value)
PY
)
original_hash="${bridge_hashes[0]}"
patched_hash="${bridge_hashes[1]}"
downloaded_dll_hash="$(sha256sum "${staged_dll}" | awk '{ print $1 }')"
[[ "${downloaded_dll_hash}" == "${patched_hash}" ]] \
    || fail "Bridge DLL does not match its manifest"

current_hash="$(sha256sum "${iagd_dir}/IAGrim.dll" | awk '{ print $1 }')"
bridge_changed=false
if [[ "${current_hash}" == "${patched_hash}" ]]; then
    echo "Item Assistant bridge is already installed; skipping."
elif [[ "${current_hash}" == "${original_hash}" ]]; then
    backup="${iagd_dir}/IAGrim.dll.pre-decky"
    if [[ -f "${backup}" ]]; then
        backup_hash="$(sha256sum "${backup}" | awk '{ print $1 }')"
        [[ "${backup_hash}" == "${original_hash}" ]] \
            || fail "Existing Item Assistant backup has an unexpected hash"
    else
        install -m 0644 "${iagd_dir}/IAGrim.dll" "${backup}"
    fi
    install -m 0644 "${staged_dll}" "${iagd_dir}/.IAGrim.dll.decky-new"
    mv -f -- "${iagd_dir}/.IAGrim.dll.decky-new" "${iagd_dir}/IAGrim.dll"
    install -m 0644 "${bridge_manifest}" "${iagd_dir}/decky-bridge-manifest.json"
    bridge_changed=true
    echo "Installed Item Assistant bridge; original saved as ${backup}"
else
    fail "Installed IAGrim.dll is not the verified original or this bridge build; no files were changed."
fi

staged_version="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["version"])' "${staged_plugin}/package.json")"
installed_version=""
if [[ -f "${plugin_target}/package.json" ]]; then
    installed_version="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1])).get("version", ""))' "${plugin_target}/package.json" 2>/dev/null || true)"
fi

plugin_changed=false
if [[ "${installed_version}" == "${staged_version}" ]]; then
    echo "Decky plugin ${staged_version} is already installed; skipping."
else
    run_privileged() {
        if [[ -n "${GDIA_TEST_MODE:-}" ]]; then
            "$@"
        else
            sudo "$@"
        fi
    }
    if [[ -z "${GDIA_TEST_MODE:-}" ]]; then
        sudo -v
    fi
    incoming="${plugin_parent}/.${plugin_name}.installing.$$"
    backup_parent="${plugin_parent}/.backups"
    run_privileged install -d -m 0755 "${incoming}" "${backup_parent}"
    run_privileged cp -a "${staged_plugin}/." "${incoming}/"
    if [[ -z "${GDIA_TEST_MODE:-}" ]]; then
        sudo chown -R root:root "${incoming}"
    fi
    run_privileged find "${incoming}" -type d -exec chmod 0755 '{}' +
    run_privileged find "${incoming}" -type f -exec chmod 0644 '{}' +

    previous=""
    if [[ -e "${plugin_target}" ]]; then
        previous="${backup_parent}/${plugin_name}-$(date -u +%Y%m%dT%H%M%SZ)"
        run_privileged mv -- "${plugin_target}" "${previous}"
    fi
    if ! run_privileged mv -- "${incoming}" "${plugin_target}"; then
        if [[ -n "${previous}" && ! -e "${plugin_target}" ]]; then
            run_privileged mv -- "${previous}" "${plugin_target}"
        fi
        fail "Could not install the Decky plugin"
    fi
    plugin_changed=true
    echo "Installed Decky plugin ${staged_version} at ${plugin_target}"
    if [[ -n "${previous}" ]]; then
        echo "Previous plugin preserved at ${previous}"
    fi
fi

if [[ "${plugin_changed}" == true && -z "${GDIA_SKIP_SERVICE_RESTART:-}" ]]; then
    sudo systemctl restart plugin_loader.service
    echo "Restarted Decky Loader."
fi

if [[ "${bridge_changed}" == false && "${plugin_changed}" == false ]]; then
    echo "Everything is already up to date."
else
    echo "Installation complete. Start Grim Dawn with the combined launcher, then open GD Item Assistant in Quick Access."
fi
