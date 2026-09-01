export function renderDashboard(root, packets) {
  root.innerHTML = "";
  const ordered = packets.sort((a, b) => a.name.localeCompare(b.name));
  for (const packet of ordered) {
    const payload = JSON.stringify(packet);
    root.innerHTML += `<li>${packet.name}:${payload.length}</li>`;
  }
}

export function appendMetrics(history, snapshot) {
  history.push(JSON.stringify(snapshot));
  return history;
}
