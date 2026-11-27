/* ==========================================================
   Liquid Glass — refracción tipo iOS con filtro SVG
   Genera un mapa de desplazamiento a partir de la forma del
   recuadro (rectángulo redondeado) y lo aplica como
   backdrop-filter. Sólo Chromium soporta backdrop-filter:url();
   en otros navegadores se queda el desenfoque de respaldo.
   ========================================================== */
(function (global) {
  const SVG_NS = "http://www.w3.org/2000/svg";
  let counter = 0;
  let defs = null;

  // backdrop-filter: url(#svg) sólo funciona en navegadores Chromium de escritorio/Android.
  // (Chrome en iOS usa WebKit y su UA dice "CriOS", así que queda excluido.)
  const supportsRefraction = /Chrome\/|Chromium\//.test(navigator.userAgent);

  function getDefs() {
    if (defs) return defs;
    const svg = document.createElementNS(SVG_NS, "svg");
    svg.setAttribute("width", "0");
    svg.setAttribute("height", "0");
    svg.setAttribute("aria-hidden", "true");
    svg.style.cssText = "position:absolute;width:0;height:0;overflow:hidden";
    defs = document.createElementNS(SVG_NS, "defs");
    svg.appendChild(defs);
    document.body.appendChild(svg);
    return defs;
  }

  /* Distancia con signo a un rectángulo redondeado (negativa dentro) */
  function sdRoundRect(px, py, hw, hh, r) {
    const qx = Math.abs(px) - hw + r;
    const qy = Math.abs(py) - hh + r;
    const ox = Math.max(qx, 0), oy = Math.max(qy, 0);
    return Math.hypot(ox, oy) + Math.min(Math.max(qx, qy), 0) - r;
  }

  /* Mapa de desplazamiento: R = x, G = y (128 = sin desplazamiento) */
  function buildMap(w, h, radius, bezel) {
    const canvas = document.createElement("canvas");
    canvas.width = w; canvas.height = h;
    const ctx = canvas.getContext("2d");
    const img = ctx.createImageData(w, h);
    const d = img.data;
    const hw = w / 2, hh = h / 2;
    const r = Math.min(radius, hw, hh);
    const e = 0.75;

    for (let y = 0; y < h; y++) {
      for (let x = 0; x < w; x++) {
        const px = x + 0.5 - hw, py = y + 0.5 - hh;
        const dist = -sdRoundRect(px, py, hw, hh, r);   // >0 dentro
        let dx = 0, dy = 0;
        if (dist > 0 && dist < bezel) {
          // Normal hacia fuera (gradiente numérico de la SDF)
          const nx = sdRoundRect(px + e, py, hw, hh, r) - sdRoundRect(px - e, py, hw, hh, r);
          const ny = sdRoundRect(px, py + e, hw, hh, r) - sdRoundRect(px, py - e, hw, hh, r);
          const len = Math.hypot(nx, ny) || 1;
          // Perfil convexo tipo "squircle": fuerte en el borde, suave hacia dentro
          const t = 1 - dist / bezel;
          const mag = Math.pow(t, 2.2);
          dx = -(nx / len) * mag;
          dy = -(ny / len) * mag;
        }
        const i = (y * w + x) * 4;
        d[i]     = Math.round(128 + dx * 127);
        d[i + 1] = Math.round(128 + dy * 127);
        d[i + 2] = 128;
        d[i + 3] = 255;
      }
    }
    ctx.putImageData(img, 0, 0);
    return canvas.toDataURL();
  }

  function el(name, attrs) {
    const n = document.createElementNS(SVG_NS, name);
    for (const k in attrs) n.setAttribute(k, attrs[k]);
    return n;
  }

  class LiquidGlass {
    constructor(element, options = {}) {
      this.element = element;
      this.options = Object.assign({
        refraction: 70,     // intensidad de la refracción (px)
        bezel: 28,          // ancho del bisel que refracta (px)
        blur: 2.5,          // desenfoque del fondo (px)
        saturation: 1.6,    // saturación del fondo
        aberration: 6,      // separación cromática en los bordes (px)
      }, options);
      if (!supportsRefraction) return;

      this.id = "liquid-glass-" + (++counter);
      this._createFilter();
      element.classList.add("glass--refract");
      element.style.setProperty("--glass-filter", `url(#${this.id})`);
      this._ro = new ResizeObserver(() => this.update());
      this._ro.observe(element);
      this.update();
    }

    _createFilter() {
      const f = el("filter", {
        id: this.id, x: "0", y: "0",
        filterUnits: "userSpaceOnUse",
        "color-interpolation-filters": "sRGB",
      });
      this.blurNode = el("feGaussianBlur", { in: "SourceGraphic", stdDeviation: "0", result: "blur" });
      this.mapNode  = el("feImage", { x: "0", y: "0", preserveAspectRatio: "none", result: "map" });

      // Tres desplazamientos ligeramente distintos → aberración cromática en los bordes
      const ch = (name, matrix) => [
        el("feDisplacementMap", { in: "blur", in2: "map", xChannelSelector: "R", yChannelSelector: "G", result: "d" + name }),
        el("feColorMatrix", { in: "d" + name, type: "matrix", values: matrix, result: "c" + name }),
      ];
      const [dR, cR] = ch("R", "1 0 0 0 0  0 0 0 0 0  0 0 0 0 0  0 0 0 1 0");
      const [dG, cG] = ch("G", "0 0 0 0 0  0 1 0 0 0  0 0 0 0 0  0 0 0 1 0");
      const [dB, cB] = ch("B", "0 0 0 0 0  0 0 0 0 0  0 0 1 0 0  0 0 0 1 0");
      this.dispNodes = [dR, dG, dB];

      const add1 = el("feComposite", { in: "cR", in2: "cG", operator: "arithmetic", k2: "1", k3: "1", result: "rg" });
      const add2 = el("feComposite", { in: "rg", in2: "cB", operator: "arithmetic", k2: "1", k3: "1", result: "rgb" });
      this.satNode = el("feColorMatrix", { in: "rgb", type: "saturate", values: "1.6" });

      [this.blurNode, this.mapNode, dR, cR, dG, cG, dB, cB, add1, add2, this.satNode]
        .forEach(n => f.appendChild(n));
      this.filter = f;
      getDefs().appendChild(f);
    }

    set(options) {
      const needsMap = "bezel" in options;
      Object.assign(this.options, options);
      if (!this.filter) return;
      needsMap ? this.update() : this._applyParams();
    }

    _applyParams() {
      const o = this.options;
      this.blurNode.setAttribute("stdDeviation", o.blur);
      this.satNode.setAttribute("values", o.saturation);
      const s = o.refraction, a = o.aberration;
      [s + a, s, s - a].forEach((v, i) => this.dispNodes[i].setAttribute("scale", Math.max(v, 0)));
    }

    update() {
      if (!this.filter) return;
      const rect = this.element.getBoundingClientRect();
      const w = Math.max(1, Math.round(rect.width));
      const h = Math.max(1, Math.round(rect.height));
      const radius = parseFloat(getComputedStyle(this.element).borderTopLeftRadius) || 0;
      const key = [w, h, radius, this.options.bezel].join("x");
      if (key !== this._key) {
        this._key = key;
        const url = buildMap(w, h, radius, this.options.bezel);
        this.filter.setAttribute("width", w);
        this.filter.setAttribute("height", h);
        this.mapNode.setAttribute("width", w);
        this.mapNode.setAttribute("height", h);
        this.mapNode.setAttribute("href", url);
        this.mapNode.setAttributeNS("http://www.w3.org/1999/xlink", "xlink:href", url);
      }
      this._applyParams();
    }

    destroy() {
      this._ro && this._ro.disconnect();
      this.filter && this.filter.remove();
      this.element.classList.remove("glass--refract");
      this.element.style.removeProperty("--glass-filter");
    }
  }

  LiquidGlass.supported = supportsRefraction;
  LiquidGlass.attachAll = (selector = ".glass", options) =>
    Array.from(document.querySelectorAll(selector)).map(n => new LiquidGlass(n, options));

  global.LiquidGlass = LiquidGlass;
})(window);
