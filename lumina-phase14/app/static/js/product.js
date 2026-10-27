/* Product page: gallery, hover zoom, lightbox, sticky mobile buy bar. */
import { openModal } from "./ui.js";

const gallery = document.querySelector("[data-gallery]");
if (gallery) {
  const frame = gallery.querySelector("[data-gallery-main]");
  const main = frame?.querySelector("img");
  const thumbs = [...gallery.querySelectorAll("[data-thumb]")];

  const select = (thumb) => {
    if (!main) return;
    main.src = thumb.dataset.src;
    main.alt = thumb.dataset.alt || "";
    thumbs.forEach((t) => t.setAttribute("aria-current", String(t === thumb)));
  };
  thumbs.forEach((t, i) => {
    t.addEventListener("click", () => select(t));
    t.addEventListener("keydown", (e) => {
      const next = e.key === "ArrowRight" ? i + 1 : e.key === "ArrowLeft" ? i - 1 : null;
      if (next === null || !thumbs[next]) return;
      e.preventDefault();
      thumbs[next].focus();
      select(thumbs[next]);
    });
  });

  if (frame && main) {
    frame.addEventListener("mousemove", (e) => {
      const r = frame.getBoundingClientRect();
      main.style.transformOrigin = `${((e.clientX - r.left) / r.width) * 100}% ${((e.clientY - r.top) / r.height) * 100}%`;
    });
    frame.addEventListener("mouseleave", () => { main.style.transformOrigin = "center"; });
    frame.addEventListener("click", () => {
      const dialog = document.getElementById("lightbox");
      const big = dialog?.querySelector("img");
      if (!big) return;
      big.src = main.src;
      big.alt = main.alt;
      openModal(dialog);
    });
  }
}

const buyBox = document.querySelector("[data-buy-box]");
const bar = document.querySelector("[data-sticky-buy]");
if (buyBox && bar && "IntersectionObserver" in window) {
  new IntersectionObserver(([entry]) => {
    // show the bar only once the main buy box has scrolled up out of view
    bar.classList.toggle("is-visible", !entry.isIntersecting && entry.boundingClientRect.top < 0);
  }).observe(buyBox);
}
