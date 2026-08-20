import {
  ButtonItem,
  DropdownItem,
  PanelSection,
  PanelSectionRow,
  SliderField,
  TextField,
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
    item.hardcore ? "Hardcore" : "Softcore",
  ];
  if (item.stackCount > 1) {
    parts.push(`Stack ${item.stackCount}`);
  }
  if (item.mod) {
    parts.push(item.mod);
  }
  return parts.join(" · ");
};

function Content() {
  const [status, setStatus] = useState<PluginStatus | null>(null);
  const [filters, setFilters] = useState<SearchFilters>(DEFAULT_FILTERS);
  const [results, setResults] = useState<SearchResult | null>(null);
  const [selected, setSelected] = useState<InventoryItem | null>(null);
  const [busy, setBusy] = useState(false);

  const refreshStatus = useCallback(async () => {
    try {
      setStatus(await getStatus());
    } catch (error) {
      console.error("GD Item Assistant status failed", error);
    }
  }, []);

  const runSearch = useCallback(
    async (offset = 0, append = false) => {
      setBusy(true);
      try {
        const next = await searchItems({ ...filters, offset, limit: PAGE_SIZE });
        if (next.error) {
          toaster.toast({ title: "GD Item Assistant", body: next.error });
        }
        setResults((current) =>
          append && current
            ? { ...next, items: [...current.items, ...next.items] }
            : next,
        );
        if (!append) {
          setSelected(null);
        }
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
    const timer = window.setInterval(() => void refreshStatus(), 5000);
    return () => window.clearInterval(timer);
  }, []);

  const sendSelected = async () => {
    if (!selected) {
      return;
    }
    setBusy(true);
    try {
      const result = await transferItem(selected.playerItemId);
      toaster.toast({ title: selected.name, body: result.message });
      await refreshStatus();
      if (result.ok) {
        setSelected(null);
        await runSearch();
      }
    } catch (error) {
      console.error("GD Item Assistant transfer failed", error);
      toaster.toast({
        title: selected.name,
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

      <PanelSection title="Find an item">
        <PanelSectionRow>
          <TextField
            label="Name contains"
            value={filters.query}
            bShowClearAction
            onChange={(event) =>
              setFilters((current) => ({
                ...current,
                query: event.currentTarget.value,
              }))
            }
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

      {selected ? (
        <PanelSection title="Selected item">
          <PanelSectionRow>
            <div style={{ width: "100%", lineHeight: 1.45 }}>
              <strong style={{ color: rarityColor(selected.rarity) }}>
                {selected.name}
              </strong>
              <div style={{ opacity: 0.72 }}>{itemDescription(selected)}</div>
            </div>
          </PanelSectionRow>
          <PanelSectionRow>
            <ButtonItem
              layout="below"
              disabled={busy || !canTransfer}
              onClick={() => void sendSelected()}
            >
              Send selected item to game
            </ButtonItem>
          </PanelSectionRow>
          {!canTransfer ? (
            <PanelSectionRow>
              <div style={{ opacity: 0.72 }}>
                Start Grim Dawn with the combined launcher before transferring.
              </div>
            </PanelSectionRow>
          ) : null}
        </PanelSection>
      ) : null}

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
              description={itemDescription(item)}
              disabled={busy}
              onClick={() => setSelected(item)}
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
