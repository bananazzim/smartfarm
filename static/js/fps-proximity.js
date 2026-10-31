// Distances are world metres, independent of greenhouse size and viewport.
export function isSensorNear(distance, wasNear) {
  return Number.isFinite(distance) && (wasNear ? distance < 3.5 : distance <= 3);
}

export function labelPosition(anchor, size, viewport, occupied) {
  const margin = 8;
  const width = Math.min(size.width, viewport.width - margin * 2);
  const height = size.height;
  const x = Math.max(margin, Math.min(anchor.x - width / 2, viewport.width - width - margin));
  const base = anchor.y - height - 12;
  let best;
  for (const shift of [0, -1, 1, -2, 2, -3, 3]) {
    const y = Math.max(margin, Math.min(base + shift * (height + 6), viewport.height - height - margin));
    const box = {x, y, width, height};
    best ??= box;
    if (!occupied.some(b => x < b.x + b.width + 4 && x + width + 4 > b.x && y < b.y + b.height + 4 && y + height + 4 > b.y)) return box;
  }
  return best;
}
