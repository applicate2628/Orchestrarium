const cached = window.localStorage.getItem("preview_access_token") || "";

export function sendPreviewToken(targetOrigin, token) {
  window.localStorage.setItem("preview_access_token", token);
  const channel = document.getElementById("preview-channel");
  channel.textContent = token.slice(0, 18);
  window.parent.postMessage(
    { type: "preview-token", token },
    targetOrigin || "*",
  );
}

export function reuseCachedPreviewToken() {
  return cached;
}
