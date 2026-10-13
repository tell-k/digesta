#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# ///
"""このセッション(または指定した記録ファイル)のトークン使用量を集計する。

usage: uv run usage.py [セッションの .jsonl] [--since "依頼文の一部"]

  引数なし: ~/.claude/projects/<このプロジェクト>/ で最新の .jsonl を使う
  --since: その文字列を含む最初のユーザー発言以降だけを集計する(会議 1 回ぶんを切り出すとき)

金額は従量課金に換算した目安。単価は Opus 系(入力 $15 / キャッシュ書込 $18.75 / キャッシュ読出 $1.5 / 出力 $75、100 万トークンあたり)を仮定。
Max プランなら実際の請求はない。API キーなどの中身は読まない(usage の数値だけ見る)。
"""
import json, os, sys
from pathlib import Path

RATE = {"input_tokens": 15, "cache_creation_input_tokens": 18.75, "cache_read_input_tokens": 1.5, "output_tokens": 75}


def main():
    args = sys.argv[1:]
    since = None
    if "--since" in args:
        i = args.index("--since"); since = args[i + 1]; del args[i:i + 2]
    if args:
        f = Path(args[0])
    else:
        import re
        proj = Path.home() / ".claude/projects" / re.sub(r"[^A-Za-z0-9]", "-", str(Path.cwd()))
        cands = sorted(proj.glob("*.jsonl"), key=lambda p: p.stat().st_mtime) if proj.is_dir() else []
        if not cands:
            sys.exit(f"セッションの記録が見つからない: {proj}(cd でプロジェクトのフォルダに移動して実行する)")
        f = cands[-1]
    rows, start = [], None
    for line in open(f):
        try:
            r = json.loads(line)
        except Exception:
            continue
        m = r.get("message") or {}
        if since and start is None and r.get("type") == "user":
            c = m.get("content")
            text = c if isinstance(c, str) else " ".join(x.get("text", "") for x in c if isinstance(x, dict)) if isinstance(c, list) else ""
            if since in text:
                start = r.get("timestamp")
        if r.get("type") == "assistant" and "usage" in m:
            rows.append((r.get("timestamp"), m["usage"], m.get("model")))
    if since and start is None:
        sys.exit(f"「{since}」を含むユーザー発言が見つからない")
    sel = [x for x in rows if not since or (x[0] and x[0] >= start)]
    t = {k: sum((u.get(k) or 0) for _, u, _ in sel) for k in RATE}
    cost = sum(t[k] * RATE[k] for k in RATE) / 1e6
    ctx = (t["cache_read_input_tokens"] + t["cache_creation_input_tokens"] + t["input_tokens"]) / max(1, len(sel))
    print(f"記録: {f.name}" + (f"(「{since}」以降)" if since else ""))
    print(f"応答回数: {len(sel)}")
    for k, v in t.items():
        print(f"  {k:<28} {v:>12,}")
    print(f"1 応答あたりの文脈(読み直し): 約 {ctx:,.0f} トークン")
    print(f"従量換算の目安: ${cost:,.2f}(Opus 系の単価を仮定。Max プランなら請求なし)")
    print(f"モデル: {', '.join(sorted({mo for _, _, mo in sel if mo}))}")


if __name__ == "__main__":
    main()
