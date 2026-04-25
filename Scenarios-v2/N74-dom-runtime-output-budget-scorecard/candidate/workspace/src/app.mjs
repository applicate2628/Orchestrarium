import { createState, saveChanges, setFilter, toggleDirty } from "./state.mjs";
import { renderInto } from "./view.mjs";

export function mountBoard(root, items) {
  const state = createState(items);
  const render = () => {
    renderInto(root, state, {
      onFilter(filter) {
        setFilter(state, filter);
        render();
      },
      onToggle(id) {
        toggleDirty(state, id);
        render();
      },
      onSave() {
        saveChanges(state);
        render();
      }
    });
  };
  render();
  return { state, rerender: render };
}
