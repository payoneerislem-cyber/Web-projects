/* Wishlist hearts everywhere + the wishlist page (remove / move to cart). */
import { post } from "./api.js";
import { showToast, updateBadge } from "./ui.js";

function setPressed(productId, pressed) {
  document.querySelectorAll(`[data-wishlist-toggle][data-product-id="${productId}"]`).forEach((btn) => {
    const name = btn.dataset.name || "this product";
    btn.setAttribute("aria-pressed", String(pressed));
    btn.setAttribute("aria-label", pressed ? `Remove ${name} from wishlist` : `Add ${name} to wishlist`);
  });
}

/** Wishlist page: fade the card out; show the empty state once the last one is gone. */
function removeCard(card, count) {
  card.classList.add("is-removing");
  setTimeout(() => {
    card.remove();
    const label = document.querySelector("[data-wishlist-count]");
    if (label) label.textContent = `${count} item${count === 1 ? "" : "s"}`;
    if (count === 0) window.location.reload();
  }, 250);
}

async function toggle(button) {
  if (button.dataset.busy) return;
  button.dataset.busy = "1";
  try {
    const data = await post("/api/wishlist/toggle", { product_id: Number(button.dataset.productId) });
    setPressed(button.dataset.productId, data.in_wishlist);
    updateBadge("wishlist", data.count);
    showToast(data.message, "success");
    const card = button.closest("[data-wishlist-card]");
    if (card && !data.in_wishlist) removeCard(card, data.count);
  } catch (err) {
    if (err.status !== 401) showToast(err.message, "error"); // 401: api.js sends them to the login page
  } finally {
    delete button.dataset.busy;
  }
}

async function moveToCart(button) {
  if (button.classList.contains("is-loading")) return;
  button.classList.add("is-loading");
  try {
    const data = await post(`/api/wishlist/${button.dataset.productId}/move-to-cart`);
    updateBadge("wishlist", data.count);
    updateBadge("cart", data.cart_count);
    showToast(data.message, "success");
    const card = button.closest("[data-wishlist-card]");
    if (card) removeCard(card, data.count);
  } catch (err) {
    showToast(err.message, "error");
    button.classList.remove("is-loading");
  }
}

export function initWishlist() {
  document.addEventListener("click", (e) => {
    const heart = e.target.closest("[data-wishlist-toggle]");
    if (heart) return toggle(heart);
    const move = e.target.closest("[data-wishlist-move]");
    if (move && !move.disabled) return moveToCart(move);
  });
}
