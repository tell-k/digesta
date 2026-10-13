#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11,<3.13"
# dependencies = ["faster-whisper>=1.1", "pyyaml>=6", "numpy"]
# ///
"""文字起こし(ローカルの faster-whisper)。カット点の特定と、作った音声の検証に使う。

usage: uv run asr.py <command> <会議のディレクトリ> [引数]

  full <dir> [--force]                全編を文字起こしして digest/work/transcript_asr.md に保存する(文字起こしがない録画用。遅い)
                                      途中で止めても、もう一度実行すれば続きから起こす。最初からやり直すなら --force

  windows <dir> 205-285 430-530 ...   元音声の指定区間(秒)を単語タイムスタンプ付きで文字起こしする
                                      結果は digest/work/win/<開始秒>.json と .txt に保存し、件数だけ表示する(--print で全文も)
  show <dir> 205 [250-270] ...        保存済みの区間を表示する。「開始秒 範囲」の形で、その時刻範囲の文だけに絞れる
  find <dir> 語 語 ...                保存済みの全区間から、語を含む文を時刻付きで探す(全文を読まずに候補を見つける)
  words <dir> <区間の開始秒> <a> <b>   a〜b 秒の単語ごとの時刻を表示する(長い発話を字幕に分けるとき)
  check-narration <dir>               ナレーション音声を文字起こしして原稿と並べる(読み間違いの確認)
  check-video <dir>                   完成動画の音声を文字起こしし、字幕の先頭と末尾の語が聞き取れているかを調べる
                                      疑わしい字幕だけを表示する(全文は digest/work/digest_asr.txt。--print で全文も)

出力は会話に流す量を抑えてある。全文が必要なときだけ --print を付けるか、保存されたファイルを部分的に読む。

Intel Mac では実時間より遅い(1分の音声に1分以上)。全編ではなく、候補区間だけを起こすこと。
区間が多いときは、このコマンドを2〜3個に分けて並行実行すると速い。
"""
import json, re, subprocess, sys
from pathlib import Path

import yaml

MODEL = "large-v3-turbo"


def audio(path):
    """音声を 16kHz モノラルの配列にして返す。faster-whisper 内蔵の読み込み(PyAV)は版によって動かないので、ffmpeg で読む"""
    import numpy as np
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-ac", "1", "-ar", "16000", "-f", "s16le", "-"], capture_output=True, check=True).stdout
    return np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0


def model():
    from faster_whisper import WhisperModel
    return WhisperModel(MODEL, device="cpu", compute_type="float32", cpu_threads=6)


def glossary_terms(root):
    """用語集の語。プロジェクト(../digesta.md)と会議フォルダ(digesta.md)の「## 用語集」節を合わせる。
    行頭の「- 」が語、その子の箇条の「聞き違い:」を見る。同じ語は会議フォルダのものが勝つ"""
    rows = {}
    for local, f in ((False, root.parent / "digesta.md"), (True, root / "digesta.md")):
        if not f.exists():
            continue
        on, term = False, None
        for line in re.sub(r"<!--.*?-->", "", f.read_text(), flags=re.S).splitlines():
            if re.match(r"^##\s", line):
                on = line[2:].strip().startswith("用語集")
                continue
            if not on:
                continue
            m = re.match(r"^- +(.+?)\s*$", line)
            if m:
                term = m.group(1); rows.pop(term, None); rows[term] = (local, False)
            elif term and re.match(r"^\s+[-*] +聞き違い\s*[:：]\s*\S", line):
                rows[term] = (local, True)
    # 切り捨てられにくい後ろ側に、会議フォルダの語、聞き違いの記録がある語を寄せる
    return [t for t, _ in sorted(rows.items(), key=lambda x: x[1])]


def prompt_of(root):
    """固有名詞のヒント。用語集の表記 + 会議の設定 asr_prompt(digesta.md。以前の置き場所 digest/rules.md も読む)"""
    own = None
    for f in (root / "digest/rules.md", root / "digesta.md"):
        if f.exists():
            m = re.match(r"^---\n(.*?)\n---\n", f.read_text(), re.S)
            if m:
                own = (yaml.safe_load(m.group(1)) or {}).get("asr_prompt", own)
    # Whisper が使うのは末尾の約 220 トークンだけ。会議の asr_prompt を最後に置き、重なる語は除く
    terms = [t for t in glossary_terms(root) if t not in (own or "")]
    return "、".join(terms) + "。" + (own or "") if terms else own


def show(work, starts):
    """show <dir> 205 [250-270]: 開始秒の区間を表示。次の引数が「a-b」なら、その時刻範囲の文だけ"""
    i = 0
    while i < len(starts):
        a = starts[i]; i += 1
        lo, hi = None, None
        if i < len(starts) and "-" in starts[i]:
            lo, hi = (float(x) for x in starts[i].split("-")); i += 1
        print(f"=== {a}" + (f" ({lo:g}-{hi:g})" if lo is not None else ""))
        for s in json.load(open(work / "win" / f"{a}.json")):
            if lo is None or (s["end"] >= lo and s["start"] <= hi):
                print(f"{s['start']:8.2f}-{s['end']:8.2f} {s['text']}")


def norm(t):
    import unicodedata
    return re.sub(r"[^0-9A-Za-z\u3040-\u30ff\u4e00-\u9fff]", "", unicodedata.normalize("NFKC", t))


def plain(m, wav):
    segs, _ = m.transcribe(audio(wav), language="ja", vad_filter=True, condition_on_previous_text=False)
    return list(segs)


def main():
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    cmd, root, args = sys.argv[1], Path(sys.argv[2]).resolve(), sys.argv[3:]
    work = root / "digest/work"
    if cmd == "full":
        # 途中で止めても、もう一度実行すれば続きから起こす(1 文ずつ書き出しているので、最後の文の頭からやり直す)。
        # 最初からやり直すなら --force。終わったら transcript_asr.done を置く
        dst, done = work / "transcript_asr.md", work / "transcript_asr.done"
        if "--force" in sys.argv:
            dst.unlink(missing_ok=True); done.unlink(missing_ok=True)
        if done.exists():
            sys.exit(f"{dst} は全編の文字起こしが済んでいる(やり直すなら --force)")
        kept, offset = [], 0
        if dst.exists():
            blocks = [b for b in dst.read_text().split("\n\n") if b.strip()]
            stamps = [re.match(r"^\[(\d+):(\d+):(\d+)\]", b) for b in blocks]
            if blocks and stamps[-1]:
                h, m_, sec = (int(x) for x in stamps[-1].groups())
                offset, kept = h * 3600 + m_ * 60 + sec, blocks[:-1]
                print(f"続きから起こす: {offset // 60}分{offset % 60:02d}秒から(やり直すなら --force)", flush=True)
        samples = audio(work / "audio16k.wav")[offset * 16000:]
        segs, _ = model().transcribe(samples, language="ja", vad_filter=True, condition_on_previous_text=False, initial_prompt=prompt_of(root))
        with open(dst, "w") as f:
            f.write("".join(b + "\n\n" for b in kept)); f.flush()
            for s in segs:
                t = offset + int(s.start)
                f.write(f"[{t // 3600:02d}:{t % 3600 // 60:02d}:{t % 60:02d}] {s.text.strip()}\n\n"); f.flush()
        done.write_text("")
        print(dst, "(話者の区別はない)")
    elif cmd == "windows":
        (work / "win").mkdir(parents=True, exist_ok=True)
        m, hint = model(), prompt_of(root)
        for w in args:
            a, b = (int(x) for x in w.split("-"))
            wav = work / "win" / f"{a}.wav"
            subprocess.run(["ffmpeg", "-v", "error", "-ss", str(a), "-t", str(b - a), "-i", str(work / "audio16k.wav"), "-y", str(wav)], check=True)
            segs, _ = m.transcribe(audio(wav), language="ja", word_timestamps=True, vad_filter=True, vad_parameters={"min_silence_duration_ms": 300},
                                   condition_on_previous_text=False, initial_prompt=hint)
            out = [{"start": round(a + s.start, 2), "end": round(a + s.end, 2), "text": s.text.strip(),
                    "words": [[round(a + x.start, 2), round(a + x.end, 2), x.word] for x in s.words]} for s in segs]
            json.dump(out, open(work / "win" / f"{a}.json", "w"), ensure_ascii=False)
            (work / "win" / f"{a}-{b}.txt").write_text("".join(f"{s['start']:8.2f}-{s['end']:8.2f} {s['text']}\n" for s in out))
            wav.unlink()
            if "--print" in sys.argv:
                show(work, [str(a)])
            else:
                print(f"{a}-{b}: {len(out)} 文 → {work / 'win' / f'{a}-{b}.txt'}(find <語> で探す、show {a} <a-b> で範囲を読む)")
    elif cmd == "show":
        show(work, [x for x in args if x != "--print"])
    elif cmd == "find":
        words = [w for w in args if not w.startswith("--")]
        hits = 0
        for f in sorted((work / "win").glob("*.json"), key=lambda p: int(p.stem)):
            for s in json.load(open(f)):
                if any(w in s["text"] or norm(w) in norm(s["text"]) for w in words):
                    print(f"{s['start']:8.2f}-{s['end']:8.2f} {s['text']}"); hits += 1
        print(f"{hits} 件(区間 {', '.join(p.stem for p in sorted((work / 'win').glob('*.json'), key=lambda p: int(p.stem)))} から)")
    elif cmd == "words":
        w, a, b = args[0], float(args[1]), float(args[2])
        print(" ".join(f"{ws:.2f}|{t}" for s in json.load(open(work / "win" / f"{w}.json")) for ws, we, t in s["words"] if a <= ws <= b))
    elif cmd == "check-narration":
        text = re.sub(r"<!--.*?-->", "", (root / "digest/narration.md").read_text(), flags=re.S)
        cards = {n: " ".join(b.split()) for n, b in re.findall(r"^## +(\S+)[^\n]*\n(.*?)(?=^## |\Z)", text, re.S | re.M) if n != "読み"}
        m = model()
        for name, src in cards.items():
            wav = work / "narr" / f"{name}.wav"
            if not wav.exists():
                print(f"{name}: 音声なし"); continue
            print(f"{name}\n  原稿: {src}\n  聞取: {''.join(s.text for s in plain(m, wav))}", flush=True)
        print("聞き取りは漢字や英字の表記が原稿と違って当然。読み(音)が違う箇所だけを問題にする")
    elif cmd == "check-video":
        mp4 = work / "digest.mp4"
        wav = work / "digest16k.wav"
        if "--reuse" in sys.argv and (work / "digest_asr.txt").exists():  # 聞き取りをやり直さず、保存済みの結果で照合だけする
            heard = [(float(m.group(1)), float(m.group(2)), m.group(3)) for m in re.finditer(r"^\s*([\d.]+)-\s*([\d.]+) (.*)$", (work / "digest_asr.txt").read_text(), re.M)]
        else:
            subprocess.run(["ffmpeg", "-v", "error", "-i", str(mp4), "-vn", "-ac", "1", "-ar", "16000", "-y", str(wav)], check=True)
            heard = [(s.start, s.end, s.text.strip()) for s in plain(model(), wav)]
            wav.unlink()
            (work / "digest_asr.txt").write_text("".join(f"{a:7.2f}-{b:7.2f} {t}\n" for a, b, t in heard))
        if "--print" in sys.argv:
            print("".join(f"{a:7.2f}-{b:7.2f} {t}\n" for a, b, t in heard), end="")
        # 字幕(work/seg/t*.ass)の先頭・末尾の語が、その時刻の聞き取りに含まれるかを調べる。含まれなければ欠けの疑い
        starts = {}
        for m in re.finditer(r"^\s*(\d+):(\d\d\.\d\d)\s+(\S+) ", (work / "timeline.txt").read_text(), re.M):
            starts[m.group(3)] = int(m.group(1)) * 60 + float(m.group(2))
        def sec(x):
            h, mi, se = x.split(":"); return int(h) * 3600 + int(mi) * 60 + float(se)
        total, bad = 0, []
        for name, off in starts.items():
            ass = work / "seg" / f"{name}.ass"
            if not ass.exists():
                continue
            for line in ass.read_text().splitlines():
                if not line.startswith("Dialogue:"):
                    continue
                p = line.split(",", 9); a, b = off + sec(p[1]), off + sec(p[2])
                text = re.sub(r"\{[^}]*\}", "", p[9]).replace("\\N", " ")
                text = re.sub(r"^\s*[QA]\.\s*", "", text)
                text = re.sub(r"[(（][^)）]*[)）]", "", text)  # 丸括弧の補足は字幕で足したものなので、音にはない
                n = norm(text)
                if len(n) < 4:
                    continue
                total += 1
                h = norm("".join(t for s, e, t in heard if e >= a - 0.8 and s <= b + 0.8))
                # 字幕は言い回しを整えてあるので厳密には一致しない。先頭・末尾 6 文字と、聞き取りの部分文字列との類似度で判定する
                import difflib
                def sim(w):
                    if not w: return 1.0
                    best = 0.0
                    for L in (len(w) - 1, len(w), len(w) + 1):
                        for i in range(0, max(1, len(h) - L + 1)):
                            best = max(best, difflib.SequenceMatcher(None, w, h[i:i + L]).ratio())
                    return best
                head, tail = n[:6], n[-6:]
                miss = [k for k, w in (("先頭", head), ("末尾", tail)) if sim(w) < 0.6]
                if miss:
                    bad.append(f"  {a:7.2f}-{b:7.2f} [{name}] {'・'.join(miss)}が聞き取りにない: 字幕「{text.strip()}」/ 聞取「{''.join(t for s, e, t in heard if e >= a - 0.6 and s <= b + 0.6)[:60]}」")
        print(f"字幕 {total} 本を照合。欠けの疑い {len(bad)} 本(漢字の表記違いによる誤検出もある。疑いの箇所だけ耳か show で確かめる)")
        print("\n".join(bad))
        print(f"全文: {work / 'digest_asr.txt'}")
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main()
