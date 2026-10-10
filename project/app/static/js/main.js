/* Global behaviour: theme, header, drawer, dropdowns, toasts, modals, reveal. */
import { initCart } from "./cart.js";
import { initWishlist } from "./wishlist.js";
import { initSearchSuggest } from "./search.js";
import { confirmDialog, initCounters, initFlashToasts, initModals, initQuantityInputs, initReveal, showToast } from "./ui.js";

const $ = (selector, root = document) => root.querySelector(selector);
const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];

function initTheme() {
  const root = document.documentElement;
  const apply = (theme) => {
    root.setAttribute("data-theme", theme);
    $$("[data-theme-toggle]").forEach((btn) => {
      btn.setAttribute("aria-pressed", String(theme === "dark"));
      btn.setAttribute("aria-label", theme === "dark" ? "Switch to light mode" : "Switch to dark mode");
    });
    $('meta[name="theme-color"]')?.setAttribute("content", theme === "dark" ? "#0c0a09" : "#ffffff");
  };
  apply(root.getAttribute("data-theme") || "light");

  $$("[data-theme-toggle]").forEach((btn) =>
    btn.addEventListener("click", () => {
      const next = root.getAttribute("data-theme") === "dark" ? "light" : "dark";
      apply(next);
      try { localStorage.setItem("theme", next); } catch (_) { /* private mode */ }
    }));

  window.matchMedia("(prefers-color-scheme: dark)").addEventListener?.("change", (e) => {
    let stored = null;
    try { stored = localStorage.getItem("theme"); } catch (_) {}
    if (!stored) apply(e.matches ? "dark" : "light");
  });
}

function initHeader() {
  const header = $("#site-header");
  if (!header) return;
  const onScroll = () => header.classList.toggle("is-scrolled", window.scrollY > 8);
  window.addEventListener("scroll", onScroll, { passive: true });
  onScroll();
}

function initDrawer() {
  const drawer = $("#mobile-drawer");
  if (!drawer) return;
  const opener = $("[data-drawer-open]");
  let lastFocus = null;

  const open = () => {
    lastFocus = document.activeElement;
    drawer.classList.add("is-open");
    drawer.setAttribute("aria-hidden", "false");
    opener?.setAttribute("aria-expanded", "true");
    document.body.classList.add("no-scroll");
    $(".drawer-close", drawer)?.focus();
  };
  const close = () => {
    drawer.classList.remove("is-open");
    drawer.setAttribute("aria-hidden", "true");
    opener?.setAttribute("aria-expanded", "false");
    document.body.classList.remove("no-scroll");
    (lastFocus || opener)?.focus?.();
  };

  opener?.addEventListener("click", open);
  drawer.addEventListener("click", (e) => { if (e.target.closest("[data-drawer-close]")) close(); });
  document.addEventListener("keydown", (e) => {
    if (!drawer.classList.contains("is-open")) return;
    if (e.key === "Escape") return close();
    if (e.key !== "Tab") return;
    const focusable = $$("a[href], button:not([disabled]), input", drawer).filter((el) => el.getClientRects().length);
    if (!focusable.length) return;
    const first = focusable[0], last = focusable[focusable.length - 1];
    if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus(); }
    else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
  });
  window.matchMedia("(min-width: 1024px)").addEventListener?.("change", (e) => {
    if (e.matches && drawer.classList.contains("is-open")) close();
  });
}

function initSearchToggle() {
  const toggle = $("[data-search-toggle]");
  const panel = $("#mobile-search");
  if (!toggle || !panel) return;
  toggle.addEventListener("click", () => {
    const open = panel.classList.toggle("is-open");
    toggle.setAttribute("aria-expanded", String(open));
    if (open) $("input", panel)?.focus();
  });
}

function initDropdowns() {
  const all = $$("details[data-dropdown]");
  document.addEventListener("click", (e) => all.forEach((d) => { if (d.open && !d.contains(e.target)) d.open = false; }));
  document.addEventListener("keydown", (e) => {
    if (e.key !== "Escape") return;
    all.forEach((d) => { if (d.open) { d.open = false; $("summary", d)?.focus(); } });
  });
  all.forEach((d) => d.addEventListener("toggle", () => {
    if (d.open) all.forEach((other) => { if (other !== d) other.open = false; });
  }));
}

function initAnnouncement() {
  $("[data-announcement-close]")?.addEventListener("click", () => {
    document.documentElement.classList.add("ann-closed");
    try { sessionStorage.setItem("announcement-closed", "1"); } catch (_) {}
  });
}

/** Declarative hooks used by the style guide and simple pages. */
function initDataHooks() {
  document.addEventListener("click", async (e) => {
    const toastBtn = e.target.closest("[data-toast]");
    if (toastBtn) return showToast(toastBtn.dataset.toast, toastBtn.dataset.toastType || "info");

    const confirmBtn = e.target.closest("[data-confirm-demo]");
    if (confirmBtn) {
      const ok = await confirmDialog({ title: "Remove item?", message: "This will remove the item from your cart.", confirmText: "Remove", danger: true });
      return showToast(ok ? "Item removed." : "Cancelled.", ok ? "success" : "info");
    }

    const loadingBtn = e.target.closest("[data-demo-loading]");
    if (loadingBtn) {
      loadingBtn.classList.add("is-loading");
      setTimeout(() => loadingBtn.classList.remove("is-loading"), 1500);
    }
  });
}

initTheme();
initHeader();
initDrawer();
initSearchToggle();
initDropdowns();
initAnnouncement();
initModals();
initFlashToasts();
initReveal();
initDataHooks();
initSearchSuggest();
initCart();
initWishlist();
initQuantityInputs();
initCounters();

// <select data-autosubmit> submits its form when changed (sorting etc.)
document.addEventListener("change", (e) => {
  if (e.target.matches?.("[data-autosubmit]")) e.target.form?.requestSubmit();
});
