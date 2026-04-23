export function computeLayout(viewport) {
  const width = Math.max(720, viewport.width || 720);
  return {
    boxes: [
      { id: "command-palette", role: "command", x: 24, y: 24, width: 360, height: 260 },
      { id: "record-tabs", role: "tab", x: 24, y: 64, width: 360, height: 44 },
      { id: "detail-form", role: "form", x: 24, y: 96, width: width - 48, height: 320 },
      { id: "raster-preview", role: "preview", x: 480, y: 96, width: 360, height: 240 },
      { id: "save-button", role: "button", x: 40, y: 120, width: 28, height: 24 },
      { id: "discard-button", role: "button", x: 62, y: 120, width: 28, height: 24 }
    ]
  };
}
