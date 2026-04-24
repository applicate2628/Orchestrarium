const PALETTE = {
  "-1": [147, 197, 253],
  "0": [248, 250, 252],
  "1": [252, 165, 165],
  "2": [220, 38, 38]
};

function hexToRgb(value) {
  const clean = value.replace("#", "");
  return [
    Number.parseInt(clean.slice(0, 2), 16),
    Number.parseInt(clean.slice(2, 4), 16),
    Number.parseInt(clean.slice(4, 6), 16)
  ];
}

function fillRect(frame, left, top, width, height, color) {
  for (let y = top; y < top + height && y < frame.length; y += 1) {
    for (let x = left; x < left + width && x < frame[y].length; x += 1) {
      frame[y][x] = [...color];
    }
  }
}

export function renderRaster(spec) {
  const background = hexToRgb(spec.background || "#111318");
  const frame = Array.from({ length: spec.height }, () =>
    Array.from({ length: spec.width }, () => [...background])
  );
  const { x, y, cell, gap } = spec.grid;
  spec.values.forEach((row, rowIndex) => {
    row.forEach((value, columnIndex) => {
      const left = x + columnIndex * (cell + gap);
      const top = y + rowIndex * (cell + gap);
      const color = PALETTE[String(value ?? 0)];
      fillRect(frame, left, top, cell, cell, color);
    });
  });
  const selectedLeft = x + spec.selected.col * (cell + gap);
  const selectedTop = y + spec.selected.row * (cell + gap);
  fillRect(frame, selectedLeft, selectedTop, cell, cell, [250, 204, 21]);
  spec.legend.values.slice().reverse().forEach((value, index) => {
    fillRect(frame, spec.legend.x, spec.legend.y + index, spec.legend.width, 1, PALETTE[String(value)]);
  });
  return frame;
}

export function exportPpm(frame) {
  return frame.flat().map((pixel) => pixel.join(" ")).join("\n");
}
