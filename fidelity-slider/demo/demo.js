/* Demo only: draws the synthetic chart and keeps the caption in step with the slider. */
(function () {
  "use strict";

  // Share of readers still reading at each section of a fictional 3,800-word story.
  var SECTIONS = [
    { name: "Opening", feature: 96, avg: 94 },
    { name: "Section 2", feature: 88, avg: 82 },
    { name: "Section 3", feature: 79, avg: 71 },
    { name: "Section 4", feature: 58, avg: 63 },
    { name: "Section 5", feature: 52, avg: 55 },
    { name: "Section 6", feature: 47, avg: 48 },
    { name: "Ending", feature: 41, avg: 40 },
  ];
  var DROP = 3; // index of the largest drop-off

  function drawChart(host) {
    var W = 640,
      H = 236,
      L = 44,
      R = 8,
      T = 18,
      B = 26;
    var cw = (W - L - R) / SECTIONS.length;
    var y = function (v) {
      return T + (H - T - B) * (1 - v / 100);
    };
    var ns = "http://www.w3.org/2000/svg";
    var svg = document.createElementNS(ns, "svg");
    svg.setAttribute("viewBox", "0 0 " + W + " " + H);
    svg.setAttribute("role", "img");
    svg.setAttribute(
      "aria-label",
      "Bar chart of readers remaining per section. " +
        SECTIONS.map(function (s) {
          return s.name + " " + s.feature + "%";
        }).join(", "),
    );
    function el(tag, attrs, text) {
      var n = document.createElementNS(ns, tag);
      for (var a in attrs) n.setAttribute(a, attrs[a]);
      if (text != null) n.textContent = text;
      svg.appendChild(n);
      return n;
    }
    [0, 50, 100].forEach(function (g) {
      el("line", {
        x1: L,
        x2: W - R,
        y1: y(g),
        y2: y(g),
        stroke: "#e6e0d8",
        "stroke-width": 1,
      });
      el("text", { x: L - 8, y: y(g) + 4, "text-anchor": "end" }, g + "%");
    });
    SECTIONS.forEach(function (s, i) {
      var x = L + i * cw;
      var bw = Math.min(26, cw * 0.32);
      var cx = x + cw / 2;
      el("rect", {
        x: cx - bw - 2,
        y: y(s.feature),
        width: bw,
        height: y(0) - y(s.feature),
        rx: 3,
        fill: i === DROP ? "#b0705a" : "#292622",
      });
      el("rect", {
        x: cx + 2,
        y: y(s.avg),
        width: bw,
        height: y(0) - y(s.avg),
        rx: 3,
        fill: "#d9d2c8",
      });
      el(
        "text",
        {
          x: cx - bw / 2 - 2,
          y: y(s.feature) - 6,
          "text-anchor": "middle",
          class: i === DROP ? "val drop" : "val",
        },
        s.feature,
      );
      el(
        "text",
        { x: cx, y: H - 6, "text-anchor": "middle" },
        s.name.replace("Section ", "S"),
      );
    });
    host.appendChild(svg);
  }

  var DESC = {
    isolated:
      "The design alone, centred and fitted to the window. Scrolling is locked.",
    outline:
      "The rest of the page as flat blocks: where the design sits, without the content.",
    muted:
      "The real page, faded and grayscale, not clickable. The date filter stays live.",
    full: "Everything, as built.",
  };
  var NAMES = {
    isolated: "Isolated",
    outline: "Outline",
    muted: "Muted",
    full: "Full",
  };

  function sync(level) {
    document.getElementById("cap-level").textContent = NAMES[level];
    document.getElementById("cap-desc").textContent = DESC[level];
  }

  document.addEventListener("DOMContentLoaded", function () {
    drawChart(document.getElementById("depth-chart"));
    // The range filter is "kept" context: it stays real at Outline and Muted.
    var range = document.querySelector(".range");
    range.addEventListener("click", function (e) {
      var b = e.target.closest("button");
      if (!b) return;
      range.querySelectorAll("button").forEach(function (x) {
        x.removeAttribute("aria-pressed");
      });
      b.setAttribute("aria-pressed", "true");
    });
    sync(window.fidelitySlider ? window.fidelitySlider.get() : "full");
  });
  window.addEventListener("fidelityslider:change", function (e) {
    sync(e.detail.level);
  });
})();
