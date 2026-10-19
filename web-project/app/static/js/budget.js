import { fillRoute, postJson } from "./api.js";
import { setStatus, showToast } from "./notifications.js";

const config = window.BudgetTracker;

function parseAmount(text) {
    const value = Number(String(text).replace(/[^0-9.-]/g, ""));
    return Number.isFinite(value) ? value : 0;
}

function formatAmount(value) {
    return Number(value).toLocaleString("en-US", { maximumFractionDigits: 2 });
}

function updateBudget(root, delta) {
    const budgetElement = root.querySelector("#currentBudget");
    const budgetBox = root.querySelector("#budgetBox");
    const current = parseAmount(budgetElement.textContent);
    const next = current + delta;
    budgetElement.textContent = formatAmount(next);
    budgetBox.style.backgroundColor = next < 0 ? "#e74c3c" : "#2ecc71";
}

function escapeHtml(value) {
    return String(value)
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#039;");
}

function transactionHtml(type, id, amount, reason, date) {
    const isIncome = type === "income";
    const editTemplate = isIncome ? config.routes.editIncome : config.routes.editExpense;
    const deleteTemplate = isIncome ? config.routes.deleteIncome : config.routes.deleteExpense;
    const sign = isIncome ? "+" : "-";
    const icon = isIncome ? "💰" : "🛍️";

    return `
        <li class="transaction-item ${isIncome ? "income-item" : "expense-item"}" data-transaction-type="${type}" data-id="${id}">
            <div>
                <strong>${icon} <span class="reason">${escapeHtml(reason)}</span></strong>:
                ${sign}<span class="amount">${formatAmount(amount)}</span> DA
                <br><small>📅 <span class="date">${escapeHtml(date)}</span></small>
            </div>
            <div class="item-actions">
                <a href="${fillRoute(editTemplate, id)}" class="edit-link" aria-label="Edit ${type}">📝</a>
                <a href="${fillRoute(deleteTemplate, id)}" class="delete-link" aria-label="Delete ${type}">❌</a>
            </div>
        </li>`;
}

function resetForm(form) {
    form.reset();
    const firstInput = form.querySelector("input");
    if (firstInput) firstInput.focus();
}

function initTransactionForms(root) {
    const expenseForm = root.querySelector("#expenseForm");
    const incomeForm = root.querySelector("#incomeForm");
    const status = root.querySelector("#statusMsg");

    expenseForm?.addEventListener("submit", async (event) => {
        event.preventDefault();
        const button = expenseForm.querySelector("button");
        const amount = root.querySelector("#amountform").value;
        const reason = root.querySelector("#reasonform").value.trim();
        if (!amount || !reason) return;

        button.disabled = true;
        button.textContent = "Sending…";
        try {
            const result = await postJson(config.routes.addExpense, { amount, reason });
            root.querySelector("#expenseList").insertAdjacentHTML(
                "afterbegin",
                transactionHtml("expense", result.id, amount, reason, result.date),
            );
            updateBudget(root, -Number(amount.replace(/,/g, "")));
            resetForm(expenseForm);
            setStatus(status, result.message);
        } catch (error) {
            setStatus(status, `Server request failed: ${error.message}`, "error");
        } finally {
            button.disabled = false;
            button.textContent = "➕ Add New Expense";
        }
    });

    incomeForm?.addEventListener("submit", async (event) => {
        event.preventDefault();
        const button = incomeForm.querySelector("button");
        const amount = root.querySelector("#incomeform").value;
        const source = root.querySelector("#sourceform").value.trim();
        if (!amount || !source) return;

        button.disabled = true;
        button.textContent = "Sending…";
        try {
            const result = await postJson(config.routes.addIncome, { amount, source });
            root.querySelector("#incomeList").insertAdjacentHTML(
                "afterbegin",
                transactionHtml("income", result.id, amount, source, result.date),
            );
            updateBudget(root, Number(amount.replace(/,/g, "")));
            resetForm(incomeForm);
            setStatus(status, result.message);
        } catch (error) {
            setStatus(status, `Server request failed: ${error.message}`, "error");
        } finally {
            button.disabled = false;
            button.textContent = "💵 Add New Income";
        }
    });
}

function initSearch(root) {
    const input = root.querySelector("#searchInput");
    const list = root.querySelector("#expenseList");
    input?.addEventListener("input", () => {
        const query = input.value.trim().toLowerCase();
        list?.querySelectorAll(".transaction-item").forEach((item) => {
            item.hidden = !item.textContent.toLowerCase().includes(query);
        });
    });
}

function initEditModal(root) {
    const modal = root.querySelector("#editmodal");
    const confirmModal = root.querySelector("#confirmmodal");
    if (!modal || !confirmModal) return;

    const amountInput = root.querySelector("#modalamount");
    const reasonInput = root.querySelector("#modalreason");
    const saveButton = root.querySelector("#savemodalbtn");
    const cancelButton = root.querySelector("#cancelmodalbtn");
    const acceptClose = root.querySelector("#acceptclosebtn");
    const cancelClose = root.querySelector("#cancelclosebtn");

    let currentLink = null;
    let currentItem = null;
    let originalAmount = "";
    let originalReason = "";

    const closeModal = () => { modal.hidden = true; };
    const openModal = () => {
        modal.hidden = false;
        window.setTimeout(() => { amountInput.focus(); amountInput.select(); }, 50);
    };

    const hasChanges = () => amountInput.value !== originalAmount || reasonInput.value !== originalReason;

    const askClose = () => {
        if (!hasChanges()) {
            closeModal();
            return;
        }
        confirmModal.hidden = false;
    };

    root.addEventListener("click", async (event) => {
        const editLink = event.target.closest("a.edit-link");
        if (!editLink) return;
        event.preventDefault();

        currentLink = editLink;
        currentItem = editLink.closest(".transaction-item");
        originalAmount = String(parseAmount(currentItem.querySelector(".amount").textContent));
        originalReason = currentItem.querySelector(".reason").textContent;
        amountInput.value = originalAmount;
        reasonInput.value = originalReason;
        openModal();
    });

    root.addEventListener("click", async (event) => {
        const deleteLink = event.target.closest("a.delete-link");
        if (!deleteLink) return;
        event.preventDefault();
        deleteLink.style.pointerEvents = "none";
        deleteLink.style.opacity = "0.5";

        const item = deleteLink.closest(".transaction-item");
        const isIncome = item.dataset.transactionType === "income";
        const amount = parseAmount(item.querySelector(".amount").textContent);
        try {
            const result = await postJson(deleteLink.href, {});
            item.remove();
            updateBudget(root, isIncome ? -amount : amount);
            showToast(result.message);
        } catch (error) {
            showToast(error.message, "error");
            deleteLink.style.pointerEvents = "auto";
            deleteLink.style.opacity = "1";
        }
    });

    saveButton.addEventListener("click", async () => {
        const amount = amountInput.value.replace(/,/g, "").trim();
        const reason = reasonInput.value.trim();
        if (!amount || !reason || Number.isNaN(Number(amount)) || Number(amount) <= 0) return;

        saveButton.disabled = true;
        const previousText = saveButton.textContent;
        saveButton.textContent = "Saving…";
        try {
            const result = await postJson(currentLink.href, { amount, reason });
            const oldAmount = parseAmount(currentItem.querySelector(".amount").textContent);
            const newAmount = Number(amount);
            const isIncome = currentItem.dataset.transactionType === "income";
            currentItem.querySelector(".amount").textContent = `${isIncome ? "+" : "-"}${formatAmount(newAmount)}`;
            currentItem.querySelector(".reason").textContent = reason;
            currentItem.querySelector(".date").textContent = result.newdate;
            updateBudget(root, isIncome ? newAmount - oldAmount : oldAmount - newAmount);
            closeModal();
            showToast(result.message);
        } catch (error) {
            showToast(error.message, "error");
        } finally {
            saveButton.disabled = false;
            saveButton.textContent = previousText;
        }
    });

    cancelButton.addEventListener("click", askClose);
    acceptClose.addEventListener("click", () => { confirmModal.hidden = true; closeModal(); });
    cancelClose.addEventListener("click", () => { confirmModal.hidden = true; });

    modal.addEventListener("click", (event) => {
        if (event.target === modal) askClose();
    });

    document.addEventListener("keydown", (event) => {
        if (event.key === "Escape" && !modal.hidden) askClose();
    });

    amountInput.addEventListener("input", (event) => {
        const raw = event.target.value.replace(/,/g, "").replace(/[^0-9.]/g, "");
        const parts = raw.split(".");
        const integer = parts.shift() || "";
        event.target.value = parts.length ? `${Number(integer || 0).toLocaleString("en-US")}.${parts.join("")}` : (integer ? Number(integer).toLocaleString("en-US") : "");
    });
}

export function initDashboard(root) {
    if (!root?.querySelector("[data-dashboard]")) return;
    const dashboard = root.querySelector("[data-dashboard]");
    initTransactionForms(dashboard);
    initSearch(dashboard);
    initEditModal(dashboard);
}
