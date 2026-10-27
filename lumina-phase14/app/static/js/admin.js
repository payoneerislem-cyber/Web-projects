/* Admin dashboard: SVG bar chart drawn from JSON embedded in the page (no chart library). */
const NS = "http://www.w3.org/2000/svg";

function svg(tag, attrs = {}, text) {
  const node = document.createElementNS(NS, tag);
  for (const [key, value] of Object.entries(attrs)) node.setAttribute(key, value);
  if (text !== undefined) node.textContent = text;
  return node;
}

function drawBars(host, series, currency) {
  const money = (cents) => (cents / 100).toLocaleString(undefined, { style: "currency", currency });
  const W = 640, H = 230, pad = { top: 14, bottom: 30 };
  const innerH = H - pad.top - pad.bottom;
  const max = Math.max(1, ...series.map((s) => s.total));
  const slot = W / series.length;
  const barW = Math.min(36, slot * 0.62);

  const chart = svg("svg", { viewBox: `0 0 ${W} ${H}`, width: "100%", role: "presentation", focusable: "false" });
  chart.appendChild(svg("line", { x1: 0, x2: W, y1: H - pad.bottom, y2: H - pad.bottom, class: "chart-axis" }));
  series.forEach((point, i) => {
    const height = Math.max(point.total ? 3 : 0, (point.total / max) * innerH);
    const x = i * slot + (slot - barW) / 2;
    const bar = svg("rect", { x, y: H - pad.bottom - height, width: barW, height, rx: 4, class: "chart-bar" });
    bar.appendChild(svg("title", {}, `${point.label}: ${money(point.total)} (${point.orders} order${point.orders === 1 ? "" : "s"})`));
    chart.appendChild(bar);
    if (i % 2 === 0 || series.length <= 8) {
      chart.appendChild(svg("text", { x: x + barW / 2, y: H - 10, "text-anchor": "middle", class: "chart-label" }, point.label));
    }
  });
  host.replaceChildren(chart);
}

const dataEl = document.getElementById("chart-data");
const host = document.getElementById("sales-chart");
if (dataEl && host) {
  try {
    const data = JSON.parse(dataEl.textContent);
    drawBars(host, data.series, data.currency || "USD");
  } catch (_) {
    host.textContent = "Chart unavailable.";
  }
}
