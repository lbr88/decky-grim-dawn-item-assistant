import {
  ButtonItem,
  ConfirmModal,
  DropdownItem,
  PanelSection,
  PanelSectionRow,
  SliderField,
  TextField,
  showModal,
  staticClasses,
} from "@decky/ui";
import { callable, definePlugin, toaster } from "@decky/api";
import { useCallback, useEffect, useState } from "react";
import { FaBoxOpen } from "react-icons/fa";

type PluginStatus = {
  installed: boolean;
  databaseReady: boolean;
  itemCount: number;
  itemAssistantRunning: boolean;
  grimDawnRunning: boolean;
  bridgeReady: boolean;
  bridgeVersion: number | null;
  message: string;
};

type InventoryItem = {
  playerItemId: number;
  name: string;
  rarity: string;
  level: number;
  hardcore: boolean;
  mod: string;
  stackCount: number;
  slot: string;
  storedAt: string;
  highlights: ItemStat[];
};

type ItemStat = {
  key: string;
  label: string;
  value: number;
  displayValue: string;
  category: string;
};

type ItemDetails = {
  item: InventoryItem;
  stats: ItemStat[];
};

type CharacterSummary = {
  characterId: string;
  name: string;
  level: number;
  hardcore: boolean;
  className: string;
  modifiedAt: string;
};

type SearchResult = {
  items: InventoryItem[];
  total: number;
  offset: number;
  limit: number;
  hasMore: boolean;
  error?: string;
};

type SearchFilters = {
  query: string;
  rarity: string;
  mode: string;
  minimumLevel: number;
  maximumLevel: number;
  sort: string;
  offset: number;
  limit: number;
};

type OperationResult = {
  ok: boolean;
  message: string;
  uncertain: boolean;
};

const getStatus = callable<[], PluginStatus>("get_status");
const searchItems = callable<[SearchFilters], SearchResult>("search_items");
const transferItem = callable<[number], OperationResult>("transfer_item");
const getItemDetails = callable<[number], ItemDetails | null>("get_item_details");
const listCharacters = callable<[], CharacterSummary[]>("list_characters");

const PAGE_SIZE = 20;
const DEFAULT_FILTERS: SearchFilters = {
  query: "",
  rarity: "all",
  mode: "all",
  minimumLevel: 0,
  maximumLevel: 100,
  sort: "name",
  offset: 0,
  limit: PAGE_SIZE,
};

const rarityOptions = [
  { data: "all", label: "All rarities" },
  { data: "Yellow", label: "Rare (yellow)" },
  { data: "Green", label: "Monster infrequent (green)" },
  { data: "Blue", label: "Epic (blue)" },
  { data: "Epic", label: "Legendary (purple)" },
];

const modeOptions = [
  { data: "all", label: "Softcore and hardcore" },
  { data: "softcore", label: "Softcore only" },
  { data: "hardcore", label: "Hardcore only" },
];

const sortOptions = [
  { data: "name", label: "Name" },
  { data: "level_desc", label: "Level: high to low" },
  { data: "level_asc", label: "Level: low to high" },
  { data: "recent", label: "Recently stored" },
];

const rarityColor = (rarity: string) => {
  switch (rarity) {
    case "Yellow":
      return "#f3d35a";
    case "Green":
      return "#70d86f";
    case "Blue":
      return "#72a8ff";
    case "Epic":
      return "#bd83ff";
    default:
      return "inherit";
  }
};

const itemDescription = (item: InventoryItem) => {
  const parts = [
    `Level ${item.level}`,
    item.slot,
    item.hardcore ? "Hardcore" : "Softcore",
  ].filter(Boolean);
  if (item.stackCount > 1) {
    parts.push(`Stack ${item.stackCount}`);
  }
  if (item.mod) {
    parts.push(item.mod);
  }
  return parts.join(" · ");
};

const eligibilityText = (item: InventoryItem, character: CharacterSummary | null) => {
  if (!character) return "";
  if (item.hardcore !== character.hardcore) {
    return `${character.name}: different ${item.hardcore ? "hardcore" : "softcore"} mode`;
  }
  if (item.level <= character.level) {
    return `${character.name} can use this now`;
  }
  return `${character.name} needs ${item.level - character.level} more level${item.level - character.level === 1 ? "" : "s"}`;
};

const ItemSummary = ({ item, character }: { item: InventoryItem; character: CharacterSummary | null }) => (
  <div style={{ lineHeight: 1.45 }}>
    <div>{itemDescription(item)}</div>
    {item.highlights.length ? (
      <div style={{ color: "#c7d5e0", marginTop: 3 }}>
        {item.highlights.map((stat) => stat.displayValue).join(" · ")}
      </div>
    ) : null}
    {character ? (
      <div style={{ color: item.level <= character.level && item.hardcore === character.hardcore ? "#8ed68e" : "#e3b96c", marginTop: 3 }}>
        {eligibilityText(item, character)}
      </div>
    ) : null}
  </div>
);

type ItemDetailsModalProps = {
  item: InventoryItem;
  canTransfer: boolean;
  character: CharacterSummary | null;
  onTransfer: (item: InventoryItem) => Promise<void>;
};

function ItemDetailsModal({ item, canTransfer, character, onTransfer }: ItemDetailsModalProps) {
  const [details, setDetails] = useState<ItemDetails | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let active = true;
    void getItemDetails(item.playerItemId)
      .then((next) => {
        if (active) setDetails(next);
      })
      .catch((error) => console.error("GD Item Assistant details failed", error))
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [item.playerItemId]);

  const grouped = (details?.stats ?? []).reduce<Record<string, ItemStat[]>>(
    (groups, stat) => {
      (groups[stat.category] ??= []).push(stat);
      return groups;
    },
    {},
  );

  return (
    <ConfirmModal
      strTitle={<span style={{ color: rarityColor(item.rarity) }}>{item.name}</span>}
      strDescription={
        <div style={{ maxHeight: "58vh", overflowY: "auto", paddingRight: 8 }}>
          <div style={{ opacity: 0.76, marginBottom: 12 }}>{itemDescription(item)}</div>
          {character ? (
            <div style={{ color: item.level <= character.level && item.hardcore === character.hardcore ? "#8ed68e" : "#e3b96c", marginBottom: 12 }}>
              {eligibilityText(item, character)} (level {character.level})
            </div>
          ) : null}
          {loading ? <div>Loading item stats…</div> : null}
          {!loading && !details ? <div>Item details are no longer available.</div> : null}
          {Object.entries(grouped).map(([category, stats]) => (
            <div key={category} style={{ marginBottom: 12 }}>
              <div style={{ fontWeight: 700, marginBottom: 4 }}>{category}</div>
              {stats.map((stat) => (
                <div key={stat.key} style={{ lineHeight: 1.45 }}>
                  {stat.displayValue}
                </div>
              ))}
            </div>
          ))}
          {details && details.stats.length === 0 ? (
            <div>No computed stats were stored for this item.</div>
          ) : null}
          {!canTransfer ? (
            <div style={{ opacity: 0.72, marginTop: 12 }}>
              Start Grim Dawn with the combined launcher before transferring.
            </div>
          ) : null}
        </div>
      }
      strOKButtonText="Send to game"
      strCancelButtonText="Back"
      bOKDisabled={!canTransfer}
      onOK={() => void onTransfer(item)}
    />
  );
}

function Content() {
  const [status, setStatus] = useState<PluginStatus | null>(null);
  const [filters, setFilters] = useState<SearchFilters>(DEFAULT_FILTERS);
  const [results, setResults] = useState<SearchResult | null>(null);
  const [characters, setCharacters] = useState<CharacterSummary[]>([]);
  const [characterId, setCharacterId] = useState("");
  const [busy, setBusy] = useState(false);

  const refreshStatus = useCallback(async () => {
    try {
      setStatus(await getStatus());
    } catch (error) {
      console.error("GD Item Assistant status failed", error);
    }
  }, []);

  const runSearch = useCallback(
    async (offset = 0, append = false, overrides: Partial<SearchFilters> = {}) => {
      setBusy(true);
      try {
        const next = await searchItems({
          ...filters,
          ...overrides,
          offset,
          limit: PAGE_SIZE,
        });
        if (next.error) {
          toaster.toast({ title: "GD Item Assistant", body: next.error });
        }
        setResults((current) =>
          append && current
            ? { ...next, items: [...current.items, ...next.items] }
            : next,
        );
      } catch (error) {
        console.error("GD Item Assistant search failed", error);
        toaster.toast({
          title: "GD Item Assistant",
          body: "Could not search Item Assistant storage",
        });
      } finally {
        setBusy(false);
      }
    },
    [filters],
  );

  useEffect(() => {
    void refreshStatus();
    void runSearch();
    void listCharacters()
      .then((next) => {
        setCharacters(next);
        setCharacterId((current) => current || next[0]?.characterId || "");
      })
      .catch((error) => console.error("GD Item Assistant character scan failed", error));
    const timer = window.setInterval(() => void refreshStatus(), 5000);
    return () => window.clearInterval(timer);
  }, []);

  const sendItem = async (item: InventoryItem) => {
    setBusy(true);
    try {
      const result = await transferItem(item.playerItemId);
      toaster.toast({ title: item.name, body: result.message });
      await refreshStatus();
      if (result.ok) {
        await runSearch();
      }
    } catch (error) {
      console.error("GD Item Assistant transfer failed", error);
      toaster.toast({
        title: item.name,
        body: "The Item Assistant bridge did not respond",
      });
    } finally {
      setBusy(false);
    }
  };

  const canTransfer =
    status?.bridgeReady === true &&
    status.itemAssistantRunning &&
    status.grimDawnRunning;
  const selectedCharacter = characters.find((character) => character.characterId === characterId) ?? null;

  const showUsableItems = () => {
    if (!selectedCharacter) return;
    const overrides: Partial<SearchFilters> = {
      minimumLevel: 0,
      maximumLevel: selectedCharacter.level,
      mode: selectedCharacter.hardcore ? "hardcore" : "softcore",
    };
    setFilters((current) => ({ ...current, ...overrides, offset: 0 }));
    void runSearch(0, false, overrides);
  };

  const showItemDetails = (item: InventoryItem, parent?: EventTarget | null) => {
    showModal(
      <ItemDetailsModal
        item={item}
        canTransfer={canTransfer}
        character={selectedCharacter}
        onTransfer={sendItem}
      />,
      parent ?? undefined,
      { strTitle: item.name, bHideMainWindowForPopouts: false },
    );
  };

  return (
    <>
      <PanelSection title="Status">
        <PanelSectionRow>
          <div style={{ width: "100%", lineHeight: 1.45 }}>
            <div>{status?.message ?? "Checking Item Assistant…"}</div>
            {status ? (
              <div style={{ opacity: 0.72, marginTop: 4 }}>
                {status.itemCount.toLocaleString()} stored items · Game{" "}
                {status.grimDawnRunning ? "running" : "not running"}
              </div>
            ) : null}
          </div>
        </PanelSectionRow>
        <PanelSectionRow>
          <ButtonItem
            layout="below"
            disabled={busy}
            onClick={() => void refreshStatus()}
          >
            Refresh status
          </ButtonItem>
        </PanelSectionRow>
      </PanelSection>

      {characters.length ? (
        <PanelSection title="Character guidance">
          <PanelSectionRow>
            <DropdownItem
              label="Compare required level with"
              rgOptions={[
                { data: "", label: "No character" },
                ...characters.map((character) => ({
                  data: character.characterId,
                  label: `${character.name} · Level ${character.level}${character.hardcore ? " · Hardcore" : ""}`,
                })),
              ]}
              selectedOption={characterId}
              onChange={(option) => setCharacterId(String(option.data))}
            />
          </PanelSectionRow>
          <PanelSectionRow>
            <div style={{ opacity: 0.72 }}>
              Guidance is read locally from the character save. It checks level and mode; it does not modify the save.
            </div>
          </PanelSectionRow>
          {selectedCharacter ? (
            <PanelSectionRow>
              <ButtonItem layout="below" disabled={busy} onClick={showUsableItems}>
                Show items {selectedCharacter.name} can use
              </ButtonItem>
            </PanelSectionRow>
          ) : null}
        </PanelSection>
      ) : null}

      <PanelSection title="Find an item">
        <PanelSectionRow>
          <TextField
            label="Name contains"
            value={filters.query}
            bShowClearAction
            onChange={(event) => {
              const query = event.currentTarget?.value ??
                (event.target as HTMLInputElement | null)?.value ?? "";
              setFilters((current) => ({
                ...current,
                query,
              }));
            }}
            onKeyDown={(event) => {
              if (event.key === "Enter") {
                void runSearch();
              }
            }}
          />
        </PanelSectionRow>
        <PanelSectionRow>
          <DropdownItem
            label="Rarity"
            rgOptions={rarityOptions}
            selectedOption={filters.rarity}
            onChange={(option) =>
              setFilters((current) => ({
                ...current,
                rarity: String(option.data),
              }))
            }
          />
        </PanelSectionRow>
        <PanelSectionRow>
          <DropdownItem
            label="Character mode"
            rgOptions={modeOptions}
            selectedOption={filters.mode}
            onChange={(option) =>
              setFilters((current) => ({
                ...current,
                mode: String(option.data),
              }))
            }
          />
        </PanelSectionRow>
        <PanelSectionRow>
          <DropdownItem
            label="Sort by"
            rgOptions={sortOptions}
            selectedOption={filters.sort}
            onChange={(option) =>
              setFilters((current) => ({
                ...current,
                sort: String(option.data),
              }))
            }
          />
        </PanelSectionRow>
        <PanelSectionRow>
          <SliderField
            label="Minimum level"
            value={filters.minimumLevel}
            min={0}
            max={100}
            step={5}
            showValue
            editableValue
            onChange={(value) =>
              setFilters((current) => ({
                ...current,
                minimumLevel: Math.min(value, current.maximumLevel),
              }))
            }
          />
        </PanelSectionRow>
        <PanelSectionRow>
          <SliderField
            label="Maximum level"
            value={filters.maximumLevel}
            min={0}
            max={100}
            step={5}
            showValue
            editableValue
            onChange={(value) =>
              setFilters((current) => ({
                ...current,
                maximumLevel: Math.max(value, current.minimumLevel),
              }))
            }
          />
        </PanelSectionRow>
        <PanelSectionRow>
          <ButtonItem
            layout="below"
            disabled={busy || status?.databaseReady !== true}
            onClick={() => void runSearch()}
          >
            Search storage
          </ButtonItem>
        </PanelSectionRow>
      </PanelSection>

      <PanelSection
        title={
          results ? `Stored items (${results.items.length} of ${results.total})` : "Stored items"
        }
        spinner={busy}
      >
        {results?.items.map((item) => (
          <PanelSectionRow key={item.playerItemId}>
            <ButtonItem
              layout="below"
              description={<ItemSummary item={item} character={selectedCharacter} />}
              disabled={busy}
              onClick={(event) => showItemDetails(item, event.currentTarget)}
            >
              <span style={{ color: rarityColor(item.rarity) }}>{item.name}</span>
            </ButtonItem>
          </PanelSectionRow>
        ))}
        {results && results.items.length === 0 ? (
          <PanelSectionRow>
            <div style={{ opacity: 0.72 }}>No matching stored items.</div>
          </PanelSectionRow>
        ) : null}
        {results?.hasMore ? (
          <PanelSectionRow>
            <ButtonItem
              layout="below"
              disabled={busy}
              onClick={() => void runSearch(results.items.length, true)}
            >
              Load more
            </ButtonItem>
          </PanelSectionRow>
        ) : null}
      </PanelSection>
    </>
  );
}

export default definePlugin(() => ({
  name: "GD Item Assistant",
  titleView: <div className={staticClasses.Title}>GD Item Assistant</div>,
  content: <Content />,
  icon: <FaBoxOpen />,
  alwaysRender: true,
  onDismount() {
    console.log("GD Item Assistant plugin unloaded");
  },
}));
