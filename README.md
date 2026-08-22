# Grim Dawn Item Assistant for Decky

A Steam Deck Quick Access plugin for searching Grim Dawn Item Assistant's
infinite storage and sending a selected item back to Grim Dawn without changing
windows.

## Current status

Version 0.3.1 is a public alpha. The complete transfer path is built and tested
against Item Assistant `1.5.9700.13021`, source commit
`b6f4e6f0fbb8f9b43d92af2f1380ef2a6f8eb1cb`.

The plugin provides:

- name search
- rarity, softcore/hardcore and level filters
- name, level and recently-stored sorting
- paged, controller-focusable results
- compact high-value stat summaries directly in each result row
- a gamepad-aware details modal with categorized computed stats
- local character-level and softcore/hardcore eligibility guidance
- a one-button filter for items the selected character can use
- item-slot filtering
- resistance-gap planning with per-character local values, overcap targets,
  minimum contribution filtering, and best-contribution sorting
- mastery and individual skill-bonus selectors sourced from Grim Dawn's item
  database, with the selected character's masteries identified
- skill, mastery, and granted-item-skill bonuses shown in rows and item details
- direct transfer from the item details modal
- Decky-managed modal placement for compatibility with current Gaming Mode
- status checks for Item Assistant, Grim Dawn and the bridge

## Required companion setup

This plugin extends the setup provided by
[Grim Dawn Item Assistant on Steam Deck](https://github.com/lbr88/grim-dawn-item-assistant-steam-deck).
Use that project's one-click installer first if Item Assistant and the combined
Grim Dawn launcher are not already working. It handles the Proton environment,
Windows dependencies and start order; this repository adds the optional Decky
Quick Access interface and item-transfer bridge.

## Requirements

- SteamOS on Steam Deck
- Decky Loader
- Grim Dawn Steam app `219990`
- Grim Dawn Item Assistant `1.5.9700.13021` installed in Grim Dawn's Proton
  prefix
- the combined Grim Dawn launcher that starts Item Assistant before the game

## Install

Download `Install-GDIA-Decky.desktop` from the latest release to the Steam Deck
Desktop and run it. It downloads, verifies and installs both required pieces:

1. the unprivileged Decky plugin; and
2. the matching Item Assistant bridge assembly.

The installer is idempotent: it skips pieces already at the requested version.
It recognizes only the verified original or a bridge recorded by a valid local
manifest, backs up the original before replacement, and refuses unknown builds.
Plugin files are staged outside Decky's watched plugin directory before an
atomic move into place. Item Assistant and Grim Dawn must be closed for the
first bridge installation or a required bridge upgrade. Plugin-only updates can
proceed while the game is running when the installed bridge is verified and
API-compatible.

## Use

1. In Gaming Mode, launch Grim Dawn using the combined launcher. Item Assistant
   starts first, then Grim Dawn starts in front.
2. Open Quick Access, choose **GD Item Assistant**, and search or filter storage.
3. Optionally choose a local character for level/mode guidance.
4. Use the resistance planner, slot filter, or mastery and skill selectors to
   explain what an item should help with.
5. Choose an item row to see its complete computed stat and skill breakdown.
6. Choose **Send to game**, or press **B** to return to the same results.
7. Open the transfer stash in Grim Dawn to collect the item.

Transfers remain disabled unless Item Assistant, Grim Dawn and bridge version 1
are all detected. A timed-out request is reported as uncertain; refresh the
list before trying the same item again.

## How it works

The Decky backend opens Item Assistant's `userdata.db` through SQLite
`mode=ro` with `query_only` enabled. Searches are parameterized, result and
input sizes are bounded, and sort expressions come from a fixed allowlist.
Computed stats and equipment-slot metadata are read in bounded batches for the
visible result page. The character selector decrypts only the local
`player.gdc` header to read name, level and mode; it does not write character
saves or attempt to assign a subjective universal upgrade score. Resistance
planner values are manually copied from the in-game character sheet and stored
only in Decky's local browser storage. Item contributions are gross values:
replacing equipped gear can remove stats, so the final total must be checked in
Grim Dawn.

Item Assistant does not expose a transfer API. The Wine-only bridge polls a
private directory under Item Assistant's existing data folder for a narrowly
validated `{ playerItemId }` request. It calls Item Assistant's own
`ItemTransferController` on the UI/SQL thread. That preserves its normal stash
file generation, local database update and cloud-deletion sync. The Decky
plugin never writes the database or stash and never reads a cloud token.

## Security properties

- no root Decky backend
- no network listener or localhost server
- no arbitrary command, path or SQL supplied by the frontend
- character saves are read locally with file-size, count and string bounds
- exact process-name and bridge-version validation
- UUID request names, 0600 request files, 0700 bridge directories and atomic
  writes
- 30-second request freshness window and bounded JSON files
- exact Item Assistant version/hash checks with a recoverable backup
- release SHA-256 verification before installation

## Development

```bash
corepack pnpm@9.15.9 install --frozen-lockfile
corepack pnpm@9.15.9 run typecheck
corepack pnpm@9.15.9 run build
python3 -m unittest discover -v
bash scripts/package-release.sh
```

To verify the C# integration, check out the pinned Item Assistant commit and
run:

```bash
bash scripts/apply-item-assistant-bridge.sh /path/to/iagd
dotnet build /path/to/iagd/IAGrim-core.sln -c Release
```

CI performs that build with .NET 10 on Windows. The patch helper refuses a
different commit or a dirty checkout.

## License

This project is MIT licensed. The bridge distribution retains Grim Dawn Item
Assistant's MIT notice; see [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
