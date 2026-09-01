import assert from "node:assert/strict";
import { renderEditor } from "../src/editor-panel.mjs";
import {
  activeItem,
  attemptNavigate,
  createEditorState,
  discardActive,
  isDirty,
  saveActive,
  updateField,
} from "../src/editor-state.mjs";

const items = [
  { id: "profile", label: "Profile Settings", fields: { title: "Profile", slug: "profile", summary: "Profile summary" } },
  { id: "billing", label: "Billing Plan", fields: { title: "Billing", slug: "billing", summary: "Billing summary" } },
];

let state = createEditorState(items);
state = updateField(state, "title", "Profile draft");
state = attemptNavigate(state, "billing");
assert.equal(state.activeId, "profile");
assert.equal(isDirty(state, "profile"), true);
assert.equal(state.blockedNavigation.targetId, "billing");

state = updateField(state, "slug", "Bad Slug!");
state = saveActive(state, { ok: true });
assert.equal(isDirty(state, "profile"), true);
assert.ok(activeItem(state).errors.slug);
assert.equal(state.focusId, "field-slug-profile");

state = updateField(state, "slug", "profile-draft");
state = saveActive(state, { ok: false, message: "API rejected" });
assert.equal(isDirty(state, "profile"), true);
assert.equal(state.status.type, "error");

state = discardActive(state);
assert.equal(activeItem(state).draft.title, "Profile");
assert.equal(isDirty(state, "profile"), false);

const html = renderEditor(state);
assert.match(html, /id="status-profile"/);
assert.match(html, /aria-live="polite"/);
assert.match(html, /data-action="save"[^>]+disabled/);
