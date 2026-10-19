import { initDashboard } from "./budget.js";
import { initNavigation } from "./navigation.js";

function boot() {
    initNavigation();
    initDashboard(document);
}

document.addEventListener("DOMContentLoaded", boot);
