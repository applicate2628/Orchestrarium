export function completeShare(dialog) {
  dialog.querySelector("#status").textContent = "Done";
  dialog.close();
}

export function toggleMore(dialog) {
  const details = dialog.querySelector("#more-panel");
  details.hidden = !details.hidden;
}
