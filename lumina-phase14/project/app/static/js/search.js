/* Live search suggestions (combobox pattern) for every .search-field in the header. */
import { get } from "./api.js";

const MIN_CHARS = 2;
const DELAY_MS = 220;

function el(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text; // textContent: never parsed as HTML
  return node;
}

export function initSearchSuggest() {
  document.querySelectorAll(".search-field").forEach(setup);
}

function setup(form, index) {
  const input = form.querySelector('input[name="q"]');
  if (!input) return;

  const listId = `suggest-${index}`;
  const box = el("div", "suggest");
  box.id = listId;
  box.setAttribute("role", "listbox");
  box.hidden = true;
  form.appendChild(box);
  input.setAttribute("role", "combobox");
  input.setAttribute("aria-autocomplete", "list");
  input.setAttribute("aria-controls", listId);
  input.setAttribute("aria-expanded", "false");

  let timer = null;
  let controller = null;
  let items = [];
  let active = -1;

  const open = () => { box.hidden = false; input.setAttribute("aria-expanded", "true"); };
  const close = () => {
    box.hidden = true;
    input.setAttribute("aria-expanded", "false");
    input.removeAttribute("aria-activedescendant");
    active = -1;
  };
  const setActive = (i) => {
    items.forEach((node, k) => {
      node.classList.toggle("is-active", k === i);
      node.setAttribute("aria-selected", String(k === i));
    });
    active = i;
    if (i >= 0) {
      input.setAttribute("aria-activedescendant", items[i].id);
      items[i].scrollIntoView({ block: "nearest" });
    } else {
      input.removeAttribute("aria-activedescendant");
    }
  };
  const message = (text) => {
    box.replaceChildren(el("p", "suggest-msg", text));
    items = [];
    active = -1;
    open();
  };

  const render = (data, q) => {
    box.replaceChildren();
    items = [];
    const add = (node) => {
      node.id = `${listId}-${items.length}`;
      node.setAttribute("role", "option");
      node.setAttribute("aria-selected", "false");
      items.push(node);
      box.appendChild(node);
    };
    data.categories.forEach((c) => {
      const a = el("a", "suggest-item suggest-cat");
      a.href = c.url;
      a.append(el("span", "suggest-name", `Category: ${c.name}`));
      add(a);
    });
    data.products.forEach((p) => {
      const a = el("a", "suggest-item");
      a.href = p.url;
      if (p.image) {
        const img = el("img");
        img.src = p.image;
        img.alt = "";
        img.width = 44;
        img.height = 44;
        a.append(img);
      }
      const text = el("span", "suggest-text");
      text.append(el("span", "suggest-name", p.name), el("span", "suggest-meta", `${p.category} · ${p.price}`));
      a.append(text);
      add(a);
    });
    if (!items.length) return message(`No matches for “${q}”`);
    const all = el("a", "suggest-item suggest-all", `See all results for “${q}”`);
    all.href = `${form.action}?q=${encodeURIComponent(q)}`;
    add(all);
    active = -1;
    open();
  };

  const run = async () => {
    const q = input.value.trim();
    if (q.length < MIN_CHARS) return close();
    controller?.abort();
    controller = new AbortController();
    message("Searching…");
    try {
      const data = await get(`/api/search/suggest?q=${encodeURIComponent(q)}`, { signal: controller.signal });
      render(data, q);
    } catch (err) {
      if (!err.aborted) message("Couldn't load suggestions. Press Enter to search.");
    }
  };

  input.addEventListener("input", () => {
    clearTimeout(timer);
    timer = setTimeout(run, DELAY_MS);
  });
  input.addEventListener("focus", () => { if (items.length && input.value.trim().length >= MIN_CHARS) open(); });
  input.addEventListener("keydown", (e) => {
    if (box.hidden || !items.length) return;
    if (e.key === "ArrowDown") { e.preventDefault(); setActive((active + 1) % items.length); }
    else if (e.key === "ArrowUp") { e.preventDefault(); setActive((active - 1 + items.length) % items.length); }
    else if (e.key === "Enter" && active >= 0) { e.preventDefault(); items[active].click(); }
    else if (e.key === "Escape") { close(); }
  });
  form.addEventListener("submit", () => { clearTimeout(timer); controller?.abort(); close(); });
  document.addEventListener("click", (e) => { if (!form.contains(e.target)) close(); });
}
