/* Thin fetch wrapper: JSON in/out, CSRF header, timeout, friendly errors. */
export class ApiError extends Error {
  constructor(message, status = 0, data = null) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.data = data;
  }
}

const csrfToken = () => document.querySelector('meta[name="csrf-token"]')?.content || "";

export async function api(url, { method = "GET", body, timeout = 15000, signal } = {}) {
  const controller = new AbortController();
  if (signal) signal.addEventListener("abort", () => controller.abort(), { once: true });
  const timer = setTimeout(() => controller.abort(), timeout);
  const headers = { Accept: "application/json", "X-Requested-With": "fetch" };
  const options = { method, headers, credentials: "same-origin", signal: controller.signal };
  if (method !== "GET") headers["X-CSRFToken"] = csrfToken();
  if (body !== undefined) {
    headers["Content-Type"] = "application/json";
    options.body = JSON.stringify(body);
  }

  let response;
  try {
    response = await fetch(url, options);
  } catch (err) {
    if (err.name === "AbortError" && signal?.aborted) {
      const cancelled = new ApiError("Request cancelled.");
      cancelled.aborted = true;
      throw cancelled;
    }
    throw new ApiError(
      err.name === "AbortError" ? "The request timed out. Please try again." : "Network error. Check your connection.",
    );
  } finally {
    clearTimeout(timer);
  }

  let data = null;
  try { data = await response.json(); } catch (_) { /* non-JSON response */ }

  if (response.status === 401) {
    window.location.href = `/login?next=${encodeURIComponent(location.pathname + location.search)}`;
    throw new ApiError("Please log in to continue.", 401, data);
  }
  if (!response.ok || (data && data.ok === false)) {
    throw new ApiError((data && data.error) || "Something went wrong. Please try again.", response.status, data);
  }
  return data;
}

export const get = (url, opts) => api(url, { ...opts, method: "GET" });
export const post = (url, body, opts) => api(url, { ...opts, method: "POST", body });
export const patch = (url, body, opts) => api(url, { ...opts, method: "PATCH", body });
export const del = (url, opts) => api(url, { ...opts, method: "DELETE" });
