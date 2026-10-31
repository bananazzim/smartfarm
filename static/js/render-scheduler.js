// At most one pending frame. A still or hidden scene has no animation loop.
export function createRenderScheduler({draw, requestFrame = requestAnimationFrame, cancelFrame = cancelAnimationFrame}) {
  let pending = null;
  let dirty = false;
  let active = true;
  let disposed = false;
  function schedule() {
    if (!disposed && active && dirty && pending === null) pending = requestFrame(frame);
  }
  function frame() {
    pending = null;
    if (disposed || !active || !dirty) return;
    dirty = false;
    draw();
    schedule();
  }
  return {
    invalidate() { dirty = true; schedule(); },
    setActive(value) {
      active = value;
      if (!active && pending !== null) { cancelFrame(pending); pending = null; }
      if (active) { dirty = true; schedule(); }
    },
    dispose() {
      disposed = true;
      if (pending !== null) cancelFrame(pending);
      pending = null;
    },
  };
}
