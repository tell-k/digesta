// pop スタイルの部品。doodle.js と同じイラストを使い、色と枠の線を変えている。
// 回ごとの追加イラストは digest/icons.js に Object.assign(ICONS, { 名前(p) { ... } }) の形で書く。
const NS = "http://www.w3.org/2000/svg";
const INK = "#2b2622";
const C = {
  coral: "#f2665b", pink: "#ffc9c2", yellow: "#f9c846", green: "#7cc36a", leaf: "#4fa35a",
  teal: "#2bb3a3", sky: "#8fd0f2", blue: "#5a8fe6", navy: "#2f4a7a", purple: "#9a6fd8",
  magenta: "#d6338a", orange: "#f39a2b", brown: "#b98958", sand: "#f1dfc4", gray: "#c9c6c0",
  white: "#ffffff", skin: "#ffe0c2", red: "#e23b3b", cream: "#fff6dc", lav: "#dcd0f7",
};

// 章のテーマ色(episode.yaml の color に書ける名前)。hex は文字や帯、tint は蛍光ペンや淡い面
const PAL = {
  coral: { hex: "#e8445a", tint: "#ffe3e8" }, magenta: { hex: "#d63a8a", tint: "#fbe0ef" }, orange: { hex: "#f08a24", tint: "#fff0d6" },
  teal: { hex: "#1fb59b", tint: "#dcf5ee" }, blue: { hex: "#3b82e6", tint: "#deebfb" }, purple: { hex: "#8b5cf6", tint: "#ece4fb" }, green: { hex: "#5cb85c", tint: "#e3f4e0" },
  yellow: { hex: "#f2b705", tint: "#fff6c8" }, sky: { hex: "#38bdf8", tint: "#dff4fd" },
};

class Pen {
  constructor(svg, seed) {
    this.svg = svg;
    this.rc = rough.svg(svg);
    this.seed = seed;
    this.n = 0;
  }
  o(fill, extra) {
    return Object.assign(
      { stroke: INK, strokeWidth: 2.3, roughness: 1.0, bowing: 1.0, seed: this.seed + this.n++, fillStyle: "solid", fill: fill || undefined },
      extra || {},
    );
  }
  add(node) { this.svg.appendChild(node); return node; }
  rect(x, y, w, h, f, o) { return this.add(this.rc.rectangle(x, y, w, h, this.o(f, o))); }
  rr(x, y, w, h, r, f, o) {
    const d = `M${x + r} ${y} H${x + w - r} Q${x + w} ${y} ${x + w} ${y + r} V${y + h - r} Q${x + w} ${y + h} ${x + w - r} ${y + h} H${x + r} Q${x} ${y + h} ${x} ${y + h - r} V${y + r} Q${x} ${y} ${x + r} ${y} Z`;
    return this.path(d, f, o);
  }
  circ(cx, cy, d, f, o) { return this.add(this.rc.circle(cx, cy, d, this.o(f, o))); }
  ell(cx, cy, w, h, f, o) { return this.add(this.rc.ellipse(cx, cy, w, h, this.o(f, o))); }
  line(x1, y1, x2, y2, o) { return this.add(this.rc.line(x1, y1, x2, y2, this.o(null, o))); }
  path(d, f, o) { return this.add(this.rc.path(d, this.o(f, o))); }
  poly(pts, f, o) { return this.add(this.rc.polygon(pts, this.o(f, o))); }
  curve(pts, o) { return this.add(this.rc.curve(pts, this.o(null, o))); }
  dot(cx, cy, d) { return this.circ(cx, cy, d || 4, INK, { roughness: 0.4, strokeWidth: 1 }); }
  text(x, y, s, size, color, extra) {
    const t = document.createElementNS(NS, "text");
    t.setAttribute("x", x); t.setAttribute("y", y);
    t.setAttribute("font-size", size || 12);
    t.setAttribute("fill", color || INK);
    t.setAttribute("text-anchor", "middle");
    t.setAttribute("font-family", "Yusei Magic");
    if (extra) for (const k in extra) t.setAttribute(k, extra[k]);
    t.textContent = s;
    return this.add(t);
  }
  sparkle(x, y, s, f) {
    const k = s * 0.28;
    return this.path(`M${x} ${y - s} Q${x + k} ${y - k} ${x + s} ${y} Q${x + k} ${y + k} ${x} ${y + s} Q${x - k} ${y + k} ${x - s} ${y} Q${x - k} ${y - k} ${x} ${y - s} Z`, f || C.yellow, { strokeWidth: 1.6 });
  }
  steam(x, y) {
    this.curve([[x, y], [x - 4, y - 7], [x + 3, y - 13], [x - 2, y - 20]], { strokeWidth: 1.8 });
  }
}

const ICONS = {
  tablet(p) {
    p.rr(22, 6, 56, 88, 7, C.white);
    p.rect(28, 14, 44, 64, C.pink, { strokeWidth: 1.6 });
    p.rect(31, 17, 18, 24, C.white, { strokeWidth: 1.4 });
    p.rect(52, 17, 17, 13, C.white, { strokeWidth: 1.4 });
    p.rect(52, 33, 17, 8, C.white, { strokeWidth: 1.4 });
    p.rect(31, 44, 38, 31, C.white, { strokeWidth: 1.4 });
    p.poly([[58, 2], [68, 2], [68, 26], [63, 21], [58, 26]], C.coral);
    p.circ(50, 86, 5, C.white, { strokeWidth: 1.5 });
  },
  checklist(p) {
    p.rr(16, 14, 52, 74, 5, C.white);
    p.rr(32, 7, 20, 12, 3, C.yellow);
    for (let i = 0; i < 3; i++) {
      const y = 36 + i * 15;
      p.path(`M23 ${y} l4 5 l8 -10`, null, { stroke: C.coral, strokeWidth: 3 });
      p.line(40, y, 60, y, { strokeWidth: 1.8 });
    }
    p.circ(70, 64, 28, "rgba(143,208,242,0.75)");
    p.line(80, 75, 93, 90, { strokeWidth: 5 });
  },
  kitchen(p) {
    p.poly([[6, 50], [94, 50], [86, 66], [14, 66]], C.white);
    p.rect(14, 66, 72, 22, C.pink);
    p.ell(36, 57, 24, 7, C.gray, { strokeWidth: 1.6 });
    p.ell(64, 57, 24, 7, C.gray, { strokeWidth: 1.6 });
    p.sparkle(22, 30, 9); p.sparkle(50, 20, 12); p.sparkle(80, 32, 8);
  },
  waffle(p) {
    p.steam(36, 26); p.steam(52, 24); p.steam(68, 26);
    p.rr(16, 32, 68, 50, 9, C.yellow);
    for (let i = 1; i < 4; i++) p.line(16 + i * 17, 34, 16 + i * 17, 80, { stroke: C.brown, strokeWidth: 2.4 });
    for (let i = 1; i < 3; i++) p.line(18, 32 + i * 16.6, 82, 32 + i * 16.6, { stroke: C.brown, strokeWidth: 2.4 });
  },
  pizza(p) {
    p.steam(34, 20); p.steam(50, 16); p.steam(66, 20);
    p.circ(50, 58, 66, "#f3c779");
    p.circ(50, 58, 52, C.orange, { strokeWidth: 1.6 });
    [[40, 48], [60, 50], [50, 66], [36, 66], [64, 68]].forEach(([x, y]) => p.circ(x, y, 9, C.red, { strokeWidth: 1.2 }));
    p.line(50, 26, 50, 90, { strokeWidth: 1.4 }); p.line(19, 58, 81, 58, { strokeWidth: 1.4 });
  },
  asagao(p) {
    p.line(50, 72, 50, 6, { stroke: C.brown, strokeWidth: 2.6 });
    p.curve([[50, 72], [38, 60], [58, 50], [42, 38], [56, 26], [46, 14]], { stroke: C.leaf, strokeWidth: 2.6 });
    p.path("M38 58 q-14 -8 -18 4 q8 10 18 -4 Z", C.green); p.path("M60 48 q14 -8 18 4 q-8 10 -18 -4 Z", C.green);
    p.circ(30, 30, 24, C.blue); p.circ(70, 26, 20, C.purple); p.circ(68, 62, 18, C.coral);
    [[30, 30, 7], [70, 26, 6], [68, 62, 5]].forEach(([x, y, s]) => p.sparkle(x, y, s, C.white));
    p.poly([[30, 72], [70, 72], [64, 96], [36, 96]], "#d98a5f");
  },
  caterpillar(p) {
    p.path("M6 78 Q50 96 94 74 Q60 70 6 78 Z", C.green);
    [[20, 62], [34, 56], [48, 62], [62, 56]].forEach(([x, y]) => p.circ(x, y, 19, "#b6e06a"));
    p.circ(78, 56, 24, "#b6e06a");
    p.dot(74, 53, 3.5); p.dot(83, 53, 3.5);
    p.path("M74 61 q5 4 9 0", null, { strokeWidth: 1.6 });
    p.line(72, 45, 68, 34, { strokeWidth: 1.6 }); p.line(84, 45, 90, 35, { strokeWidth: 1.6 });
  },
  spray(p) {
    p.rr(14, 42, 28, 46, 5, C.sky);
    p.rect(20, 26, 16, 16, C.white);
    p.poly([[36, 26], [50, 24], [50, 34], [36, 34]], C.coral);
    p.path("M30 34 q10 6 6 16", null, { strokeWidth: 2 });
    [[58, 22], [66, 30], [58, 36], [70, 20], [74, 38]].forEach(([x, y]) => p.line(x, y, x + 5, y + (y < 30 ? -2 : 2), { strokeWidth: 1.6, stroke: C.blue }));
    [[76, 62], [88, 72], [70, 80], [86, 88]].forEach(([x, y]) => {
      p.circ(x, y, 9, C.red, { strokeWidth: 1.4 });
      p.line(x - 6, y - 4, x - 9, y - 7, { strokeWidth: 1.2 }); p.line(x + 6, y - 4, x + 9, y - 7, { strokeWidth: 1.2 });
      p.line(x - 6, y + 4, x - 9, y + 7, { strokeWidth: 1.2 }); p.line(x + 6, y + 4, x + 9, y + 7, { strokeWidth: 1.2 });
    });
  },
  grasshopper(p) {
    p.path("M10 66 Q40 44 80 46 Q96 44 92 52 Q70 70 10 66 Z", "#9ad25e");
    p.path("M44 60 L60 26 L72 62", null, { strokeWidth: 2.6 });
    p.line(30, 64, 24, 80, { strokeWidth: 2 }); p.line(54, 62, 52, 80, { strokeWidth: 2 });
    p.dot(84, 49, 3.5);
    p.line(88, 45, 96, 30, { strokeWidth: 1.6 }); p.line(84, 45, 86, 28, { strokeWidth: 1.6 });
  },
  seeds(p) {
    p.rr(14, 40, 56, 46, 4, C.cream);
    p.path("M14 42 L42 62 L70 42", null, { strokeWidth: 1.8 });
    [[60, 22], [74, 28], [84, 40], [80, 56], [88, 68], [70, 14], [90, 24]].forEach(([x, y], i) => p.ell(x, y, 8, 6, INK, { strokeWidth: 1, roughness: 0.6 }));
    p.sparkle(46, 22, 9);
  },
  bento(p) {
    p.rr(8, 28, 84, 52, 8, "#e9c58c");
    p.line(52, 30, 52, 78, { strokeWidth: 1.6 });
    p.poly([[30, 36], [46, 68], [14, 68]], C.white);
    p.rect(23, 58, 14, 10, INK, { strokeWidth: 1 });
    p.rr(58, 34, 28, 14, 5, C.yellow);
    p.ell(72, 64, 28, 12, C.coral);
  },
  book(p) {
    p.path("M50 30 Q32 20 12 26 V78 Q32 72 50 82 Z", C.white);
    p.path("M50 30 Q68 20 88 26 V78 Q68 72 50 82 Z", C.white);
    p.text(31, 60, "?", 28, C.coral);
    p.line(58, 42, 80, 39, { strokeWidth: 1.4 }); p.line(58, 52, 80, 49, { strokeWidth: 1.4 }); p.line(58, 62, 80, 59, { strokeWidth: 1.4 });
  },
  piano(p) {
    p.rr(8, 34, 84, 40, 4, C.white);
    for (let i = 1; i < 7; i++) p.line(8 + i * 12, 36, 8 + i * 12, 72, { strokeWidth: 1.4 });
    [1, 2, 4, 5, 6].forEach((i) => p.rect(8 + i * 12 - 4, 34, 8, 22, INK, { strokeWidth: 1, roughness: 0.5 }));
    p.path("M70 26 v-16 l12 -3 v14", null, { strokeWidth: 2 }); p.ell(66, 26, 9, 7, INK, { strokeWidth: 1 }); p.ell(78, 22, 9, 7, INK, { strokeWidth: 1 });
  },
  docs(p) {
    p.poly([[22, 30], [70, 24], [76, 84], [28, 90]], C.lav);
    p.poly([[16, 24], [64, 22], [66, 84], [18, 86]], C.pink);
    p.rect(26, 12, 50, 66, C.white);
    p.text(51, 33, "PEP", 15, C.magenta);
    [42, 51, 60, 69].forEach((y) => p.line(33, y, 69, y, { strokeWidth: 1.5 }));
  },
  network(p) {
    const nodes = [[50, 50, 22, C.teal], [24, 28, 12, C.magenta], [78, 24, 13, C.purple], [84, 64, 11, C.yellow], [22, 74, 13, C.magenta], [54, 86, 10, C.teal], [12, 50, 8, C.purple], [60, 16, 8, C.yellow], [40, 20, 7, C.teal], [90, 44, 7, C.purple], [36, 90, 7, C.yellow]];
    const edges = [[0, 1], [0, 2], [0, 3], [0, 4], [0, 5], [1, 6], [2, 7], [1, 8], [2, 9], [3, 9], [4, 10], [5, 10], [4, 6], [8, 7]];
    edges.forEach(([a, b]) => p.line(nodes[a][0], nodes[a][1], nodes[b][0], nodes[b][1], { strokeWidth: 1.5 }));
    nodes.forEach(([x, y, d, f]) => p.circ(x, y, d, f, { strokeWidth: 1.6 }));
  },
  map(p) {
    p.poly([[8, 26], [34, 16], [64, 26], [92, 16], [92, 76], [64, 86], [34, 76], [8, 86]], C.cream);
    p.line(34, 16, 34, 76, { strokeWidth: 1.5 }); p.line(64, 26, 64, 86, { strokeWidth: 1.5 });
    p.curve([[18, 70], [30, 52], [46, 60], [56, 44], [74, 46]], { stroke: C.magenta, strokeWidth: 2.4, strokeLineDash: [5, 5] });
    p.path("M76 44 Q64 26 76 20 Q88 26 76 44 Z", C.coral);
    p.circ(76, 28, 5, C.white, { strokeWidth: 1.2 });
    p.path("M14 64 l8 8 M22 64 l-8 8", null, { stroke: C.magenta, strokeWidth: 2.4 });
  },
  robot(p) {
    p.line(50, 22, 50, 10, { strokeWidth: 2 }); p.circ(50, 8, 8, C.yellow);
    p.rr(24, 22, 52, 38, 8, C.lav);
    p.circ(39, 39, 10, C.white); p.circ(61, 39, 10, C.white); p.dot(40, 40, 4); p.dot(60, 40, 4);
    p.path("M42 51 q8 5 16 0", null, { strokeWidth: 1.8 });
    p.rr(32, 64, 36, 26, 5, C.teal);
    p.line(32, 70, 18, 80, { strokeWidth: 2.4 }); p.line(68, 70, 84, 60, { strokeWidth: 2.4 });
    p.sparkle(88, 50, 8); p.sparkle(12, 24, 6);
  },
  tomb(p) {
    p.path("M30 86 V42 Q30 16 50 16 Q70 16 70 42 V86 Z", C.gray);
    p.rect(20, 84, 60, 9, "#a9a59d");
    p.text(50, 50, "LT", 17, INK);
    p.line(80, 84, 84, 60, { stroke: C.leaf, strokeWidth: 2 }); p.circ(85, 56, 10, C.magenta, { strokeWidth: 1.4 });
    p.line(14, 84, 12, 66, { stroke: C.leaf, strokeWidth: 2 }); p.circ(12, 62, 9, C.yellow, { strokeWidth: 1.4 });
  },
  browser(p) {
    p.rr(6, 14, 88, 72, 6, C.white);
    p.line(6, 28, 94, 28, { strokeWidth: 1.6 });
    [14, 22, 30].forEach((x, i) => p.circ(x, 21, 5, [C.coral, C.yellow, C.green][i], { strokeWidth: 1 }));
    const ns = [[26, 52, 12, C.teal], [16, 40, 6, C.magenta], [38, 40, 7, C.purple], [18, 70, 7, C.yellow], [40, 70, 6, C.magenta]];
    ns.slice(1).forEach(([x, y]) => p.line(26, 52, x, y, { strokeWidth: 1.2 }));
    ns.forEach(([x, y, d, f]) => p.circ(x, y, d, f, { strokeWidth: 1.2 }));
    p.rect(52, 36, 34, 8, C.pink, { strokeWidth: 1.2 });
    [52, 60, 68, 76].forEach((y) => p.line(52, y, 86, y, { strokeWidth: 1.3 }));
  },
  coin(p) {
    p.circ(50, 52, 62, C.yellow); p.circ(50, 52, 46, "#ffe08a", { strokeWidth: 1.4 });
    p.text(50, 66, "¥", 38, INK);
  },
  plane(p) {
    p.poly([[46, 50], [30, 18], [42, 18], [66, 48]], C.sky);
    p.poly([[46, 58], [32, 86], [44, 86], [66, 58]], C.sky);
    p.poly([[12, 52], [4, 32], [14, 32], [26, 50]], C.orange);
    p.path("M8 52 L72 44 Q94 42 94 52 Q92 60 72 60 L8 60 Z", C.white);
    [40, 52, 64].forEach((x) => p.circ(x, 52, 5, C.navy, { strokeWidth: 1 }));
  },
  train(p) {
    p.line(2, 78, 98, 78, { strokeWidth: 2 });
    p.path("M6 34 H62 Q90 36 96 62 V68 H6 Z", C.white);
    p.path("M6 56 H93 L96 66 H6 Z", C.blue, { strokeWidth: 1.4 });
    [14, 30, 46].forEach((x) => p.rr(x, 40, 11, 10, 2, C.sky, { strokeWidth: 1.4 }));
    p.path("M66 40 Q80 42 86 52 H66 Z", C.sky, { strokeWidth: 1.4 });
    [22, 46, 76].forEach((x) => p.circ(x, 72, 9, INK, { strokeWidth: 1 }));
  },
  ferry(p) {
    p.rect(54, 14, 12, 16, C.orange);
    p.rect(32, 28, 40, 14, C.white);
    p.rect(20, 42, 62, 18, C.white);
    [28, 40, 52, 64].forEach((x) => p.circ(x, 51, 6, C.sky, { strokeWidth: 1.2 }));
    p.poly([[6, 60], [96, 60], [84, 82], [18, 82]], C.navy);
    p.curve([[2, 88], [14, 82], [26, 90], [38, 83], [50, 90], [62, 83], [74, 90], [86, 83], [98, 88]], { stroke: C.blue, strokeWidth: 2.6 });
  },
  nowifi(p) {
    p.path("M14 44 Q50 10 86 44", null, { strokeWidth: 4 });
    p.path("M26 56 Q50 34 74 56", null, { strokeWidth: 4 });
    p.path("M38 68 Q50 58 62 68", null, { strokeWidth: 4 });
    p.circ(50, 80, 9, INK);
    p.line(16, 14, 86, 90, { stroke: C.red, strokeWidth: 6 }); p.line(86, 14, 16, 90, { stroke: C.red, strokeWidth: 6 });
  },
  sleepless(p) {
    p.path("M78 8 Q62 14 66 30 Q72 42 88 36 Q74 34 72 24 Q72 14 78 8 Z", C.yellow);
    p.sparkle(50, 14, 5); p.sparkle(92, 50, 4);
    p.rr(6, 62, 88, 22, 5, C.sky);
    p.ell(26, 60, 30, 12, C.white);
    p.circ(28, 48, 26, C.skin);
    p.circ(23, 47, 9, C.white, { strokeWidth: 1.4 }); p.circ(34, 47, 9, C.white, { strokeWidth: 1.4 }); p.dot(23, 47, 3); p.dot(34, 47, 3);
    p.path("M24 56 q5 -3 9 0", null, { strokeWidth: 1.5 });
    p.path("M40 62 Q66 52 94 64", C.blue, { strokeWidth: 1.6 });
    p.line(8, 84, 8, 94, {}); p.line(92, 84, 92, 94, {});
  },
  suitcase(p) {
    p.path("M38 30 V12 H62 V30", null, { strokeWidth: 2.6 });
    p.rr(26, 30, 48, 56, 6, C.orange);
    p.line(40, 34, 40, 82, { strokeWidth: 1.6 }); p.line(60, 34, 60, 82, { strokeWidth: 1.6 });
    p.circ(36, 90, 8, INK, { strokeWidth: 1 }); p.circ(64, 90, 8, INK, { strokeWidth: 1 });
  },
  backpack(p) {
    p.path("M38 24 Q50 4 62 24", null, { strokeWidth: 2.6 });
    p.rr(24, 22, 52, 66, 14, C.blue);
    p.rr(32, 54, 36, 24, 5, C.sky);
    p.line(30, 40, 70, 40, { strokeWidth: 1.8 });
  },
  parcel(p) {
    p.poly([[14, 44], [30, 26], [84, 26], [68, 44]], "#e7c18b");
    p.poly([[68, 44], [84, 26], [84, 68], [68, 86]], "#c99a5e");
    p.rect(14, 44, 54, 42, "#d9ad72");
    p.line(41, 44, 41, 86, { strokeWidth: 1.6 }); p.line(41, 44, 57, 26, { strokeWidth: 1.6 });
    p.rect(20, 62, 16, 12, C.white, { strokeWidth: 1.3 });
  },
  hotel(p) {
    p.rect(24, 22, 52, 70, C.white);
    p.rect(30, 8, 40, 14, C.orange);
    p.text(50, 19.5, "HOTEL", 9.5, C.white);
    for (let r = 0; r < 3; r++) for (let c = 0; c < 3; c++) p.rect(31 + c * 14, 30 + r * 14, 9, 9, C.sky, { strokeWidth: 1.2 });
    p.rect(43, 74, 14, 18, C.brown, { strokeWidth: 1.4 });
  },
  torii(p) {
    p.rect(25, 34, 8, 54, C.red); p.rect(67, 34, 8, 54, C.red);
    p.rect(16, 42, 68, 7, C.red);
    p.path("M6 22 Q50 12 94 22 L90 33 Q50 24 10 33 Z", C.red);
    p.curve([[2, 92], [16, 86], [30, 93], [44, 86], [58, 93], [72, 86], [86, 93], [98, 88]], { stroke: C.blue, strokeWidth: 2.6 });
  },
  laptop(p) {
    p.rr(20, 22, 60, 42, 4, C.white);
    p.rect(26, 28, 48, 30, C.sky, { strokeWidth: 1.3 });
    p.poly([[12, 68], [88, 68], [94, 80], [6, 80]], C.gray);
  },
  standing(p) {
    p.circ(40, 20, 20, C.skin);
    p.path("M35 22 q5 3 10 0", null, { strokeWidth: 1.5 }); p.dot(36, 17, 2.6); p.dot(45, 17, 2.6);
    p.path("M32 32 Q40 28 50 32 L52 62 H30 Z", C.orange);
    p.line(36, 62, 34, 92, { strokeWidth: 3 }); p.line(46, 62, 48, 92, { strokeWidth: 3 });
    p.line(50, 40, 66, 52, { strokeWidth: 2.6 });
    p.poly([[60, 52], [86, 52], [90, 58], [58, 58]], C.gray);
    p.rect(64, 36, 22, 16, C.sky);
    p.line(74, 58, 74, 92, { strokeWidth: 2.4 });
    p.path("M8 30 q-4 6 0 12 M14 26 q-4 8 0 18", null, { strokeWidth: 1.5 });
  },
  stamp(p) {
    p.circ(50, 50, 78, null, { stroke: C.red, strokeWidth: 3.4 });
    p.circ(50, 50, 62, null, { stroke: C.red, strokeWidth: 1.6 });
    p.text(50, 62, "関門", 30, C.red);
  },
  building(p) {
    p.rect(30, 10, 40, 82, C.sky);
    for (let r = 0; r < 6; r++) p.line(32, 20 + r * 12, 68, 20 + r * 12, { strokeWidth: 1.2 });
    p.line(50, 12, 50, 90, { strokeWidth: 1.2 });
    p.line(6, 92, 94, 92, { strokeWidth: 2 });
    p.sparkle(82, 20, 8);
  },
  mic(p) {
    p.rr(36, 8, 28, 46, 14, C.coral);
    p.line(40, 24, 60, 24, { strokeWidth: 1.4 }); p.line(40, 34, 60, 34, { strokeWidth: 1.4 });
    p.path("M26 40 Q26 66 50 66 Q74 66 74 40", null, { strokeWidth: 2.6 });
    p.line(50, 66, 50, 86, { strokeWidth: 2.6 }); p.line(34, 88, 66, 88, { strokeWidth: 3 });
  },
  // ---- 会議全般で使える汎用イラスト ----
  calendar(p) {
    p.rr(14, 20, 72, 68, 6, C.white);
    p.path("M14 26 Q14 20 20 20 H80 Q86 20 86 26 V38 H14 Z", C.coral);
    p.line(32, 12, 32, 26, { strokeWidth: 3.4 }); p.line(68, 12, 68, 26, { strokeWidth: 3.4 });
    for (let r = 0; r < 3; r++) for (let c = 0; c < 4; c++) p.rect(22 + c * 15, 46 + r * 13, 9, 8, r === 1 && c === 2 ? C.yellow : C.cream, { strokeWidth: 1.1 });
  },
  check(p) {
    p.circ(50, 52, 74, C.green);
    p.path("M30 52 L45 67 L72 36", null, { stroke: C.white, strokeWidth: 8, roughness: 0.6 });
  },
  bulb(p) {
    [[50, 6, 50, 0], [20, 18, 14, 12], [80, 18, 86, 12], [10, 44, 2, 44], [90, 44, 98, 44]].forEach(([a, b, c, d]) => p.line(a, b, c, d, { strokeWidth: 2 }));
    p.path("M50 12 Q24 12 24 40 Q24 54 38 64 V72 H62 V64 Q76 54 76 40 Q76 12 50 12 Z", C.yellow);
    p.rect(39, 72, 22, 12, C.gray); p.line(42, 90, 58, 90, { strokeWidth: 3 });
    p.path("M42 46 L48 58 L52 46 L58 58", null, { strokeWidth: 1.8 });
  },
  target(p) {
    p.circ(46, 54, 76, C.white); p.circ(46, 54, 54, C.coral, { strokeWidth: 1.6 }); p.circ(46, 54, 32, C.white, { strokeWidth: 1.6 }); p.circ(46, 54, 12, C.coral, { strokeWidth: 1.4 });
    p.line(46, 54, 84, 16, { strokeWidth: 3 });
    p.poly([[84, 16], [96, 12], [92, 24]], C.yellow, { strokeWidth: 1.6 }); p.poly([[84, 16], [80, 6], [92, 12]], C.yellow, { strokeWidth: 1.6 });
  },
  chart(p) {
    p.line(12, 10, 12, 88, { strokeWidth: 2.6 }); p.line(12, 88, 94, 88, { strokeWidth: 2.6 });
    [[22, 60, C.sky], [42, 46, C.teal], [62, 32, C.yellow], [80, 18, C.coral]].forEach(([x, y, f]) => p.rect(x, y, 12, 88 - y, f, { strokeWidth: 1.6 }));
    p.curve([[20, 50], [44, 36], [64, 22], [90, 8]], { stroke: C.magenta, strokeWidth: 2.6 });
  },
  people(p) {
    [[24, 40, C.sky, C.brown], [76, 40, C.yellow, "#3a2a20"]].forEach(([x, y, shirt, hair]) => {
      p.path(`M${x - 18} 92 Q${x - 16} 64 ${x} 62 Q${x + 16} 64 ${x + 18} 92 Z`, shirt);
      p.circ(x, y + 6, 28, C.skin); p.path(`M${x - 13} ${y + 2} Q${x - 12} ${y - 12} ${x} ${y - 10} Q${x + 12} ${y - 12} ${x + 13} ${y + 2} Q${x} ${y - 6} ${x - 13} ${y + 2} Z`, hair, { strokeWidth: 1.4 });
    });
    p.path("M26 96 Q28 62 50 60 Q72 62 74 96 Z", C.coral);
    p.circ(50, 40, 34, C.skin); p.path("M34 36 Q34 18 50 20 Q66 18 66 36 Q50 26 34 36 Z", C.brown, { strokeWidth: 1.6 });
    p.dot(44, 42, 3.4); p.dot(56, 42, 3.4); p.path("M44 49 q6 5 12 0", null, { strokeWidth: 1.8 });
  },
  clock(p) {
    p.circ(50, 52, 78, C.white); p.circ(50, 52, 64, C.cream, { strokeWidth: 1.4 });
    [[50, 24], [78, 52], [50, 80], [22, 52]].forEach(([x, y]) => p.dot(x, y, 4));
    p.line(50, 52, 50, 32, { strokeWidth: 3.4 }); p.line(50, 52, 66, 60, { strokeWidth: 2.6 }); p.circ(50, 52, 6, C.coral, { strokeWidth: 1.2 });
  },
  flag(p) {
    p.line(22, 8, 22, 94, { strokeWidth: 3.6 });
    p.path("M22 12 Q44 2 60 14 Q74 24 90 14 V52 Q74 62 60 52 Q44 40 22 50 Z", C.coral);
    p.ell(22, 94, 26, 6, C.gray, { strokeWidth: 1.4 });
  },
  warning(p) {
    p.path("M50 10 Q54 10 57 16 L92 78 Q96 88 86 88 H14 Q4 88 8 78 L43 16 Q46 10 50 10 Z", C.yellow);
    p.line(50, 34, 50, 60, { strokeWidth: 6 }); p.circ(50, 74, 8, INK);
  },
  question(p) {
    p.rr(12, 12, 76, 62, 16, C.lav);
    p.poly([[30, 72], [26, 92], [48, 73]], C.lav);
    p.text(50, 62, "?", 52, C.purple);
  },
  note(p) {
    p.poly([[18, 12], [70, 12], [84, 26], [84, 90], [18, 90]], C.cream);
    p.poly([[70, 12], [70, 26], [84, 26]], C.yellow, { strokeWidth: 1.6 });
    [38, 50, 62, 74].forEach((y) => p.line(28, y, 74, y, { strokeWidth: 1.5 }));
    p.path("M62 86 L92 50 L98 56 L68 92 L60 94 Z", C.orange, { strokeWidth: 1.6 });
  },
  rocket(p) {
    p.path("M50 6 Q72 26 70 62 H30 Q28 26 50 6 Z", C.white);
    p.circ(50, 36, 16, C.sky); p.poly([[30, 50], [14, 72], [30, 66]], C.coral); p.poly([[70, 50], [86, 72], [70, 66]], C.coral);
    p.rect(36, 62, 28, 8, C.gray, { strokeWidth: 1.6 });
    p.path("M40 72 Q50 98 60 72 Q50 82 40 72 Z", C.yellow, { strokeWidth: 1.6 });
  },
  // 人物(発表者は誰か特定の似顔絵ではなく記号的な顔)
  face(p, hair, shirt, style) {
    p.path("M14 98 Q16 72 50 70 Q84 72 86 98 Z", shirt);
    p.circ(50, 44, 52, C.skin);
    if (style === "long") {
      p.path("M22 50 Q16 10 50 12 Q84 10 78 50 Q76 30 62 26 Q44 34 28 28 Q22 36 22 50 Z", hair);
      p.path("M22 48 Q14 70 24 80 Q28 64 26 50 Z", hair); p.path("M78 48 Q86 70 76 80 Q72 64 74 50 Z", hair);
    } else if (style === "bob") {
      p.path("M20 54 Q14 10 50 12 Q86 10 80 54 Q78 34 70 28 Q50 24 30 30 Q22 38 20 54 Z", hair);
    } else {
      p.path("M24 40 Q22 14 50 14 Q78 14 76 40 Q66 26 50 28 Q34 26 24 40 Z", hair);
    }
    p.dot(40, 46, 4); p.dot(60, 46, 4);
    p.path("M40 57 q10 8 20 0", null, { strokeWidth: 2 });
    p.ell(32, 54, 8, 5, C.pink, { stroke: "none", roughness: 0.5 }); p.ell(68, 54, 8, 5, C.pink, { stroke: "none", roughness: 0.5 });
  },
  sloth(p) {
    p.path("M14 98 Q16 74 50 72 Q84 74 86 98 Z", C.orange);
    p.ell(50, 44, 66, 58, "#b48a62");
    p.ell(50, 47, 50, 42, C.sand);
    p.path("M26 40 Q34 34 44 44 Q38 54 28 50 Z", "#a07a55", { strokeWidth: 1.4 });
    p.path("M74 40 Q66 34 56 44 Q62 54 72 50 Z", "#a07a55", { strokeWidth: 1.4 });
    p.dot(37, 45, 5); p.dot(63, 45, 5);
    p.ell(50, 52, 11, 8, "#3a2a20", { strokeWidth: 1 });
    p.path("M40 58 q10 8 20 0", null, { strokeWidth: 2 });
  },
};

function icon(name, size, seed, ...args) {
  const svg = document.createElementNS(NS, "svg");
  svg.setAttribute("viewBox", "0 0 100 100");
  svg.setAttribute("width", size); svg.setAttribute("height", size);
  svg.classList.add("ico");
  svg.style.overflow = "visible";
  ICONS[name](new Pen(svg, seed || 7), ...args);
  return svg;
}

// <i data-ico="name" data-s="80" data-a="arg1,arg2"> を置き換える
function mountIcons(root) {
  (root || document).querySelectorAll("i[data-ico]").forEach((el, i) => {
    const a = (el.dataset.a || "").split(",").filter(Boolean).map((s) => C[s] || s);
    const svg = icon(el.dataset.ico, +el.dataset.s || 64, +(el.dataset.seed || i * 13 + 5), ...a);
    if (el.dataset.rot) svg.style.transform = `rotate(${el.dataset.rot}deg)`;
    svg.setAttribute("class", "ico " + el.className);
    if (el.getAttribute("style")) svg.setAttribute("style", svg.getAttribute("style") + ";" + el.getAttribute("style"));
    el.replaceWith(svg);
  });
}

// data-box="色" の要素の背面に手描きの枠を敷く
function mountBoxes(root) {
  (root || document).querySelectorAll("[data-box]").forEach((el, i) => {
    const w = el.offsetWidth, h = el.offsetHeight;
    const svg = document.createElementNS(NS, "svg");
    svg.setAttribute("width", w + 16); svg.setAttribute("height", h + 16);
    svg.style.cssText = "position:absolute;left:-8px;top:-8px;z-index:0;overflow:visible;pointer-events:none";
    const p = new Pen(svg, 100 + i * 7);
    const [fill, stroke, kind] = el.dataset.box.split(",");
    const f = fill === "none" ? null : PAL[fill] ? PAL[fill].tint : C[fill] || fill;
    const o = { stroke: stroke ? (PAL[stroke] ? PAL[stroke].hex : C[stroke] || stroke) : INK, strokeWidth: +(el.dataset.sw || 3), roughness: +(el.dataset.rough || 0.7) };
    if (el.dataset.hachure) Object.assign(o, { fillStyle: "hachure", hachureGap: 5, fillWeight: 1.6 });
    if (kind === "ell") p.ell(8 + w / 2, 8 + h / 2, w + 6, h + 6, f, o);
    else if (kind === "under") p.line(8, h + 6, w + 8, h + 6, o);
    else p.rr(8, 8, w, h, +(el.dataset.r || 12), f, o);
    if (getComputedStyle(el).position === "static") el.style.position = "relative";
    el.prepend(svg);
  });
}

// 手描き矢印: <svg class="arrow" data-pts="x,y x,y x,y" data-c="coral">
function mountArrows(root) {
  (root || document).querySelectorAll("svg[data-pts]").forEach((svg, i) => {
    const pts = svg.dataset.pts.split(" ").map((s) => s.split(",").map(Number));
    const p = new Pen(svg, 300 + i * 11);
    const col = PAL[svg.dataset.c] ? PAL[svg.dataset.c].hex : C[svg.dataset.c] || svg.dataset.c || INK;
    const sw = +(svg.dataset.sw || 3);
    p.curve(pts, { stroke: col, strokeWidth: sw, roughness: 0.8 });
    const [x2, y2] = pts[pts.length - 1], [x1, y1] = pts[pts.length - 2];
    const a = Math.atan2(y2 - y1, x2 - x1), L = +(svg.dataset.head || 14);
    const h = (d) => [x2 - L * Math.cos(a + d), y2 - L * Math.sin(a + d)];
    const [ax, ay] = h(0.5), [bx, by] = h(-0.5);
    p.path(`M${ax} ${ay} L${x2} ${y2} L${bx} ${by}`, null, { stroke: col, strokeWidth: sw, roughness: 0.6 });
  });
}
