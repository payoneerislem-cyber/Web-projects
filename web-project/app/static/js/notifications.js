export function setStatus(element, message, type = "success") {
    if (!element) return;
    element.textContent = message || "";
    element.style.color = type === "success" ? "#2ecc71" : "#e74c3c";
}

export function showToast(message, type = "success") {
    const toast = document.createElement("div");
    toast.className = `app-toast ${type}`;
    toast.textContent = message;
    toast.style.opacity = "0";
    toast.style.transform = "translateY(16px)";
    document.body.appendChild(toast);

    requestAnimationFrame(() => {
        toast.style.opacity = "1";
        toast.style.transform = "translateY(0)";
    });

    window.setTimeout(() => {
        toast.style.opacity = "0";
        toast.style.transform = "translateY(16px)";
        window.setTimeout(() => toast.remove(), 300);
    }, 3000);
}
