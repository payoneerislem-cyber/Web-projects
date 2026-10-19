import { request } from "./api.js";
import { showToast } from "./notifications.js";
import { initDashboard } from "./budget.js";

const config = window.BudgetTracker;

function showLoading(root) {
    root.innerHTML = `
        <div class="dashboard-card" aria-busy="true">
            <div class="skeleton skeleton-title"></div>
            <div class="skeleton skeleton-panel"></div>
        </div>`;
}

function isInternalPage(url) {
    return url === "/budget" || url === "/change_password";
}

export async function loadPage(targetUrl, { pushState = true } = {}) {
    if (!isInternalPage(targetUrl)) {
        window.location.assign(targetUrl);
        return;
    }

    const root = document.querySelector("#app");
    if (!root) return;

    if (pushState) window.history.pushState({}, "", targetUrl);
    showLoading(root);

    try {
        const result = await request(`${config.routes.pageData}?page=${encodeURIComponent(targetUrl)}`);
        root.innerHTML = result.content;
        initDashboard(root);
    } catch (error) {
        showToast(error.message || "Unable to load page", "error");
        window.location.assign(targetUrl);
    }
}

export function initNavigation() {
    document.addEventListener("click", (event) => {
        const link = event.target.closest("a.nav-link");
        if (!link) return;
        event.preventDefault();
        loadPage(link.getAttribute("href"));
    });

    window.addEventListener("popstate", () => {
        loadPage(window.location.pathname, { pushState: false });
    });
}
