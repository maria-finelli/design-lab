/*!
 * Fidelity Slider v0.1.0
 * One lever from "only the design" to "the full interface around it".
 * MIT License. No dependencies.
 *
 * Point it at the design you are evaluating. Everything else on the page is
 * context, and the slider turns that context up or down live, with no rebuild.
 *
 *   isolated  the design alone, centred and fitted to the window, scrolling locked
 *   outline   the rest of the page as flat blocks (where it sits, no content)
 *   muted     the real page, faded and grayscale, not clickable
 *   full      everything, as built
 *
 * Setup (first match wins, URL beats everything):
 *   ?fidelity=outline&fidelity-focus=.card&fidelity-ui=on   URL params (also 0 to 3)
 *   <script src="fidelity-slider.js" data-focus=".card" data-level="muted"
 *           data-keep=".page-title" data-ui="on" data-keys="shift"></script>
 *   window.FidelitySlider = { focus, keep, level, ui, keys, ... }  set before the script loads
 *   <div data-fs-focus>  /  <div data-fs-keep>  /  <div data-fs-ignore>   attributes in the markup
 *
 * focus:  the outermost element of the design (the card, the modal), not its content.
 * keep:   context that must stay real at outline and muted (a filter that drives
 *         the design, the page title). Hidden at isolated like everything else.
 * ignore: elements the slider never touches (your own toolbars, captions).
 * ui:     the control starts hidden; "." shows or hides it. "on" starts it visible.
 * keys:   1 to 4 pick a level, [ and ] step. "shift" moves the level keys to
 *         Shift + 1 to 4 (for apps that already use the digits); "off" drops them.
 * url:    "off" stops the slider from syncing ?fidelity= in the address bar.
 * label:  the text before the track (default "Fidelity").
 * labels: names for the four levels, e.g. { isolated: "Solo" }.
 *
 * Styling lives in CSS custom properties (--fs-*). See fidelity-slider.tokens.css.
 *
 * API: window.fidelitySlider.set("muted"), .get(), .toggle(show?), .refresh(),
 *      .destroy(), .levels, and a "fidelityslider:change" event on window.
 *
 * Extracted from a private prototyping tool; behavior is kept 1:1.
 * Safe to inline: there is no closing script tag in here.
 */
(function () {
  "use strict";
  if (window.fidelitySlider) return;

  var LEVELS = ["isolated", "outline", "muted", "full"];
  var SKIP = {
    SCRIPT: 1,
    STYLE: 1,
    LINK: 1,
    META: 1,
    TEMPLATE: 1,
    NOSCRIPT: 1,
    HEAD: 1,
  };
  var PAD = 32; // breathing room around the design at isolated
  var URL_LEVEL = "fidelity";
  var URL_FOCUS = "fidelity-focus";
  var URL_UI = "fidelity-ui";

  var script = document.currentScript || {};
  var ds = script.dataset || {};
  var pre = window.FidelitySlider || {};
  var params = new URLSearchParams(location.search);

  function pick(urlKey, dsKey, preKey) {
    return (urlKey && params.get(urlKey)) || ds[dsKey] || pre[preKey] || null;
  }
  function toLevel(v) {
    if (v == null) return null;
    v = String(v).toLowerCase();
    if (/^[0-3]$/.test(v)) return LEVELS[+v];
    return LEVELS.indexOf(v) > -1 ? v : null;
  }

  var LABELS = {
    isolated: "Isolated",
    outline: "Outline",
    muted: "Muted",
    full: "Full",
  };
  if (pre.labels)
    for (var k in pre.labels) if (LABELS[k]) LABELS[k] = String(pre.labels[k]);
  var leadLabel = pick(null, "label", "label") || "Fidelity";

  var focusSel = pick(URL_FOCUS, "focus", "focus") || "[data-fs-focus]";
  var keepSel = pick(null, "keep", "keep") || "[data-fs-keep]";
  if (keepSel !== "[data-fs-keep]") keepSel += ", [data-fs-keep]";
  var level = toLevel(pick(URL_LEVEL, "level", "level")) || "full";
  var uiOn = (pick(URL_UI, "ui", "ui") || "off") === "on";
  var keyMode = ds.keys || pre.keys || "digits";
  var urlSync = (ds.url || pre.url || "on") !== "off";

  /* ---------- styles ----------
   * Default tokens sit in :where(:root) (zero specificity), so any :root or
   * html rule in your own CSS overrides them, whatever the load order.
   */
  var css =
    ":where(:root){" +
    "--fs-font-family:Inter,ui-sans-serif,system-ui,-apple-system,'Segoe UI',sans-serif;" +
    "--fs-canvas:#F7F4EF;--fs-block:#ECE7E0;--fs-block-line:#DFD8CF;--fs-block-radius:12px;" +
    "--fs-muted-opacity:.3;--fs-muted-filter:grayscale(1);" +
    "--fs-ease:cubic-bezier(0.16, 1, 0.3, 1);" +
    "--fs-ui-bg:#292622;--fs-ui-shadow:0 6px 20px rgba(41,38,34,.16);" +
    "--fs-ui-label:#A69E95;--fs-ui-text:#F6F2EC;" +
    "--fs-track:#706A63;--fs-fill:#B3AA9F;" +
    "--fs-stop:#918A82;--fs-stop-on:#F6F2EC;" +
    "--fs-thumb:#F6F2EC;--fs-thumb-ring:#292622;--fs-thumb-shadow:0 1px 4px rgba(0,0,0,.35);" +
    "--fs-focus-ring:rgba(246,242,236,.5);" +
    "--fs-ui-bottom:20px;--fs-z:2147483647}" +
    // Smooth hand-off between every level. Background images can't tween, so they fade with opacity.
    "[data-fs]{transition:opacity .5s var(--fs-ease),filter .5s var(--fs-ease),background-color .5s var(--fs-ease)," +
    "border-color .5s var(--fs-ease),box-shadow .5s var(--fs-ease),color .35s ease-out," +
    "translate .7s var(--fs-ease),scale .7s var(--fs-ease)}" +
    // muted: real page, quiet
    "html[data-fs-level=muted] [data-fs=ctx]{opacity:var(--fs-muted-opacity);filter:var(--fs-muted-filter);pointer-events:none}" +
    // outline and isolated: path ancestors become one quiet canvas
    "html[data-fs-level=outline],html[data-fs-level=isolated]{background:var(--fs-canvas)!important}" +
    "html[data-fs-level=outline] [data-fs=path],html[data-fs-level=isolated] [data-fs=path]{" +
    "background-color:var(--fs-canvas)!important;background-image:none!important;box-shadow:none!important;border-color:transparent!important}" +
    // outline: every context region collapses to a flat block with a slightly darker stroke
    "html[data-fs-level=outline] [data-fs=ctx]{background:var(--fs-block)!important;color:transparent!important;" +
    "border:1px solid var(--fs-block-line)!important;box-shadow:none!important;border-radius:var(--fs-block-radius);pointer-events:none}" +
    "html[data-fs-level=outline] [data-fs=ctx] *{visibility:hidden!important}" +
    // A context image keeps its box (so it still reads as a block) but drops its pixels.
    "html[data-fs-level=outline] [data-fs=ctx]:is(img,video){object-position:-99999px 0}" +
    "html[data-fs-level=outline] [data-fs=ctx]:is(svg,canvas,iframe){opacity:0}" +
    // isolated: nothing but the design, no scrolling, nothing clipped around it
    "html[data-fs-level=isolated],html[data-fs-level=isolated] body{overflow:hidden!important;overscroll-behavior:none}" +
    "html[data-fs-level=isolated] [data-fs-unclip]{overflow:visible!important}" +
    "html[data-fs-level=isolated] [data-fs=ctx],html[data-fs-level=isolated] [data-fs=keep]{opacity:0;visibility:hidden;pointer-events:none;" +
    "transition:opacity .5s var(--fs-ease),visibility 0s linear .5s}" +
    // control: a floating pill with a label, a four-stop track and the current level's name
    ".fs-ui{position:fixed;left:50%;bottom:var(--fs-ui-bottom);z-index:var(--fs-z);display:flex;align-items:center;gap:14px;" +
    "box-sizing:border-box;max-width:calc(100vw - 32px);" +
    "padding:10px 18px;border-radius:999px;background:var(--fs-ui-bg);box-shadow:var(--fs-ui-shadow);color:var(--fs-ui-text);" +
    "font:500 12px/1 var(--fs-font-family);letter-spacing:.02em;-webkit-font-smoothing:antialiased;" +
    "translate:-50% 0;transition:opacity .3s ease-out,translate .45s var(--fs-ease);user-select:none;-webkit-user-select:none}" +
    ".fs-ui.fs-hidden{opacity:0;translate:-50% 16px;pointer-events:none}" +
    ".fs-ui[data-nofocus]{display:none}" +
    ".fs-lbl{color:var(--fs-ui-label)}" +
    ".fs-name{min-width:58px;color:var(--fs-ui-text)}" +
    ".fs-slider{position:relative;flex:0 1 168px;width:168px;min-width:96px;height:24px;cursor:pointer;touch-action:none;outline:none}" +
    // A larger invisible hit area for fingers; it doesn't change what you see.
    ".fs-slider::before{content:'';position:absolute;inset:-10px -9px}" +
    ".fs-rail,.fs-fill{position:absolute;left:0;top:50%;height:4px;margin-top:-2px;border-radius:2px}" +
    ".fs-rail{right:0;background:var(--fs-track)}" +
    ".fs-fill{width:0;background:var(--fs-fill);transition:width .45s var(--fs-ease)}" +
    ".fs-dot{position:absolute;top:50%;width:8px;height:8px;margin:-4px 0 0 -4px;border-radius:50%;" +
    "background:var(--fs-stop);transition:background .2s ease-out,scale .2s ease-out}" +
    ".fs-dot.on{background:var(--fs-stop-on)}.fs-dot:hover{scale:1.35}" +
    ".fs-knob{position:absolute;top:50%;left:0;width:18px;height:18px;margin:-9px 0 0 -9px;border-radius:50%;" +
    "background:var(--fs-thumb);box-shadow:0 0 0 3px var(--fs-thumb-ring),var(--fs-thumb-shadow);" +
    "transition:left .45s var(--fs-ease),scale .2s ease-out,box-shadow .2s ease-out}" +
    ".fs-slider:hover .fs-knob{scale:1.08}" +
    ".fs-slider.fs-drag .fs-knob,.fs-slider.fs-drag .fs-fill{transition:none}" +
    ".fs-slider.fs-drag .fs-knob{scale:1.15}" +
    ".fs-slider:focus-visible .fs-knob{box-shadow:0 0 0 3px var(--fs-thumb-ring),0 0 0 5px var(--fs-focus-ring)}" +
    ".fs-sr{position:absolute;width:1px;height:1px;margin:-1px;padding:0;overflow:hidden;clip:rect(0 0 0 0);white-space:nowrap;border:0}" +
    "@media (prefers-reduced-motion:reduce){[data-fs],.fs-ui,.fs-knob,.fs-fill,.fs-dot{transition:none!important}}";
  var style = document.createElement("style");
  style.setAttribute("data-fs-ui", "");
  style.textContent = css;
  (document.head || document.documentElement).appendChild(style);

  /* ---------- marking ---------- */
  var marked = [];
  var focusEls = [];

  function clearMarks() {
    for (var i = 0; i < marked.length; i++)
      marked[i].removeAttribute("data-fs");
    marked = [];
  }
  function mark(el, kind) {
    if (el.getAttribute("data-fs") !== kind) el.setAttribute("data-fs", kind);
    marked.push(el);
  }
  function qsa(sel) {
    try {
      return Array.prototype.slice.call(document.querySelectorAll(sel));
    } catch (_e) {
      console.warn("[fidelity slider] bad selector:", sel);
      return [];
    }
  }

  function remark() {
    clearMarks();
    var focus = qsa(focusSel).filter(function (el) {
      return !el.closest("[data-fs-ui]");
    });
    var keep = qsa(keepSel).filter(function (el) {
      return !focus.some(function (f) {
        return f.contains(el) || el.contains(f);
      });
    });
    focusEls = focus;
    if (ui) ui.toggleAttribute("data-nofocus", !focus.length);
    if (!focus.length) return;

    var roots = focus.concat(keep);
    var path = new Set();
    roots.forEach(function (r) {
      for (var a = r.parentElement; a; a = a.parentElement) path.add(a);
    });
    var rootSet = new Set(roots);
    path.forEach(function (a) {
      if (a !== document.documentElement) mark(a, "path");
      for (var c = a.firstElementChild; c; c = c.nextElementSibling) {
        if (
          path.has(c) ||
          rootSet.has(c) ||
          SKIP[c.tagName] ||
          c.hasAttribute("data-fs-ui") ||
          c.hasAttribute("data-fs-ignore")
        )
          continue;
        mark(c, "ctx");
      }
    });
    keep.forEach(function (k) {
      mark(k, "keep");
    });
    focus.forEach(function (f) {
      mark(f, "focus");
    });
  }

  /* ---------- isolated: lock scrolling, fit the design in the window ---------- */
  var shifted = new Set();
  var opened = new Map(); // clipping or scrolling ancestors opened up at isolated, and their scroll spot
  function openAncestors(el) {
    for (
      var a = el.parentElement;
      a && a !== document.body;
      a = a.parentElement
    ) {
      if (opened.has(a)) continue;
      var cs = getComputedStyle(a);
      if (/hidden|clip|auto|scroll/.test(cs.overflowX + " " + cs.overflowY)) {
        opened.set(a, [a.scrollLeft, a.scrollTop]);
        a.setAttribute("data-fs-unclip", "");
      }
    }
  }
  function closeAncestors() {
    opened.forEach(function (pos, a) {
      a.removeAttribute("data-fs-unclip");
      a.scrollLeft = pos[0];
      a.scrollTop = pos[1];
    });
    opened.clear();
  }

  function centre() {
    if (level !== "isolated") {
      shifted.forEach(function (el) {
        el.style.translate = "";
        el.style.scale = "";
        el.style.transformOrigin = "";
      });
      shifted.clear();
      closeAncestors();
      return;
    }
    var vw = document.documentElement.clientWidth || window.innerWidth;
    var vh = window.innerHeight;
    focusEls.forEach(function (el) {
      // Open every clipping or scrolling ancestor so nothing crops the design,
      // then measure where it rests: freeze any glide in progress, read the layout
      // without our translate and scale, then carry on from where it was.
      openAncestors(el);
      var cs = getComputedStyle(el);
      var nowT = cs.translate,
        nowS = cs.scale;
      el.style.transition = "none";
      el.style.translate = "none";
      el.style.scale = "none";
      var r = el.getBoundingClientRect();
      el.style.translate = nowT === "none" ? "" : nowT;
      el.style.scale = nowS === "none" ? "" : nowS;
      void el.offsetWidth;
      el.style.transition = "";
      if (!r.width || !r.height) return;
      // translate is in the element's own units; undo ancestor scaling.
      var k = el.offsetWidth ? r.width / el.offsetWidth : 1;
      // Fit inside the window: shrink a design that's too big, never enlarge one.
      var fit = Math.min(
        1,
        (vw - PAD * 2) / r.width,
        (vh - PAD * 2) / r.height,
      );
      var dx = vw / 2 - (r.left + r.width / 2);
      var dy = vh / 2 - (r.top + r.height / 2);
      el.style.transformOrigin = "50% 50%";
      el.style.translate =
        Math.round(dx / k) + "px " + Math.round(dy / k) + "px";
      el.style.scale = fit < 1 ? String(Math.round(fit * 1000) / 1000) : "1";
      shifted.add(el);
    });
  }

  /* ---------- level ---------- */
  var dragging = false;
  function set(next, opts) {
    next = toLevel(next);
    if (!next) return;
    var changed = next !== level;
    level = next;
    document.documentElement.setAttribute("data-fs-level", level);
    remark();
    centre();
    renderUI();
    if (changed && live) live.textContent = leadLabel + ": " + LABELS[level];
    if (urlSync && (!opts || opts.url !== false)) {
      var u = new URL(location.href);
      if (level === "full") u.searchParams.delete(URL_LEVEL);
      else u.searchParams.set(URL_LEVEL, level);
      try {
        history.replaceState(history.state, "", u);
      } catch (_e) {}
    }
    window.dispatchEvent(
      new CustomEvent("fidelityslider:change", { detail: { level: level } }),
    );
  }

  /* ---------- control: a track with a dot per level ---------- */
  var ui = null,
    slider,
    knob,
    fill,
    nameEl,
    live,
    dots = [];
  function pct(i) {
    return (i / (LEVELS.length - 1)) * 100;
  }
  function keyHint(i) {
    return (keyMode === "shift" ? "Shift + " : "") + (i + 1);
  }
  function setHidden(hide) {
    ui.classList.toggle("fs-hidden", hide);
    // A hidden control must not be reachable by Tab or a screen reader.
    ui.toggleAttribute("inert", hide);
    ui.setAttribute("aria-hidden", hide ? "true" : "false");
  }
  function buildUI() {
    ui = document.createElement("div");
    ui.className = "fs-ui";
    ui.setAttribute("data-fs-ui", "");
    ui.setAttribute("role", "group");
    ui.setAttribute("aria-label", leadLabel);

    var lbl = document.createElement("span");
    lbl.className = "fs-lbl";
    lbl.setAttribute("aria-hidden", "true");
    lbl.textContent = leadLabel;

    slider = document.createElement("div");
    slider.className = "fs-slider";
    slider.tabIndex = 0;
    slider.setAttribute("role", "slider");
    slider.setAttribute("aria-label", leadLabel + " level");
    slider.setAttribute("aria-orientation", "horizontal");
    slider.setAttribute("aria-valuemin", "0");
    slider.setAttribute("aria-valuemax", String(LEVELS.length - 1));
    if (keyMode !== "off")
      slider.setAttribute(
        "aria-keyshortcuts",
        LEVELS.map(function (_l, i) {
          return keyHint(i).replace(" + ", "+");
        }).join(" "),
      );
    var rail = document.createElement("div");
    rail.className = "fs-rail";
    fill = document.createElement("div");
    fill.className = "fs-fill";
    slider.appendChild(rail);
    slider.appendChild(fill);
    LEVELS.forEach(function (l, i) {
      var d = document.createElement("span");
      d.className = "fs-dot";
      d.style.left = pct(i) + "%";
      d.title = LABELS[l] + (keyMode === "off" ? "" : " (" + keyHint(i) + ")");
      dots.push(d);
      slider.appendChild(d);
    });
    knob = document.createElement("div");
    knob.className = "fs-knob";
    slider.appendChild(knob);

    nameEl = document.createElement("span");
    nameEl.className = "fs-name";
    nameEl.setAttribute("aria-hidden", "true");

    ui.appendChild(lbl);
    ui.appendChild(slider);
    ui.appendChild(nameEl);
    document.body.appendChild(ui);

    // Announces level changes made with the page-wide keys, even while the control is hidden.
    live = document.createElement("div");
    live.className = "fs-sr";
    live.setAttribute("data-fs-ui", "");
    live.setAttribute("aria-live", "polite");
    document.body.appendChild(live);

    setHidden(!uiOn);

    // Drag anywhere on the track: the knob follows the pointer and the page moves
    // to the nearest level as you pass it; on release the knob settles on its dot.
    function follow(e) {
      var b = slider.getBoundingClientRect();
      var r = Math.max(0, Math.min(1, (e.clientX - b.left) / b.width));
      knob.style.left = r * 100 + "%";
      fill.style.width = r * 100 + "%";
      var i = Math.round(r * (LEVELS.length - 1));
      if (LEVELS[i] !== level) set(LEVELS[i]);
    }
    function end() {
      if (!dragging) return;
      dragging = false;
      slider.classList.remove("fs-drag");
      renderUI();
    }
    slider.addEventListener("pointerdown", function (e) {
      dragging = true;
      slider.setPointerCapture(e.pointerId);
      slider.classList.add("fs-drag");
      follow(e);
      e.preventDefault();
      slider.focus({ preventScroll: true });
    });
    slider.addEventListener("pointermove", function (e) {
      if (dragging) follow(e);
    });
    slider.addEventListener("pointerup", end);
    slider.addEventListener("pointercancel", end);
    slider.addEventListener("keydown", function (e) {
      var i = LEVELS.indexOf(level);
      var to = {
        ArrowLeft: i - 1,
        ArrowDown: i - 1,
        ArrowRight: i + 1,
        ArrowUp: i + 1,
        Home: 0,
        End: LEVELS.length - 1,
      }[e.key];
      if (to == null) return;
      e.preventDefault();
      e.stopPropagation(); // the host page's own arrow-key handlers stay out of it
      set(LEVELS[Math.max(0, Math.min(LEVELS.length - 1, to))]);
    });
  }
  function renderUI() {
    if (!ui) return;
    var i = LEVELS.indexOf(level);
    slider.setAttribute("aria-valuenow", String(i));
    slider.setAttribute("aria-valuetext", LABELS[level]);
    nameEl.textContent = LABELS[level];
    dots.forEach(function (d, j) {
      d.classList.toggle("on", j <= i);
    });
    if (dragging) return;
    knob.style.left = pct(i) + "%";
    fill.style.width = pct(i) + "%";
  }

  /* ---------- boot ---------- */
  var mo = null,
    ro = null,
    watchTimer = null,
    onResize,
    onKey,
    onWatch;
  function boot() {
    buildUI();
    set(level, { url: false });

    // SPAs re-render: re-mark when nodes come or go (attributes are ignored, so no loop).
    var queued = false;
    mo = new MutationObserver(function () {
      if (queued) return;
      queued = true;
      requestAnimationFrame(function () {
        queued = false;
        var before = focusEls[0];
        remark();
        if (focusEls[0] !== before) centre();
      });
    });
    mo.observe(document.body, { childList: true, subtree: true });

    // Re-fit when the design itself changes size (a drawer opens, a tab swaps).
    if (window.ResizeObserver) {
      var watched = null;
      ro = new ResizeObserver(function () {
        if (level === "isolated") centre();
      });
      onWatch = function () {
        if (focusEls[0] === watched) return;
        ro.disconnect();
        watched = focusEls[0] || null;
        if (watched) ro.observe(watched);
      };
      window.addEventListener("fidelityslider:change", onWatch);
      watchTimer = setInterval(onWatch, 1000);
      onWatch();
    }

    onResize = function () {
      centre();
      renderUI();
    };
    window.addEventListener("resize", onResize);
    // Capture phase on window, so a host handler that stops propagation can't swallow it.
    onKey = function (e) {
      var t = e.target;
      if (e.metaKey || e.ctrlKey || e.altKey) return;
      if (
        t &&
        (t.isContentEditable || /^(INPUT|TEXTAREA|SELECT)$/.test(t.tagName))
      )
        return;
      if (e.key === "." || e.code === "Period") {
        if (!focusEls.length) remark(); // the design may have rendered after the last pass
        if (!focusEls.length) {
          console.warn(
            "[fidelity slider] nothing on this page matches " + focusSel,
          );
          return;
        }
        setHidden(!ui.classList.contains("fs-hidden"));
        return;
      }
      if (keyMode === "off" || !focusEls.length) return;
      var i = LEVELS.indexOf(level);
      var digit = /^Digit[1-4]$/.test(e.code) ? +e.code.slice(5) : 0;
      if (digit && e.shiftKey === (keyMode === "shift")) set(LEVELS[digit - 1]);
      else if (e.key === "[") set(LEVELS[Math.max(0, i - 1)]);
      else if (e.key === "]") set(LEVELS[Math.min(3, i + 1)]);
    };
    window.addEventListener("keydown", onKey, true);
  }

  function destroy() {
    level = "full";
    centre();
    clearMarks();
    document.documentElement.removeAttribute("data-fs-level");
    if (mo) mo.disconnect();
    if (ro) ro.disconnect();
    if (watchTimer) clearInterval(watchTimer);
    if (onWatch) window.removeEventListener("fidelityslider:change", onWatch);
    if (onResize) window.removeEventListener("resize", onResize);
    if (onKey) window.removeEventListener("keydown", onKey, true);
    if (ui) ui.remove();
    if (live) live.remove();
    style.remove();
    delete window.fidelitySlider;
  }

  window.fidelitySlider = {
    set: set,
    get: function () {
      return level;
    },
    levels: LEVELS.slice(),
    toggle: function (show) {
      if (!ui) return;
      setHidden(show == null ? !ui.classList.contains("fs-hidden") : !show);
    },
    refresh: function () {
      remark();
      centre();
    },
    destroy: destroy,
  };
  if (document.readyState === "loading")
    document.addEventListener("DOMContentLoaded", boot);
  else boot();
})();
