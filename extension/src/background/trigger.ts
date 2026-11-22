import type { TriggerMessage } from "../shared/types";

/**
 * Asks the content script in `tabId` to start a check. If the page has no content script yet
 * (page outside the manifest matches), injects it with chrome.scripting (needs activeTab, which
 * the context-menu click or the keyboard shortcut grants) and retries.
 */
export async function triggerTab(tabId: number, selectionText?: string): Promise<boolean> {
  const message: TriggerMessage = { type: "guardian-trigger", selectionText };
  try {
    await chrome.tabs.sendMessage(tabId, message);
    return true;
  } catch {
    // No receiver: the content script is not on this page yet.
  }
  try {
    await chrome.scripting.executeScript({ target: { tabId }, files: ["content.js"] });
    await chrome.tabs.sendMessage(tabId, message);
    return true;
  } catch (err) {
    console.warn("MoMo Guardian: không thể chèn vào trang này", err);
    return false;
  }
}