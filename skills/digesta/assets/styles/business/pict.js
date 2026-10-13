// business スタイルの部品。線画のピクトグラム(単色・直線)と、枠・矢印の描画。
// doodle スタイルと同じ関数名(ICONS / icon / mountIcons / mountBoxes / mountArrows / PAL)を持ち、cards.html / frame.html / grareco.html から同じ書き方で使える。
// 会議ごとの追加ピクトグラムは digest/icons.js に Object.assign(ICONS, { 名前(p) { ... } }) の形で書く。
const NS = "http://www.w3.org/2000/svg";
const INK = "#1f3a5f";
// 章のテーマ色。hex は見出しや番号、tint は薄い帯
const PAL = {
  coral: { hex: "#b5443a", tint: "#f6e4e2" }, magenta: { hex: "#8a3b6e", tint: "#f1e3ec" }, orange: { hex: "#b86a1c", tint: "#f8ebdc" },
  teal: { hex: "#1f7a6e", tint: "#dcefeb" }, blue: { hex: "#2f5f9e", tint: "#dfe8f4" }, purple: { hex: "#5b4a9e", tint: "#e6e2f2" }, green: { hex: "#3b7a3f", tint: "#e0eedf" },
};
const C = new Proxy({ ink: INK, gray: "#8a949e", light: "#dfe3e8", white: "#ffffff", accent: "#2f5f9e", warn: "#b5443a", ok: "#1f7a6e" }, { get: (o, k) => (k in o ? o[k] : undefined) });  // doodle の色名(C.coral など)は undefined になり、塗りなしとして扱われる

class Pen {
  constructor(svg, color) { this.svg = svg; this.color = color || INK; }
  add(el) { this.svg.appendChild(el); return el; }
  mk(tag, attrs, fill) {
    const el = document.createElementNS(NS, tag);
    for (const k in attrs) el.setAttribute(k, attrs[k]);
    el.setAttribute("stroke", this.color); el.setAttribute("stroke-width", attrs["stroke-width"] || 4);
    el.setAttribute("stroke-linecap", "round"); el.setAttribute("stroke-linejoin", "round");
    el.setAttribute("fill", fill || "none");
    return this.add(el);
  }
  rect(x, y, w, h, r, fill) { return this.mk("rect", { x, y, width: w, height: h, rx: r || 0 }, fill); }
  circ(cx, cy, r, fill) { return this.mk("circle", { cx, cy, r }, fill); }
  line(x1, y1, x2, y2, w) { return this.mk("line", { x1, y1, x2, y2, "stroke-width": w || 4 }); }
  path(d, fill, w) { return this.mk("path", { d, "stroke-width": w || 4 }, fill); }
  poly(pts, fill) { return this.mk("polygon", { points: pts.map((p) => p.join(",")).join(" ") }, fill); }
  dot(cx, cy, r) { const d = this.circ(cx, cy, r || 3, this.color); d.setAttribute("stroke", "none"); return d; }
  // doodle スタイルの icons.js(会議ごとの追加イラスト)も動くようにする互換メソッド。塗りは無視して単色の線画にする
  rr(x, y, w, h, r) { return this.rect(x, y, w, h, Math.min(r || 0, 6)); }
  ell(cx, cy, w, h) { return this.mk("ellipse", { cx, cy, rx: w / 2, ry: h / 2 }); }
  curve(pts) { return this.path("M" + pts.map((q) => q.join(" ")).join(" L")); }
  sparkle(x, y, s) { return this.path(`M${x} ${y - s} L${x} ${y + s} M${x - s} ${y} L${x + s} ${y}`, null, 2.5); }
  steam(x, y) { return this.path(`M${x} ${y} Q${x - 4} ${y - 7} ${x + 3} ${y - 13} T${x - 2} ${y - 20}`, null, 2.5); }
  text(x, y, s, size, weight) {
    const t = document.createElementNS(NS, "text");
    t.setAttribute("x", x); t.setAttribute("y", y); t.setAttribute("font-size", size || 14); t.setAttribute("fill", this.color);
    t.setAttribute("text-anchor", "middle"); t.setAttribute("font-family", "BIZ UDPGothic, sans-serif"); t.setAttribute("font-weight", typeof weight === "number" ? weight : 700); t.setAttribute("stroke", "none");
    t.textContent = s; return this.add(t);
  }
}

const ICONS = {
  // 会議全般
  calendar(p) { p.rect(14, 22, 72, 66, 4); p.line(14, 40, 86, 40); p.line(32, 12, 32, 30); p.line(68, 12, 68, 30); [[30, 54], [50, 54], [70, 54], [30, 72], [50, 72]].forEach(([x, y]) => p.dot(x, y, 3.5)); },
  check(p) { p.circ(50, 50, 38); p.path("M30 52 L44 66 L72 36", null, 6); },
  bulb(p) { p.path("M50 10 Q26 10 26 36 Q26 50 38 60 V70 H62 V60 Q74 50 74 36 Q74 10 50 10 Z"); p.line(40, 80, 60, 80); p.line(44, 90, 56, 90); },
  target(p) { p.circ(50, 50, 38); p.circ(50, 50, 24); p.dot(50, 50, 7); },
  chart(p) { p.line(14, 12, 14, 88); p.line(14, 88, 90, 88); p.rect(26, 56, 12, 32, 0); p.rect(46, 40, 12, 48, 0); p.rect(66, 24, 12, 64, 0); },
  trend(p) { p.line(14, 12, 14, 88); p.line(14, 88, 90, 88); p.path("M22 74 L40 56 L56 64 L84 28"); p.path("M70 28 H84 V42"); },
  people(p) { p.circ(34, 34, 12); p.circ(66, 34, 12); p.path("M12 86 Q12 58 34 58 Q46 58 52 66"); p.path("M48 66 Q54 58 66 58 Q88 58 88 86"); },
  person(p) { p.circ(50, 32, 16); p.path("M20 90 Q20 60 50 60 Q80 60 80 90"); },
  clock(p) { p.circ(50, 50, 38); p.path("M50 28 V50 L66 60"); },
  flag(p) { p.line(22, 10, 22, 92); p.path("M22 16 H80 L68 36 L80 56 H22"); },
  warning(p) { p.path("M50 12 L92 84 H8 Z"); p.line(50, 40, 50, 62, 6); p.dot(50, 74, 4); },
  question(p) { p.rect(12, 14, 76, 56, 6); p.path("M28 70 L22 90 L46 70"); p.text(50, 54, "?", 36); },
  note(p) { p.path("M20 10 H66 L82 26 V90 H20 Z"); p.path("M66 10 V26 H82"); [40, 54, 68].forEach((y) => p.line(32, y, 70, y)); },
  rocket(p) { p.path("M50 8 Q70 28 68 64 H32 Q30 28 50 8 Z"); p.circ(50, 38, 8); p.path("M32 50 L18 70 H32"); p.path("M68 50 L82 70 H68"); p.path("M42 64 L50 90 L58 64"); },
  doc(p) { p.path("M22 10 H64 L78 24 V90 H22 Z"); [36, 50, 64, 78].forEach((y, i) => p.line(34, y, i === 3 ? 54 : 66, y)); },
  gear(p) { p.circ(50, 50, 14); for (let i = 0; i < 8; i++) { const a = (i * Math.PI) / 4; p.line(50 + 26 * Math.cos(a), 50 + 26 * Math.sin(a), 50 + 38 * Math.cos(a), 50 + 38 * Math.sin(a), 8); } p.circ(50, 50, 28); },
  cloud(p) { p.path("M26 74 Q8 74 10 56 Q12 42 28 42 Q32 20 54 22 Q72 22 76 40 Q92 40 90 58 Q90 74 74 74 Z"); },
  server(p) { p.rect(16, 14, 68, 22, 3); p.rect(16, 40, 68, 22, 3); p.rect(16, 66, 68, 22, 3); [25, 51, 77].forEach((y) => p.dot(28, y, 3.5)); },
  laptop(p) { p.rect(20, 20, 60, 42, 3); p.path("M10 74 H90 L84 84 H16 Z"); },
  phone(p) { p.rect(30, 8, 40, 84, 6); p.line(44, 80, 56, 80); },
  mail(p) { p.rect(10, 22, 80, 56, 4); p.path("M10 26 L50 56 L90 26"); },
  chat(p) { p.rect(10, 14, 56, 40, 6); p.path("M20 54 L16 70 L36 54"); p.path("M46 46 H90 V84 H78 L72 94 L66 84 H46 Z"); },
  search(p) { p.circ(42, 42, 26); p.line(62, 62, 88, 88, 7); },
  money(p) { p.rect(8, 26, 84, 50, 4); p.circ(50, 51, 12); p.dot(22, 51, 3); p.dot(78, 51, 3); },
  home(p) { p.path("M12 50 L50 14 L88 50"); p.path("M22 44 V88 H78 V44"); p.rect(42, 62, 16, 26, 0); },
  wrench(p) { p.path("M62 10 Q84 12 86 34 L46 74 L26 94 L6 74 L26 54 L66 14 Z"); p.circ(72, 26, 7); },
  shield(p) { p.path("M50 8 L86 22 Q86 70 50 92 Q14 70 14 22 Z"); p.path("M34 50 L46 62 L68 38", null, 5); },
  arrow(p) { p.line(12, 50, 84, 50, 6); p.path("M62 28 L86 50 L62 72", null, 6); },
  cycle(p) { p.path("M78 40 A30 30 0 0 0 24 34"); p.path("M22 60 A30 30 0 0 0 76 66"); p.path("M22 22 V36 H36"); p.path("M78 78 V64 H64"); },
  thermo(p) { p.rect(38, 8, 24, 56, 12); p.circ(50, 76, 16); p.line(50, 30, 50, 70, 8); },
  pin(p) { p.path("M50 92 Q22 60 22 40 Q22 12 50 12 Q78 12 78 40 Q78 60 50 92 Z"); p.circ(50, 40, 10); },
  mic(p) { p.rect(36, 8, 28, 46, 14); p.path("M24 44 Q24 70 50 70 Q76 70 76 44"); p.line(50, 70, 50, 86); p.line(34, 88, 66, 88); },
  list(p) { [24, 50, 76].forEach((y) => { p.dot(20, y, 5); p.line(34, y, 84, y); }); },
  numbered(p) { p.rect(10, 12, 80, 76, 4); [32, 50, 68].forEach((y, i) => { p.text(24, y + 6, String(i + 1), 16); p.line(36, y, 78, y); }); },
};

function icon(name, size, _seed, color) {
  const svg = document.createElementNS(NS, "svg");
  svg.setAttribute("viewBox", "0 0 100 100"); svg.setAttribute("width", size); svg.setAttribute("height", size);
  svg.classList.add("ico"); svg.style.overflow = "visible";
  (ICONS[name] || ICONS.doc)(new Pen(svg, color));
  return svg;
}

// <i data-ico="名前" data-s="大きさ" data-c="色"> を置き換える。data-a(doodle の顔の引数)は無視する
function mountIcons(root) {
  (root || document).querySelectorAll("i[data-ico]").forEach((el) => {
    if (el.dataset.ico === "face" || el.dataset.ico === "sloth") { el.remove(); return; }  // 人物は出さない
    const svg = icon(el.dataset.ico, +el.dataset.s || 48, 0, el.dataset.c ? (PAL[el.dataset.c] ? PAL[el.dataset.c].hex : el.dataset.c) : INK);
    svg.setAttribute("class", "ico " + el.className);
    if (el.getAttribute("style")) svg.setAttribute("style", svg.getAttribute("style") + ";" + el.getAttribute("style"));
    el.replaceWith(svg);
  });
}

// data-box="塗り,線" の要素に、直線の枠を付ける(doodle と同じ属性名で、CSS の枠に変換する)
function mountBoxes(root) {
  (root || document).querySelectorAll("[data-box]").forEach((el) => {
    const [fill, stroke, kind] = el.dataset.box.split(",");
    const f = fill === "none" ? "transparent" : PAL[fill] ? PAL[fill].tint : fill === "pink" ? "#f6e4e2" : fill;
    const s = stroke === "none" ? "transparent" : stroke ? (PAL[stroke] ? PAL[stroke].hex : stroke) : C.light;
    el.style.background = f;
    if (kind === "under") el.style.borderBottom = `2px solid ${s}`;
    else { el.style.border = `${el.dataset.sw ? Math.min(+el.dataset.sw, 2) : 1.5}px solid ${s}`; el.style.borderRadius = (el.dataset.r ? Math.min(+el.dataset.r, 6) : 4) + "px"; }
  });
}

// <svg data-pts="x,y x,y" data-c="色"> に直線の矢印を描く
function mountArrows(root) {
  (root || document).querySelectorAll("svg[data-pts]").forEach((svg) => {
    const pts = svg.dataset.pts.split(" ").map((s) => s.split(",").map(Number));
    const col = PAL[svg.dataset.c] ? PAL[svg.dataset.c].hex : svg.dataset.c || INK;
    const p = new Pen(svg, col);
    p.path("M" + pts.map((q) => q.join(" ")).join(" L"), null, +(svg.dataset.sw || 3));
    const L = +(svg.dataset.head || 12);
    if (L > 0) {
      const [x2, y2] = pts[pts.length - 1], [x1, y1] = pts[pts.length - 2], a = Math.atan2(y2 - y1, x2 - x1);
      p.path(`M${x2 - L * Math.cos(a + 0.5)} ${y2 - L * Math.sin(a + 0.5)} L${x2} ${y2} L${x2 - L * Math.cos(a - 0.5)} ${y2 - L * Math.sin(a - 0.5)}`, null, +(svg.dataset.sw || 3));
    }
  });
}
