/* ==========================================================
   Efectos de estaciones: pétalos, motas de sol, hojas y nieve.
   Dos lienzos: uno detrás del cristal (se refracta) y otro
   delante, con pocas partículas grandes y desenfocadas para
   dar profundidad.
   ========================================================== */
(function (global) {
  const rand = (a, b) => a + Math.random() * (b - a);
  const pick = arr => arr[(Math.random() * arr.length) | 0];
  const TAU = Math.PI * 2;

  /* Sprites pre-renderizados: mucho más rápido que un degradado por partícula */
  function sprite(stops, size = 64) {
    const c = document.createElement("canvas");
    c.width = c.height = size;
    const x = c.getContext("2d"), r = size / 2;
    const g = x.createRadialGradient(r, r, 0, r, r, r);
    stops.forEach(([o, col]) => g.addColorStop(o, col));
    x.fillStyle = g; x.fillRect(0, 0, size, size);
    return c;
  }
  const SNOW = sprite([[0, "rgba(255,255,255,1)"], [0.45, "rgba(255,255,255,.9)"], [1, "rgba(255,255,255,0)"]]);
  const MOTE = sprite([[0, "rgba(255,250,225,1)"], [0.12, "rgba(255,222,140,.75)"], [0.35, "rgba(255,190,80,.25)"], [1, "rgba(255,170,50,0)"]]);

  /* ---------- Definición de cada estación ---------- */
  const TYPES = {
    spring: {
      back: 70, front: 6,
      make(p, w, h, fresh) {
        p.x = rand(-50, w); p.y = fresh ? rand(-h, h) : rand(-60, -20);
        p.size = rand(7, 13) * p.depth;
        p.vy = rand(0.35, 0.8) * p.depth; p.vx = rand(0.2, 0.6);
        p.color = pick(["#ffd1dc", "#ffb7c5", "#ffe4ec", "#f9a8c0", "#fff5f8"]);
        p.sway = rand(0.6, 1.6); p.flip = rand(0.01, 0.03);
      },
      step(p, t, dt) {
        p.x += (p.vx + Math.sin(t * 0.001 * p.sway + p.phase) * 0.6) * dt;
        p.y += p.vy * dt;
        p.rot += p.vr * dt; p.tumble += p.flip * dt;
      },
      draw(ctx, p) {
        ctx.scale(1, 0.25 + 0.75 * Math.abs(Math.cos(p.tumble)));   // giro 3D
        const s = p.size;
        ctx.fillStyle = p.color;
        ctx.beginPath();                             // pétalo de cerezo con muesca
        ctx.moveTo(0, -s);
        ctx.bezierCurveTo(s * 0.9, -s * 0.9, s * 0.8, s * 0.6, 0, s);
        ctx.bezierCurveTo(-s * 0.8, s * 0.6, -s * 0.9, -s * 0.9, 0, -s);
        ctx.fill();
        ctx.fillStyle = "rgba(255,255,255,.45)";
        ctx.beginPath(); ctx.ellipse(-s * 0.2, -s * 0.2, s * 0.18, s * 0.45, 0.3, 0, TAU); ctx.fill();
      },
    },

    summer: {
      back: 60, front: 5, blend: "lighter",
      make(p, w, h, fresh) {
        p.x = rand(0, w); p.y = fresh ? rand(0, h) : h + 20;
        p.size = rand(2.5, 7) * p.depth;
        p.vy = -rand(0.2, 0.6) * p.depth; p.vx = rand(-0.15, 0.15);
      },
      step(p, t, dt) {
        p.x += (p.vx + Math.sin(t * 0.0007 + p.phase) * 0.3) * dt;
        p.y += p.vy * dt;
        p.twinkle = 0.5 + 0.5 * Math.sin(t * 0.003 + p.phase * 3);
      },
      draw(ctx, p) {
        const r = p.size * 4;
        ctx.globalAlpha *= p.twinkle;
        ctx.drawImage(MOTE, -r, -r, r * 2, r * 2);
      },
    },

    autumn: {
      back: 45, front: 5,
      make(p, w, h, fresh) {
        p.x = fresh ? rand(-100, w) : rand(-200, w * 0.7); p.y = fresh ? rand(-h, h) : rand(-80, -30);
        p.size = rand(10, 18) * p.depth;
        p.vy = rand(0.6, 1.3) * p.depth; p.vx = rand(0.4, 1.0) * p.depth;
        p.color = pick(["#e2582b", "#f39c34", "#c0392b", "#d9a62e", "#a8501f", "#e8772e"]);
        p.flip = rand(0.02, 0.05); p.vr = rand(-0.04, 0.04);
      },
      step(p, t, dt) {
        const gust = 0.6 + Math.max(0, Math.sin(t * 0.00035)) * 2.2;   // ráfagas de viento
        p.x += (p.vx * gust + Math.sin(t * 0.0015 + p.phase) * 0.8) * dt;
        p.y += (p.vy + Math.cos(t * 0.002 + p.phase) * 0.3) * dt;
        p.rot += p.vr * gust * dt; p.tumble += p.flip * dt;
      },
      draw(ctx, p) {
        ctx.scale(0.2 + 0.8 * Math.abs(Math.cos(p.tumble)), 1);
        const s = p.size;
        ctx.fillStyle = p.color;
        ctx.beginPath();                                 // hoja lanceolada
        ctx.moveTo(0, -s);
        ctx.quadraticCurveTo(s * 0.75, -s * 0.2, 0, s * 0.85);
        ctx.quadraticCurveTo(-s * 0.75, -s * 0.2, 0, -s);
        ctx.fill();
        ctx.strokeStyle = "rgba(60,20,0,.45)";
        ctx.lineWidth = Math.max(0.8, s * 0.07);
        ctx.beginPath(); ctx.moveTo(0, -s * 0.85); ctx.lineTo(0, s * 1.15); ctx.stroke();  // nervio + tallo
      },
    },

    winter: {
      back: 160, front: 10,
      make(p, w, h, fresh) {
        p.x = rand(-50, w + 50); p.y = fresh ? rand(-h, h) : rand(-40, -10);
        p.size = rand(1.6, 4.2) * p.depth;
        p.vy = rand(0.5, 1.2) * p.depth; p.vx = rand(-0.2, 0.2);
      },
      step(p, t, dt) {
        p.x += (p.vx + Math.sin(t * 0.001 + p.phase) * 0.45 * p.depth) * dt;
        p.y += p.vy * dt;
      },
      draw(ctx, p) {
        const r = p.size * 1.8;
        ctx.drawImage(SNOW, -r, -r, r * 2, r * 2);
      },
    },
  };

  /* ---------- Capa de partículas (un lienzo) ---------- */
  class Layer {
    constructor(canvas, { front = false } = {}) {
      this.canvas = canvas;
      this.ctx = canvas.getContext("2d");
      this.front = front;
      this.particles = [];
      this.resize();
    }
    resize() {
      const dpr = Math.min(window.devicePixelRatio || 1, 2);
      this.w = window.innerWidth; this.h = window.innerHeight;
      this.canvas.width = this.w * dpr; this.canvas.height = this.h * dpr;
      this.ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    }
    spawn(season, fresh) {
      const p = {
        season, alpha: 0, dying: false,
        depth: this.front ? rand(2.2, 3.2) : rand(0.5, 1.4),
        rot: rand(0, TAU), vr: rand(-0.02, 0.02), tumble: rand(0, TAU),
        phase: rand(0, TAU), kx: 0, ky: 0,
      };
      TYPES[season].make(p, this.w, this.h, fresh);
      this.particles.push(p);
    }
    out(p) {
      const m = 120;
      return p.y > this.h + m || p.y < -this.h - m || p.x > this.w + m * 2 || p.x < -m * 3;
    }
  }

  class SeasonFX {
    constructor(backCanvas, frontCanvas) {
      this.layers = [new Layer(backCanvas), new Layer(frontCanvas, { front: true })];
      this.pointer = { x: -1e4, y: -1e4 };
      this.reduced = matchMedia("(prefers-reduced-motion: reduce)").matches;
      addEventListener("resize", () => this.layers.forEach(l => l.resize()));
      addEventListener("pointermove", e => { this.pointer.x = e.clientX; this.pointer.y = e.clientY; });
      addEventListener("pointerleave", () => { this.pointer.x = this.pointer.y = -1e4; });
      this._tick = this._tick.bind(this);
    }

    set(season) {
      if (season === this.season) return;
      this.season = season;
      const def = TYPES[season];
      this.layers.forEach(l => {
        l.particles.forEach(p => (p.dying = true));          // las anteriores se desvanecen
        const n = l.front ? def.front : def.back;
        const scaled = Math.round(n * Math.min(1, (l.w * l.h) / (1280 * 800)) + (l.front ? 0 : 10));
        for (let i = 0; i < Math.max(scaled, 3); i++) l.spawn(season, true);
      });
      if (this.reduced) { this._frame(0, true); return; }
      if (!this._running) { this._running = true; requestAnimationFrame(this._tick); }
    }

    _tick(t) {
      // dt en "fotogramas de 60 Hz": el movimiento no depende de los FPS
      const dt = this._last ? Math.min((t - this._last) / 16.67, 4) : 1;
      this._last = t;
      this._frame(t, false, dt);
      requestAnimationFrame(this._tick);
    }

    _frame(t, still, dt = 1) {
      const { pointer } = this;
      for (const l of this.layers) {
        const { ctx } = l;
        ctx.clearRect(0, 0, l.w, l.h);
        for (let i = l.particles.length - 1; i >= 0; i--) {
          const p = l.particles[i];
          const def = TYPES[p.season];
          if (!still) {
            def.step(p, t, dt);
            // El puntero aparta las partículas cercanas
            const dx = p.x - pointer.x, dy = p.y - pointer.y, d2 = dx * dx + dy * dy;
            if (d2 < 120 * 120) {
              const f = (1 - Math.sqrt(d2) / 120) * 0.6;
              const d = Math.sqrt(d2) || 1;
              p.kx += (dx / d) * f * dt; p.ky += (dy / d) * f * dt;
            }
            const damp = Math.pow(0.94, dt);
            p.kx *= damp; p.ky *= damp;
            p.x += p.kx * dt; p.y += p.ky * dt;
          }
          p.alpha = still ? 1 : p.dying ? p.alpha - 0.025 * dt : Math.min(1, p.alpha + 0.03 * dt);
          if (p.dying && p.alpha <= 0) { l.particles.splice(i, 1); continue; }
          if (!still && l.out(p)) {
            l.particles.splice(i, 1);
            if (!p.dying) l.spawn(p.season, false);
            continue;
          }
          ctx.save();
          ctx.globalCompositeOperation = def.blend || "source-over";
          ctx.globalAlpha = p.alpha * (l.front ? 0.8 : 0.7 + 0.3 * Math.min(p.depth, 1));
          ctx.translate(p.x, p.y);
          ctx.rotate(p.rot);
          def.draw(ctx, p);
          ctx.restore();
        }
      }
    }
  }

  SeasonFX.fromDate = (date = new Date(), southern = false) => {
    const m = date.getMonth();  // estaciones meteorológicas
    const n = m <= 1 || m === 11 ? "winter" : m <= 4 ? "spring" : m <= 7 ? "summer" : "autumn";
    const flip = { winter: "summer", summer: "winter", spring: "autumn", autumn: "spring" };
    return southern ? flip[n] : n;
  };

  global.SeasonFX = SeasonFX;
})(window);
