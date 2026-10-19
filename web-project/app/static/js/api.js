const config = window.BudgetTracker;

export async function request(url, options = {}) {
    const method = (options.method || "GET").toUpperCase();
    const headers = new Headers(options.headers || {});

    if (method !== "GET" && method !== "HEAD" && method !== "OPTIONS") {
        headers.set("X-CSRF-Token", config.csrfToken);
    }

    const response = await fetch(url, { ...options, headers });
    let data = null;
    const contentType = response.headers.get("content-type") || "";

    if (contentType.includes("application/json")) {
        data = await response.json();
    } else {
        data = await response.text();
    }

    if (!response.ok) {
        const message = data?.error || `Request failed with status ${response.status}`;
        throw new Error(message);
    }

    return data;
}

export function postJson(url, payload) {
    return request(url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
    });
}

export function fillRoute(template, id) {
    return template.replace(/0$/, String(id));
}
