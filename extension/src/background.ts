import { handleCheckPort } from "./background/check";
import { triggerTab } from "./background/trigger";
import { CHECK_PORT_NAME } from "./shared/types";

const MENU_ID = "guardian-check-selection";
const MENU_TITLE = "Kiểm tra bằng MoMo Guardian";
const COMMAND_ID = "check-selection";

chrome.runtime.onInstalled.addListener(() => {
  chrome.contextMenus.removeAll(() => {
    chrome.contextMenus.create({ id: MENU_ID, title: MENU_TITLE, contexts: ["selection"] });
  });
});

chrome.runtime.onConnect.addListener((port) => {
  if (port.name === CHECK_PORT_NAME) handleCheckPort(port);
});

chrome.contextMenus.onClicked.addListener((info, tab) => {
  if (info.menuItemId === MENU_ID && tab?.id !== undefined) void triggerTab(tab.id, info.selectionText);
});

chrome.commands.onCommand.addListener((command, tab) => {
  if (command !== COMMAND_ID) return;
  if (tab?.id !== undefined) {
    void triggerTab(tab.id);
    return;
  }
  void chrome.tabs.query({ active: true, currentWindow: true }).then(([active]) => {
    if (active?.id !== undefined) void triggerTab(active.id);
  });
});