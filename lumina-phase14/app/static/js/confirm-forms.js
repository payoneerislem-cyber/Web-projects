/* <form data-confirm="Are you sure?"> asks first (styled dialog), then submits. */
import { confirmDialog } from "./ui.js";

document.addEventListener("submit", async (e) => {
  const form = e.target.closest("form[data-confirm]");
  if (!form || form.dataset.confirmed) return;
  e.preventDefault();
  const ok = await confirmDialog({
    title: "Please confirm", message: form.dataset.confirm, confirmText: "Yes, continue", danger: true,
  });
  if (!ok) return;
  form.dataset.confirmed = "1";
  if (form.requestSubmit) form.requestSubmit(); else form.submit();
});
