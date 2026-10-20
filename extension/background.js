/*
 * Кнопка розширення на панелі браузера: на активній вкладці показує / ховає панель «Кодування».
 * Перше натискання вставляє на сторінку файли панелі (дозвіл activeTab — лише на вкладці, де натиснули).
 */
const ext = typeof browser !== "undefined" ? browser : chrome;
const FILES = ["directory.js", "logic.js", "fill.js", "panel.js"];

ext.action.onClicked.addListener(async (tab) => {
  if (!tab || tab.id === undefined) return;
  const target = { tabId: tab.id };
  try {
    const [probe] = await ext.scripting.executeScript({ target, func: () => !!globalThis.__askepCoding });
    if (probe && probe.result) {
      await ext.scripting.executeScript({ target, func: () => globalThis.__askepCoding.toggle() });
    } else {
      await ext.scripting.executeScript({ target, files: FILES });
    }
  } catch (e) {
    // службові сторінки браузера (chrome://, about:) не дозволяють вставляти скрипти
    console.warn("Askep Кодування: не вдалося відкрити панель на цій сторінці —", e && e.message);
  }
});
