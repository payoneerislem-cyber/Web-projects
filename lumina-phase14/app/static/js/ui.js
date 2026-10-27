/* Reusable UI primitives: toasts, modals, confirm dialog, badges, scroll reveal. */
const ICONS = {
  success: '<path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/>',
  error: '<circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/>',
  warning: '<circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/>',
  info: '<circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/>',
  close: '<line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>',
};

function svg(name, size, cls) {
  const el = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  for (const [k, v] of Object.entries({
    class: `icon ${cls || ""}`.trim(), width: size, height: size, viewBox: "0 0 24 24", fill: "none",
    stroke: "currentColor", "stroke-width": 2, "stroke-linecap": "round", "stroke-linejoin": "round",
    "aria-hidden": "true", focusable: "false",
  })) el.setAttribute(k, v);
  el.innerHTML = ICONS[name]; // static, trusted strings only
  return el;
}

/* ---------- Toasts ---------- */
const MAX_TOASTS = 4;

function wireToast(toast, duration) {
  const close = () => {
    if (toast.classList.contains("is-out")) return;
    toast.classList.add("is-out");
    setTimeout(() => toast.remove(), 250);
  };
  toast.querySelector(".toast-close")?.addEventListener("click", close);
  if (duration > 0) {
    let timer = setTimeout(close, duration);
    toast.addEventListener("mouseenter", () => clearTimeout(timer));
    toast.addEventListener("mouseleave", () => { timer = setTimeout(close, 1500); });
  }
}

export function showToast(message, type = "info", { duration } = {}) {
  const region = document.getElementById("toast-region");
  if (!region) return;
  const kind = ["success", "error", "warning", "info"].includes(type) ? type : "info";
  const toast = document.createElement("div");
  toast.className = `toast toast-${kind}`;
  toast.setAttribute("role", kind === "error" ? "alert" : "status");

  const text = document.createElement("p");
  text.className = "toast-message";
  text.textContent = message; // textContent: never interpret as HTML

  const close = document.createElement("button");
  close.type = "button";
  close.className = "toast-close";
  close.setAttribute("aria-label", "Dismiss notification");
  close.appendChild(svg("close", 16));

  toast.append(svg(kind, 20, "toast-icon"), text, close);
  region.appendChild(toast);
  while (region.children.length > MAX_TOASTS) region.firstElementChild.remove();
  wireToast(toast, duration ?? (kind === "error" ? 7000 : 4000));
}

/** Server-side flash messages are rendered as toasts in the HTML; make them dismiss. */
export function initFlashToasts() {
  document.querySelectorAll("#toast-region .toast").forEach((t) =>
    wireToast(t, t.classList.contains("toast-error") ? 7000 : 4500));
}

/* ---------- Modals (native <dialog>) ---------- */
export function openModal(target) {
  const dialog = typeof target === "string" ? document.querySelector(target) : target;
  if (dialog && !dialog.open) dialog.showModal();
}

export function initModals() {
  document.addEventListener("click", (e) => {
    const opener = e.target.closest("[data-modal-open]");
    if (opener) return openModal(opener.dataset.modalOpen);
    const closer = e.target.closest("[data-modal-close]");
    if (closer) return closer.closest("dialog")?.close();
    // Click on the backdrop (the <dialog> element itself) closes it.
    if (e.target instanceof HTMLDialogElement && e.target.classList.contains("modal")) e.target.close();
  });
}

/** Promise-based confirmation, e.g. `if (await confirmDialog({danger: true})) ...` */
export function confirmDialog({ title = "Are you sure?", message = "", confirmText = "Confirm", cancelText = "Cancel", danger = false } = {}) {
  return new Promise((resolve) => {
    const id = `confirm-${Date.now()}`;
    const dialog = document.createElement("dialog");
    dialog.className = "modal modal-sm";
    dialog.setAttribute("aria-labelledby", `${id}-title`);

    const panel = document.createElement("div");
    panel.className = "modal-panel";
    const h = document.createElement("h2");
    h.id = `${id}-title`;
    h.textContent = title;
    const p = document.createElement("p");
    p.className = "text-muted";
    p.textContent = message;
    const actions = document.createElement("div");
    actions.className = "modal-actions";
    const cancel = document.createElement("button");
    cancel.type = "button";
    cancel.className = "btn btn-secondary";
    cancel.textContent = cancelText;
    const ok = document.createElement("button");
    ok.type = "button";
    ok.className = `btn ${danger ? "btn-danger" : "btn-primary"}`;
    ok.textContent = confirmText;
    actions.append(cancel, ok);
    panel.append(h, p, actions);
    dialog.appendChild(panel);

    let result = false;
    ok.addEventListener("click", () => { result = true; dialog.close(); });
    cancel.addEventListener("click", () => dialog.close());
    dialog.addEventListener("close", () => { dialog.remove(); resolve(result); });
    document.body.appendChild(dialog);
    dialog.showModal();
    cancel.focus();
  });
}

/* ---------- Header badges ---------- */
export function updateBadge(name, count) {
  const n = Math.max(0, Number(count) || 0);
  document.querySelectorAll(`[data-badge="${name}"]`).forEach((el) => {
    el.textContent = n > 99 ? "99+" : String(n);
    el.hidden = n === 0;
    el.classList.remove("is-bump");
    void el.offsetWidth; // restart animation
    if (n > 0) el.classList.add("is-bump");
  });
}

/* ---------- Scroll reveal ---------- */
export function initReveal() {
  const items = document.querySelectorAll("[data-reveal]");
  const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  if (!("IntersectionObserver" in window) || reduce) {
    items.forEach((el) => el.classList.add("is-visible"));
    return;
  }
  const io = new IntersectionObserver((entries) => {
    entries.forEach((entry) => {
      if (entry.isIntersecting) {
        entry.target.classList.add("is-visible");
        io.unobserve(entry.target);
      }
    });
  }, { threshold: 0.12, rootMargin: "0px 0px -40px 0px" });
  items.forEach((el, i) => {
    el.style.transitionDelay = `${(Number(el.dataset.revealDelay) || (i % 4) * 60)}ms`;
    io.observe(el);
  });
}

/* ---------- Animated counters: <span data-counter="1200">1200</span> ---------- */
export function initCounters() {
  const els = document.querySelectorAll("[data-counter]");
  if (!els.length || !("IntersectionObserver" in window)) return; // keep server-rendered numbers
  const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const fmt = (el, n) => `${n.toLocaleString()}${el.dataset.counterSuffix || ""}`;

  const run = (el) => {
    const target = Number(el.dataset.counter) || 0;
    if (reduce || target === 0) { el.textContent = fmt(el, target); return; }
    const start = performance.now();
    const duration = 1200;
    const tick = (now) => {
      const t = Math.min((now - start) / duration, 1);
      el.textContent = fmt(el, Math.round(target * (1 - Math.pow(1 - t, 3))));
      if (t < 1) requestAnimationFrame(tick);
    };
    requestAnimationFrame(tick);
  };

  const io = new IntersectionObserver((entries) => {
    entries.forEach((entry) => {
      if (entry.isIntersecting) { run(entry.target); io.unobserve(entry.target); }
    });
  }, { threshold: 0.4 });
  els.forEach((el) => { if (!reduce) el.textContent = fmt(el, 0); io.observe(el); });
}

/* ---------- Quantity steppers: <div data-qty> [data-qty-minus] [data-qty-input] [data-qty-plus] ---------- */
export function initQuantityInputs() {
  document.addEventListener("click", (e) => {
    const btn = e.target.closest("[data-qty-minus], [data-qty-plus]");
    if (!btn) return;
    const box = btn.closest("[data-qty]");
    const input = box?.querySelector("[data-qty-input]");
    if (!input) return;
    setQuantity(input, (Number(input.value) || 1) + (btn.hasAttribute("data-qty-plus") ? 1 : -1));
  });
  document.addEventListener("change", (e) => {
    if (e.target.matches("[data-qty-input]")) setQuantity(e.target, Number(e.target.value) || 1);
  });
}

export function setQuantity(input, value) {
  const min = Number(input.min) || 1;
  const max = Number(input.max) || Infinity;
  const next = Math.min(Math.max(Math.round(value), min), max);
  const changed = String(next) !== input.value;
  input.value = String(next);
  const box = input.closest("[data-qty]");
  box?.querySelector("[data-qty-minus]")?.toggleAttribute("disabled", next <= min);
  box?.querySelector("[data-qty-plus]")?.toggleAttribute("disabled", next >= max);
  input.dispatchEvent(new CustomEvent("qty:change", { bubbles: true, detail: { value: next, changed } }));
}
