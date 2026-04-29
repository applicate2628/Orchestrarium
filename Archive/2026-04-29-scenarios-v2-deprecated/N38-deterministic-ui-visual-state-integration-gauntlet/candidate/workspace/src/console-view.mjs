import { activeRecord, visibleCommands } from "./console-state.mjs";

export function renderConsole(state) {
  const record = activeRecord(state);
  const commandHtml = visibleCommands(state)
    .map((command) => `<li id="command-${command.id}">${command.label}</li>`)
    .join("");
  const title = record?.draft?.title || "";
  const slug = record?.draft?.slug || "";

  return `
<section class="incident-console">
  <ul class="command-list">${commandHtml}</ul>
  <nav class="record-tabs">
    ${state.records.map((item) => `<button>${item.label}</button>`).join("")}
  </nav>
  <form class="detail-form">
    <label>Title <input name="title" value="${title}"></label>
    <label>Slug <input name="slug" value="${slug}"></label>
    <button data-action="save">Save</button>
  </form>
  <p>${state.status?.text || ""}</p>
</section>`;
}
