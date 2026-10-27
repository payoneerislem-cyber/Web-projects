/* Checkout: progressive multi-step form. Without JS every step is visible and the form still works. */
const form = document.querySelector("[data-checkout]");

if (form) {
  const steps = [...form.querySelectorAll("[data-step]")];
  const NEW_ADDRESS_FIELDS = ["line1", "city", "postal_code", "country"];
  const $ = (selector, root = form) => root.querySelector(selector);
  const checked = (name) => form.querySelector(`input[name="${name}"]:checked`);
  const val = (name) => (form.elements[name]?.value || "").trim();

  const summaries = {
    contact: () => `${val("full_name")} · ${val("email")}`,
    address: () => {
      const choice = checked("address_id");
      return choice && choice.value !== "new"
        ? choice.dataset.addressSummary
        : [val("line1"), val("city")].filter(Boolean).join(", ");
    },
    shipping: () => {
      const r = checked("shipping_method");
      return r ? `${r.dataset.label} · ${r.dataset.shipping}` : "";
    },
    payment: () => checked("payment_method")?.dataset.label || "",
  };

  function setState(step, state) {
    step.dataset.state = state;
    const open = state === "open";
    $("[data-step-body]", step).hidden = !open;
    const summary = $("[data-step-summary]", step);
    const edit = $("[data-step-edit]", step);
    if (summary) { summary.hidden = state !== "done"; summary.textContent = state === "done" ? summaries[step.dataset.step]?.() || "" : ""; }
    if (edit) edit.hidden = state !== "done";
  }

  function open(step, scroll = true) {
    steps.forEach((s) => { if (s !== step) setState(s, s.dataset.state === "done" ? "done" : "todo"); });
    setState(step, "open");
    if (step.dataset.step === "review") fillReview();
    if (scroll) step.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  function valid(step) {
    syncAddressMode();
    for (const el of step.querySelectorAll("input, select, textarea")) {
      if (el.disabled || el.closest("[hidden]")) continue;
      if (!el.checkValidity()) { el.reportValidity(); el.focus(); return false; }
    }
    return true;
  }

  function fillReview() {
    const review = $("[data-review]");
    review.replaceChildren();
    for (const [label, key] of [["Contact", "contact"], ["Ship to", "address"], ["Delivery", "shipping"], ["Payment", "payment"]]) {
      const dt = document.createElement("dt"); dt.textContent = label;
      const dd = document.createElement("dd"); dd.textContent = summaries[key]();
      review.append(dt, dd);
    }
  }

  /* Address: saved address vs. new address fields */
  function syncAddressMode() {
    const choice = checked("address_id") || $('input[name="address_id"][type="hidden"]');
    const isNew = !choice || choice.value === "new";
    const box = $("[data-new-address]");
    if (box) box.hidden = !isNew;
    NEW_ADDRESS_FIELDS.forEach((name) => { if (form.elements[name]) form.elements[name].required = isNew; });
  }

  /* Sidebar totals follow the chosen delivery method */
  function syncShipping() {
    const r = checked("shipping_method");
    if (!r) return;
    document.querySelectorAll('[data-sum="shipping"]').forEach((el) => { el.textContent = r.dataset.shipping; });
    document.querySelectorAll('[data-sum="total"]').forEach((el) => { el.textContent = r.dataset.total; });
  }

  function syncPayment() {
    const block = $("[data-demo-block]");
    if (block) block.hidden = !checked("payment_method")?.hasAttribute("data-test-mode");
  }

  form.addEventListener("change", (e) => {
    if (e.target.name === "address_id") syncAddressMode();
    if (e.target.name === "shipping_method") syncShipping();
    if (e.target.name === "payment_method") syncPayment();
  });

  steps.forEach((step, i) => {
    $("[data-step-next]", step)?.addEventListener("click", () => {
      if (!valid(step)) return;
      setState(step, "done");
      open(steps[i + 1]);
    });
    $("[data-step-edit]", step)?.addEventListener("click", () => open(step));
  });

  form.addEventListener("submit", (e) => {
    for (const step of steps) {
      if (!valid(step)) { e.preventDefault(); open(step); return; }
    }
    const button = $("[data-place-order]");
    if (button.classList.contains("is-loading")) { e.preventDefault(); return; } // no double submit
    button.classList.add("is-loading");
  });

  /* Start: first step, or the first step the server flagged with an error */
  syncAddressMode();
  syncShipping();
  syncPayment();
  const failing = steps.findIndex((s) => s.querySelector(".error"));
  const target = failing === -1 ? 0 : failing;
  steps.forEach((s, i) => setState(s, i < target ? "done" : "todo"));
  open(steps[target], target > 0); // only jump down to a step that has an error
}
