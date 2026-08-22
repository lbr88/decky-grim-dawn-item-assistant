import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";

const backend = vi.hoisted(() => ({
  getStatus: vi.fn(),
  searchItems: vi.fn(),
  transferItem: vi.fn(),
  getItemDetails: vi.fn(),
  listCharacters: vi.fn(),
  getBuildOptions: vi.fn(),
}));

const modal = vi.hoisted(() => ({
  element: null as ReactNode,
  close: vi.fn(),
}));

vi.mock("@decky/api", () => ({
  callable: (name: string) => ({
    get_status: backend.getStatus,
    search_items: backend.searchItems,
    transfer_item: backend.transferItem,
    get_item_details: backend.getItemDetails,
    list_characters: backend.listCharacters,
    get_build_options: backend.getBuildOptions,
  })[name],
  definePlugin: (factory: () => unknown) => factory(),
  toaster: { toast: vi.fn() },
}));

vi.mock("@decky/ui", async () => {
  const React = await import("react");
  const passthrough = ({ children }: { children?: ReactNode }) => React.createElement("div", null, children);
  return {
    ButtonItem: ({ children, description, ...props }: any) => (
      <button disabled={props.disabled} onClick={props.onClick}>
        {children}
        {description}
      </button>
    ),
    ConfirmModal: (props: any) => (
      <div role="dialog">
        <div>{props.strTitle}</div>
        <div>{props.strDescription}</div>
        <button disabled={props.bOKDisabled} onClick={props.onOK}>
          {props.strOKButtonText}
        </button>
        <button onClick={props.onCancel}>{props.strCancelButtonText}</button>
        <button aria-label="Gamepad cancel" onClick={props.onEscKeypress} />
      </div>
    ),
    DropdownItem: passthrough,
    PanelSection: passthrough,
    PanelSectionRow: passthrough,
    SliderField: passthrough,
    TextField: passthrough,
    showModal: (element: ReactNode) => {
      modal.element = element;
      return { Close: modal.close, Update: vi.fn() };
    },
    staticClasses: { Title: "title" },
  };
});

vi.mock("react-icons/fa", () => ({ FaBoxOpen: () => <span /> }));

const item = {
  playerItemId: 1235,
  name: "Aetherfire Ascended Shoulderplates of the Aether",
  rarity: "Green",
  level: 82,
  hardcore: false,
  mod: "",
  stackCount: 1,
  slot: "Shoulders",
  storedAt: "2026-08-22T00:00:00Z",
  highlights: [],
  buildBonuses: [],
  matchReasons: [],
};

const readyStatus = {
  installed: true,
  databaseReady: true,
  itemCount: 2011,
  itemAssistantRunning: true,
  grimDawnRunning: true,
  bridgeReady: true,
  bridgeVersion: 1,
  message: "Ready to send items to Grim Dawn",
};

beforeEach(() => {
  backend.getStatus.mockResolvedValue(readyStatus);
  backend.searchItems.mockResolvedValue({
    items: [item],
    total: 1,
    offset: 0,
    limit: 20,
    hasMore: false,
  });
  backend.transferItem.mockResolvedValue({
    ok: true,
    message: "Transferred 1 item to Grim Dawn",
    uncertain: false,
  });
  backend.getItemDetails.mockResolvedValue({
    item,
    stats: [
      {
        key: "defensiveAether",
        label: "Aether Resistance",
        value: 59,
        displayValue: "+59% Aether Resistance",
        category: "Defense",
      },
    ],
  });
  backend.listCharacters.mockResolvedValue([]);
  backend.getBuildOptions.mockResolvedValue({ masteries: [], skills: [] });
  modal.element = null;
  modal.close.mockClear();
});

afterEach(() => cleanup());

async function openDetails() {
  const module = await import("../src/index");
  const plugin = module.default as { content: ReactNode };
  const pluginView = render(plugin.content);
  const itemButton = await screen.findByRole("button", { name: new RegExp(item.name) });
  fireEvent.click(itemButton);
  expect(modal.element).not.toBeNull();
  pluginView.unmount();
  render(modal.element);
  await screen.findByText("+59% Aether Resistance");
}

describe("item details actions", () => {
  test("Send to game is enabled and invokes the real transfer action when status is ready", async () => {
    await openDetails();

    const send = screen.getByRole("button", { name: "Send to game" });
    expect((send as HTMLButtonElement).disabled).toBe(false);
    fireEvent.click(send);

    await waitFor(() => expect(backend.transferItem).toHaveBeenCalledWith(item.playerItemId));
  });

  test("Send stays available and shows the last failed readiness check", async () => {
    backend.getStatus.mockResolvedValue({
      ...readyStatus,
      bridgeReady: false,
      message: "Item Assistant is running without the Decky bridge",
    });
    await openDetails();

    const send = screen.getByRole("button", { name: "Send to game" });
    expect((send as HTMLButtonElement).disabled).toBe(false);
    expect(screen.getByRole("dialog").textContent).toContain(
      "Item Assistant is running without the Decky bridge",
    );
  });

  test("Back closes the details window", async () => {
    await openDetails();

    fireEvent.click(screen.getByRole("button", { name: "Back" }));

    expect(modal.close).toHaveBeenCalledTimes(1);
  });

  test("gamepad cancel closes the details window", async () => {
    await openDetails();

    fireEvent.click(screen.getByRole("button", { name: "Gamepad cancel" }));

    expect(modal.close).toHaveBeenCalledTimes(1);
  });
});
