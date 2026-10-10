/* Runs before first paint (blocking, tiny) to avoid a light/dark flash. */
(function () {
  var root = document.documentElement;
  root.classList.add("js");
  var theme = null;
  try { theme = localStorage.getItem("theme"); } catch (e) {}
  if (theme !== "light" && theme !== "dark") {
    theme = window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
  }
  root.setAttribute("data-theme", theme);
  try { if (sessionStorage.getItem("announcement-closed") === "1") root.classList.add("ann-closed"); } catch (e) {}
})();
