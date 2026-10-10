/* Cart behaviour: add-to-cart buttons everywhere + the interactive cart page. */
import { del, get, patch, post } from "./api.js";
import { confirmDialog, showToast, updateBadge } from "./ui.js";

/* ---------- add to cart / buy now ---------- */
function quantityFor(button) {
  // On the product page the stepper decides the quantity; cards always add 1.
  if (button.closest("[data-buy-box], [data-sticky-buy]")) {
    const input = document.querySelector("[data-buy-box] [data-qty-input]");
    if (input) return Math.max(1, Number(input.value) || 1);
  }
  return 1;
}

async function addToCart(button, redirect) {
  if (button.classList.contains("is-loading")) return;
  button.classList.add("is-loading");
  try {
    const data = await post("/api/cart/add", {
      product_id: Number(button.dataset.productId),
      quantity: quantityFor(button),
    });
    updateBadge("cart", data.cart.count);
    if (redirect) {
      window.location.href = redirect;
      return;
    }
    showToast(data.message, "success");
  } catch (err) {
    showToast(err.message, "error");
  } finally {
    button.classList.remove("is-loading");
  }
}

/* ---------- cart page ---------- */
function initCartPage(page) {
  const timers = new Map();
  const lineOf = (el) => el.closest("[data-item-id]");

  const setText = (selector, text) => {
    const el = page.querySelector(selector);
    if (el) el.textContent = text;
  };

  function applyCart(cart) {
    updateBadge("cart", cart.count);
    const known = new Set([...page.querySelectorAll("[data-item-id]")].map((l) => l.dataset.itemId));
    if (!cart.items.length || cart.items.some((i) => !known.has(String(i.id)))) {
      window.location.reload(); // empty state / new lines are rendered by the server
      return;
    }
    const byId = new Map(cart.items.map((i) => [String(i.id), i]));
    page.querySelectorAll("[data-item-id]").forEach((line) => {
      const item = byId.get(line.dataset.itemId);
      if (!item) { line.remove(); return; }
      line.classList.remove("is-updating");
      const input = line.querySelector("[data-qty-input]");
      input.max = String(item.max_quantity);
      input.value = String(item.quantity);
      line.dataset.qty = String(item.quantity);
      line.querySelector("[data-qty-minus]").disabled = item.quantity <= 1;
      line.querySelector("[data-qty-plus]").disabled = item.quantity >= item.max_quantity;
      line.querySelector("[data-line-total]").textContent = item.line_total_formatted;
      const note = line.querySelector("[data-stock-note]");
      note.textContent = item.stock_note;
      note.hidden = !item.stock_note;
    });

    ["subtotal", "discount", "shipping", "tax", "total"].forEach((key) =>
      setText(`[data-sum="${key}"]`, cart.formatted[key]));
    page.querySelector('[data-row="discount"]')?.toggleAttribute("hidden", cart.discount === 0);
    page.querySelector('[data-row="tax"]')?.toggleAttribute("hidden", cart.tax === 0);
    setText("[data-cart-count]", `${cart.count} item${cart.count === 1 ? "" : "s"}`);

    const bar = page.querySelector("[data-ship-progress]");
    if (bar) {
      bar.max = cart.free_shipping_threshold;
      bar.value = Math.min(cart.subtotal - cart.discount, cart.free_shipping_threshold);
    }
    setText("[data-ship-msg]", cart.free_shipping_remaining > 0
      ? `Add ${cart.free_shipping_remaining_formatted} more for free shipping`
      : "You've unlocked free shipping");
  }

  async function updateLine(line, quantity) {
    const seq = (line._seq = (line._seq || 0) + 1);
    line.classList.add("is-updating");
    try {
      const data = await patch(`/api/cart/items/${line.dataset.itemId}`, { quantity });
      if (seq === line._seq) applyCart(data.cart);
    } catch (err) {
      showToast(err.message, "error");
      if (err.data?.cart) applyCart(err.data.cart);
      else {
        try { applyCart((await get("/api/cart")).cart); } catch (_) { window.location.reload(); }
      }
    }
  }

  // The stepper announces every change; debounce so rapid +/- clicks send one request.
  page.addEventListener("qty:change", (e) => {
    const line = lineOf(e.target);
    if (!line) return;
    const quantity = Number(e.target.value);
    if (quantity === Number(line.dataset.qty)) return;
    clearTimeout(timers.get(line));
    timers.set(line, setTimeout(() => updateLine(line, quantity), 350));
  });

  page.addEventListener("click", async (e) => {
    const removeBtn = e.target.closest("[data-remove-item]");
    if (removeBtn) {
      const line = lineOf(removeBtn);
      line.classList.add("is-updating");
      try {
        const data = await del(`/api/cart/items/${line.dataset.itemId}`);
        showToast("Item removed from your cart.", "success");
        applyCart(data.cart);
      } catch (err) {
        showToast(err.message, "error");
        line.classList.remove("is-updating");
        if (err.data?.cart) applyCart(err.data.cart);
      }
      return;
    }

    if (e.target.closest("[data-clear-cart]")) {
      const ok = await confirmDialog({
        title: "Clear your cart?", message: "All items will be removed from your cart.",
        confirmText: "Clear cart", danger: true,
      });
      if (!ok) return;
      try {
        await del("/api/cart");
        window.location.reload();
      } catch (err) {
        showToast(err.message, "error");
      }
    }
  });
}

export function initCart() {
  document.addEventListener("click", (e) => {
    const add = e.target.closest("[data-add-to-cart]");
    if (add && !add.disabled) return addToCart(add, null);
    const buy = e.target.closest("[data-buy-now]");
    if (buy && !buy.disabled) return addToCart(buy, buy.dataset.redirect || "/cart");
  });
  const page = document.querySelector("[data-cart-page]");
  if (page) initCartPage(page);
}
