// この会議だけの追加イラスト(mono 用)。lib/mono.js の sloth と checklist は色が3色に寄っていないので、ここで描き直す
Object.assign(ICONS, {
  checklist(p) {
    p.rr(16, 14, 52, 74, 5, C.white);
    p.rr(32, 7, 20, 12, 3, C.yellow);
    for (let i = 0; i < 3; i++) {
      const y = 36 + i * 15;
      p.path(`M23 ${y} l4 5 l8 -10`, null, { stroke: C.coral, strokeWidth: 3 });
      p.line(40, y, 60, y, { strokeWidth: 1.8 });
    }
    p.circ(70, 64, 28, "rgba(238,238,238,0.8)");
    p.line(80, 75, 93, 90, { strokeWidth: 5 });
  },
  sloth(p) {
    p.path("M14 98 Q16 74 50 72 Q84 74 86 98 Z", C.yellow);
    p.ell(50, 44, 66, 58, "#9a9a9a");
    p.ell(50, 47, 50, 42, "#eeeeee");
    p.path("M26 40 Q34 34 44 44 Q38 54 28 50 Z", "#6b6b6b", { strokeWidth: 1.4 });
    p.path("M74 40 Q66 34 56 44 Q62 54 72 50 Z", "#6b6b6b", { strokeWidth: 1.4 });
    p.dot(37, 45, 5); p.dot(63, 45, 5);
    p.ell(50, 52, 11, 8, "#2b2b2b", { strokeWidth: 1 });
    p.path("M40 58 q10 8 20 0", null, { strokeWidth: 2 });
  },
});
