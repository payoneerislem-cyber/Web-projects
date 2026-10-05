/* Shop filters: mobile bottom sheet, tidy URLs, auto-submitting sort. */
const sheet = document.getElementById("filters");
const overlay = document.querySelector(".filters-overlay");
const openers = document.querySelectorAll("[data-filters-open]");
const form = document.getElementById("filters-form");
let lastFocus = null;

function openSheet() {
  lastFocus = document.activeElement;
  sheet.classList.add("is-open");
  overlay?.classList.add("is-open");
  document.body.classList.add("no-scroll");
  openers.forEach((b) => b.setAttribute("aria-expanded", "true"));
  sheet.querySelector("input, button")?.focus();
}

function closeSheet() {
  sheet.classList.remove("is-open");
  overlay?.classList.remove("is-open");
  document.body.classList.remove("no-scroll");
  openers.forEach((b) => b.setAttribute("aria-expanded", "false"));
  lastFocus?.focus?.();
}

if (sheet) {
  openers.forEach((b) => b.addEventListener("click", openSheet));
  document.querySelectorAll("[data-filters-close]").forEach((b) => b.addEventListener("click", closeSheet));
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && sheet.classList.contains("is-open")) closeSheet();
  });
  window.matchMedia("(min-width: 1024px)").addEventListener?.("change", (e) => {
    if (e.matches && sheet.classList.contains("is-open")) closeSheet();
  });
}

if (form) {
  // Keep URLs clean: don't send empty fields.
  form.addEventListener("submit", () => {
    [...form.elements].forEach((el) => {
      if (!el.name) return;
      const choice = el.type === "checkbox" || el.type === "radio";
      if ((!choice || el.checked) && el.value === "") {
        el.disabled = true;
        el.dataset.stripped = "1";
      }
    });
  });
  // Coming back via the browser's back button: re-enable what we disabled.
  window.addEventListener("pageshow", () => {
    document.querySelectorAll("[data-stripped]").forEach((el) => {
      el.disabled = false;
      delete el.dataset.stripped;
    });
  });
}

document.querySelectorAll("[data-autosubmit]").forEach((select) =>
  select.addEventListener("change", () => {
    const f = select.form;
    if (!f) return;
    if (f.requestSubmit) f.requestSubmit(); else f.submit();
  }));
