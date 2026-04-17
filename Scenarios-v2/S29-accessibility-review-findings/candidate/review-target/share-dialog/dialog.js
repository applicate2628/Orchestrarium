const dialog = document.querySelector(".share-dialog");
const launcher = document.querySelector(".launcher");
const footerLink = dialog.querySelector(".footer-link");
const toggle = dialog.querySelector("#scope-toggle");

launcher.addEventListener("click", () => {
  dialog.classList.add("is-open");
  footerLink.focus();
});

document.addEventListener("keydown", (event) => {
  if (event.key === "Escape" && dialog.classList.contains("is-open")) {
    dialog.classList.remove("is-open");
    launcher.focus();
  }
});

toggle.addEventListener("click", () => {
  const nextValue = toggle.textContent.trim() === "On" ? "Off" : "On";
  toggle.textContent = nextValue;
});
