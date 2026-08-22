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
  buildBonuses: ItemBuildBonus[];
  matchReasons: string[];
};

type ItemBuildBonus = {
  kind: string;
  name: string;
  masteryId: string;
  value: number;
  displayValue: string;
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

type BuildOptions = {
  masteries: { masteryId: string; name: string }[];
  skills: { name: string; masteryId: string }[];
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
  slot: string;
  resistance: string;
  minimumResistance: number;
  mastery: string;
  skill: string;
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
const getBuildOptions = callable<[], BuildOptions>("get_build_options");

const PAGE_SIZE = 20;
const DEFAULT_FILTERS: SearchFilters = {
  query: "",
  rarity: "all",
  mode: "all",
  minimumLevel: 0,
  maximumLevel: 100,
  sort: "name",
  slot: "all",
  resistance: "all",
  minimumResistance: 1,
  mastery: "all",
  skill: "",
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
  { data: "resistance_desc", label: "Selected resistance: high to low" },
];

const slotOptions = [
  { data: "all", label: "All item slots" },
  { data: "ArmorProtective_Head", label: "Head Armor" },
  { data: "ArmorProtective_Chest", label: "Chest Armor" },
  { data: "ArmorProtective_Legs", label: "Leg Armor" },
  { data: "ArmorProtective_Feet", label: "Boots" },
  { data: "ArmorProtective_Hands", label: "Gloves" },
  { data: "ArmorProtective_Shoulders", label: "Shoulders" },
  { data: "ArmorProtective_Waist", label: "Belt" },
  { data: "ArmorJewelry_Amulet", label: "Amulet" },
  { data: "ArmorJewelry_Ring", label: "Ring" },
  { data: "ArmorJewelry_Medal", label: "Medal" },
  { data: "ItemArtifact", label: "Relic" },
  { data: "ItemEnchantment", label: "Augment / Enchantment" },
  { data: "WeaponArmor_Offhand", label: "Caster Off-hand" },
  { data: "WeaponArmor_Shield", label: "Shield" },
  { data: "WeaponMelee_Sword", label: "One-handed Sword" },
  { data: "WeaponMelee_Sword2h", label: "Two-handed Sword" },
  { data: "WeaponMelee_Mace", label: "One-handed Mace" },
  { data: "WeaponMelee_Mace2h", label: "Two-handed Mace" },
  { data: "WeaponMelee_Axe", label: "One-handed Axe" },
  { data: "WeaponMelee_Axe2h", label: "Two-handed Axe" },
  { data: "WeaponMelee_Dagger", label: "Dagger" },
  { data: "WeaponMelee_Scepter", label: "Scepter" },
  { data: "WeaponMelee_Spear2h", label: "Two-handed Spear" },
  { data: "WeaponHunting_Ranged1h", label: "One-handed Ranged" },
  { data: "WeaponHunting_Ranged2h", label: "Two-handed Ranged" },
];

const resistanceOptions = [
  { data: "all", label: "Any resistance" },
  { data: "fire", label: "Fire" },
  { data: "cold", label: "Cold" },
  { data: "lightning", label: "Lightning" },
  { data: "pierce", label: "Pierce" },
  { data: "poison", label: "Poison & Acid" },
  { data: "bleeding", label: "Bleeding" },
  { data: "vitality", label: "Vitality" },
  { data: "aether", label: "Aether" },
  { data: "chaos", label: "Chaos" },
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

const characterMasteryIds = (className: string) => {
  const suffix = className.replace("tagSkillClassName", "");
  return suffix.match(/.{2}/g)?.map((part) => `class${part}`) ?? [];
};

const RESISTANCE_STORAGE_KEY = "gdia-resistance-profiles-v1";

const loadResistanceProfiles = (): Record<string, Record<string, number>> => {
  try {
    const value = window.localStorage.getItem(RESISTANCE_STORAGE_KEY);
    return value ? JSON.parse(value) : {};
  } catch {
    return {};
  }
};

const ItemSummary = ({ item, character }: { item: InventoryItem; character: CharacterSummary | null }) => (
  <div style={{ lineHeight: 1.45 }}>
    <div>{itemDescription(item)}</div>
    {item.matchReasons.length ? (
      <div style={{ color: "#8ed68e", marginTop: 3 }}>
        Helps: {item.matchReasons.join(" · ")}
      </div>
    ) : null}
    {item.highlights.length ? (
      <div style={{ color: "#c7d5e0", marginTop: 3 }}>
        {item.highlights.map((stat) => stat.displayValue).join(" · ")}
      </div>
    ) : null}
    {item.buildBonuses.length ? (
      <div style={{ color: "#8fb8e8", marginTop: 3 }}>
        {item.buildBonuses.slice(0, 2).map((bonus) => bonus.displayValue).join(" · ")}
        {item.buildBonuses.length > 2 ? ` · +${item.buildBonuses.length - 2} more` : ""}
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
          {details?.item.buildBonuses.length ? (
            <div style={{ marginBottom: 12 }}>
              <div style={{ fontWeight: 700, marginBottom: 4 }}>Skills & masteries</div>
              {details.item.buildBonuses.map((bonus) => (
                <div key={`${bonus.kind}-${bonus.name}`} style={{ lineHeight: 1.45 }}>
                  {bonus.displayValue}
                </div>
              ))}
            </div>
          ) : null}
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
  const [buildOptions, setBuildOptions] = useState<BuildOptions>({
    masteries: [],
    skills: [],
  });
  const [characterId, setCharacterId] = useState("");
  const [resistanceProfiles, setResistanceProfiles] = useState(loadResistanceProfiles);
  const [targetResistance, setTargetResistance] = useState(80);
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
    void getBuildOptions()
      .then(setBuildOptions)
      .catch((error) => console.error("GD Item Assistant build options failed", error));
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
  const selectedCharacterMasteries = new Set(
    characterMasteryIds(selectedCharacter?.className ?? ""),
  );
  const masteryOptions = [
    { data: "all", label: "Any mastery" },
    ...buildOptions.masteries.map((mastery) => ({
      data: mastery.masteryId,
      label: `${mastery.name}${selectedCharacterMasteries.has(mastery.masteryId) ? " · Character mastery" : ""}`,
    })),
  ];
  const skillOptions = [
    { data: "", label: "Any skill bonus" },
    ...buildOptions.skills
      .filter((skill) => filters.mastery !== "all" && skill.masteryId === filters.mastery)
      .map((skill) => ({ data: skill.name, label: skill.name })),
  ];
  const resistanceProfileId = characterId || "manual";
  const currentResistance = filters.resistance === "all"
    ? 0
    : resistanceProfiles[resistanceProfileId]?.[filters.resistance] ?? 0;
  const resistanceGap = Math.max(0, targetResistance - currentResistance);
  const selectedResistanceLabel = resistanceOptions.find(
    (option) => option.data === filters.resistance,
  )?.label ?? "Resistance";

  const updateCurrentResistance = (value: number) => {
    if (filters.resistance === "all") return;
    setResistanceProfiles((current) => {
      const next = {
        ...current,
        [resistanceProfileId]: {
          ...(current[resistanceProfileId] ?? {}),
          [filters.resistance]: value,
        },
      };
      try {
        window.localStorage.setItem(RESISTANCE_STORAGE_KEY, JSON.stringify(next));
      } catch {
        // Session-only guidance still works when storage is unavailable.
      }
      return next;
    });
  };

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

  const findResistanceFixes = () => {
    if (filters.resistance === "all") return;
    const overrides: Partial<SearchFilters> = {
      minimumResistance: Math.max(1, resistanceGap),
      sort: "resistance_desc",
    };
    setFilters((current) => ({ ...current, ...overrides, offset: 0 }));
    void runSearch(0, false, overrides);
  };

  const showItemDetails = (item: InventoryItem) => {
    showModal(
      <ItemDetailsModal
        item={item}
        canTransfer={canTransfer}
        character={selectedCharacter}
        onTransfer={sendItem}
      />,
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
              Level, mode, and masteries are read locally. Resistance values you enter are saved only in Decky's local browser storage; character saves are never modified.
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

      <PanelSection title="Resistance planner">
        <PanelSectionRow>
          <DropdownItem
            label="Resistance to improve"
            rgOptions={resistanceOptions}
            selectedOption={filters.resistance}
            onChange={(option) => {
              const resistance = String(option.data);
              setFilters((current) => ({
                ...current,
                resistance,
                minimumResistance: 1,
                sort: resistance === "all" && current.sort === "resistance_desc"
                  ? "name"
                  : current.sort,
              }));
            }}
          />
        </PanelSectionRow>
        {filters.resistance !== "all" ? (
          <>
            <PanelSectionRow>
              <SliderField
                label={`Current ${selectedResistanceLabel}`}
                value={currentResistance}
                min={-50}
                max={100}
                step={1}
                showValue
                editableValue
                onChange={updateCurrentResistance}
              />
            </PanelSectionRow>
            <PanelSectionRow>
              <SliderField
                label="Desired total (includes overcap)"
                value={targetResistance}
                min={80}
                max={120}
                step={5}
                showValue
                editableValue
                onChange={setTargetResistance}
              />
            </PanelSectionRow>
            <PanelSectionRow>
              <div style={{ width: "100%", lineHeight: 1.45 }}>
                <strong>
                  {resistanceGap > 0
                    ? `${resistanceGap}% ${selectedResistanceLabel} Resistance needed`
                    : `${selectedResistanceLabel} target reached`}
                </strong>
                <div style={{ opacity: 0.72, marginTop: 3 }}>
                  Results show gross resistance on the stored item. Replacing equipped gear can remove some resistance, so verify the final total in Grim Dawn.
                </div>
              </div>
            </PanelSectionRow>
            <PanelSectionRow>
              <SliderField
                label="Minimum item contribution"
                value={filters.minimumResistance}
                min={1}
                max={200}
                step={1}
                showValue
                editableValue
                onChange={(minimumResistance) =>
                  setFilters((current) => ({ ...current, minimumResistance }))
                }
              />
            </PanelSectionRow>
            <PanelSectionRow>
              <ButtonItem layout="below" disabled={busy} onClick={findResistanceFixes}>
                Find items that can cover this gap
              </ButtonItem>
            </PanelSectionRow>
          </>
        ) : (
          <PanelSectionRow>
            <div style={{ opacity: 0.72 }}>
              Choose a resistance, enter the value shown on your character sheet, and set the desired overcap.
            </div>
          </PanelSectionRow>
        )}
      </PanelSection>

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
            label="Item slot"
            rgOptions={slotOptions}
            selectedOption={filters.slot}
            onChange={(option) =>
              setFilters((current) => ({
                ...current,
                slot: String(option.data),
              }))
            }
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
            label="Mastery bonuses"
            rgOptions={masteryOptions}
            selectedOption={filters.mastery}
            onChange={(option) =>
              setFilters((current) => ({
                ...current,
                mastery: String(option.data),
                skill: "",
              }))
            }
          />
        </PanelSectionRow>
        {filters.mastery !== "all" ? (
          <PanelSectionRow>
            <DropdownItem
              label="Specific skill bonus"
              rgOptions={skillOptions}
              selectedOption={filters.skill}
              onChange={(option) =>
                setFilters((current) => ({
                  ...current,
                  skill: String(option.data),
                }))
              }
            />
          </PanelSectionRow>
        ) : null}
        <PanelSectionRow>
          <DropdownItem
            label="Sort by"
            rgOptions={sortOptions.filter(
              (option) => option.data !== "resistance_desc" || filters.resistance !== "all",
            )}
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
              onClick={() => showItemDetails(item)}
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
