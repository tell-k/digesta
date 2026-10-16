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
                                      会議フォルダに vtt / srt(Teams などの字幕)があれば、文字起こしせずにその発話の時刻を使う
                                      vtt / srt がなく、Teams の文字起こし docx を取り込んであれば、その発話の時刻を使う(開始だけで秒単位)
                                      (単語の時刻はない。カット点と字幕を決める区間だけ --asr を付けて起こし直す)
  show <dir> 205 [250-270] ...        保存済みの区間を表示する。「開始秒 範囲」の形で、その時刻範囲の文だけに絞れる
  find <dir> 語 語 ...                保存済みの全区間から、語を含む文を時刻付きで探す(全文を読まずに候補を見つける)
  words <dir> <区間の開始秒> <a> <b>   a〜b 秒の単語ごとの時刻を表示する(長い発話を字幕に分けるとき)
  check-narration <dir>               ナレーション音声を文字起こしして原稿と並べる(読み間違いの確認)
                                      external_api: allow なら Gemini で聞き取る(ローカルの CPU を使わない)。--local でローカル
  check-video <dir>                   クリップの切れ目で音が途切れていないかを、元の録画の音量で調べる(文字起こしはしない。数秒で終わる)
                                      疑わしい切れ目と、近くの無音の時刻を表示する。動画を作る前でも使える
  check-video <dir> --asr             完成動画のクリップの境目(前後 4 秒)を文字起こしし、字幕の先頭と末尾の語が聞き取れているかを調べる
                                      (聞き取りは digest/work/digest_asr.txt。--print で全文も。--reuse で前の聞き取りを使う)

出力は会話に流す量を抑えてある。全文が必要なときだけ --print を付けるか、保存されたファイルを部分的に読む。
文字起こしの結果は digest/work/asr_cache/ に残し、同じ音声・同じ設定なら起こし直さない(full は除く)。

Intel Mac では実時間より遅い(1分の音声に1分以上)。全編ではなく、候補区間だけを起こすこと。
1 本でコア数の半分(最大 6)のスレッドを使い、優先度を下げて動く。並行実行はしない(コアを奪い合ってかえって遅くなる)。
環境変数で変えられる: DIGESTA_ASR_THREADS(スレッド数)、DIGESTA_ASR_COMPUTE(int8 / float32。既定 int8)、
DIGESTA_ASR_DEVICE(既定は自動。NVIDIA の GPU で起こせれば cuda、だめなら cpu。cuda には CUDA 12 と cuDNN 9 が要り、
compute の既定は float16 になる。cpu にすると GPU の確認を省く)
"""
import json, os, re, subprocess, sys
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
    device = os.environ.get("DIGESTA_ASR_DEVICE") or ("cuda" if cuda_works() else "cpu")
    compute = os.environ.get("DIGESTA_ASR_COMPUTE", "int8" if device == "cpu" else "float16")
    threads = int(os.environ.get("DIGESTA_ASR_THREADS", max(1, min(6, (os.cpu_count() or 4) // 2))))
    lower_priority()
    return WhisperModel(MODEL, device=device, compute_type=compute, cpu_threads=threads)


def cuda_works():
    """NVIDIA の GPU で文字起こしできるか。GPU があっても CUDA 12 や cuDNN 9 のライブラリが欠けていると、
    起こし始めたところでプロセスごと落ちることがある。別のプロセスで 1 秒の無音を起こして確かめる"""
    import ctranslate2
    if ctranslate2.get_cuda_device_count() == 0:
        return False
    code = (f"import numpy, faster_whisper as f; m = f.WhisperModel({MODEL!r}, device='cuda', compute_type='float16'); "
            "list(m.transcribe(numpy.zeros(16000, numpy.float32), language='ja')[0])")
    try:
        r = subprocess.run([sys.executable, "-c", code], capture_output=True, encoding="utf-8", errors="replace", timeout=600, check=False)
        ok, why = r.returncode == 0, (r.stderr.strip().splitlines() or [f"終了コード {r.returncode}"])[-1]
    except subprocess.TimeoutExpired:
        ok, why = False, "確認が終わらない"
    print("GPU(cuda)で文字起こしする" if ok else f"GPU はあるが使えないので CPU で起こす(CUDA 12 と cuDNN 9 が要る): {why}", flush=True)
    return ok


ASR_CACHE = None  # main() が digest/work/asr_cache を入れる
_model = None


def transcribe(samples, **kw):
    """faster-whisper の transcribe。同じ音声・同じ設定で前に起こした結果があれば、それを返す(起こし直さない)。
    モデルは起こす必要が出たときに初めて読み込む。戻り値は Segment と同じく start / end / text / words を持つ"""
    import hashlib
    from types import SimpleNamespace as NS
    global _model
    h = hashlib.sha256(samples.tobytes())
    h.update(json.dumps([MODEL, os.environ.get("DIGESTA_ASR_DEVICE"), os.environ.get("DIGESTA_ASR_COMPUTE"), kw], ensure_ascii=False, sort_keys=True).encode())
    f = ASR_CACHE / f"{h.hexdigest()[:32]}.json" if ASR_CACHE else None
    if f and f.exists():
        rows = json.loads(f.read_text(encoding="utf-8"))
    else:
        if _model is None:
            _model = model()
        segs, _ = _model.transcribe(samples, **kw)
        rows = [[s.start, s.end, s.text, [[w.start, w.end, w.word] for w in s.words or []]] for s in segs]
        if f:
            f.parent.mkdir(parents=True, exist_ok=True); f.write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")
    return [NS(start=a, end=b, text=t, words=[NS(start=x, end=y, word=w) for x, y, w in ws]) for a, b, t, ws in rows]


def lower_priority():
    """文字起こし中も他のアプリが固まらないよう、このプロセスの優先度を下げる"""
    try:
        if os.name == "nt":
            import ctypes
            k = ctypes.windll.kernel32
            k.SetPriorityClass(k.GetCurrentProcess(), 0x4000)  # BELOW_NORMAL_PRIORITY_CLASS
        else:
            os.nice(10)
    except OSError:
        pass


def gemini_allowed(root):
    """会議の設定が external_api: allow で、Gemini のキーがあるか(digest.py の設定の読み方をそのまま使う)"""
    sys.path.insert(0, str(Path(__file__).parent))
    import digest
    return digest.Ep(root).cfg["external_api"] == "allow" and bool(digest.gemini_key_source()[0])


def gemini_transcribe(root, wavs):
    """{名前: wav} をまとめて 1 回の Gemini 呼び出しで聞き取り、{名前: 文} を返す(無料枠の回数を使わないよう 1 回にまとめる)"""
    import base64, urllib.error, urllib.request

    import digest
    ep = digest.Ep(root)
    ep.need_external("Gemini によるナレーションの聞き取り")
    parts = [{"text": "次の各音声を、聞こえたとおりに日本語で書き起こしてください。言い直しや読み間違いも直さずに書きます。"
                      "結果は {\"名前\": \"書き起こし\"} の JSON だけを返します。"}]
    for name, wav in wavs.items():
        parts += [{"text": f"名前: {name}"}, {"inline_data": {"mime_type": "audio/wav", "data": base64.b64encode(wav.read_bytes()).decode()}}]
    body = {"contents": [{"parts": parts}], "generationConfig": {"responseMimeType": "application/json", "temperature": 0}}
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{ep.cfg['gemini_asr_model']}:generateContent"
    req = urllib.request.Request(url, data=json.dumps(body).encode(), headers={"x-goog-api-key": digest.gemini_key(), "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=600) as r:
            res = json.load(r)
    except urllib.error.HTTPError as e:
        sys.exit(f"Gemini の聞き取り HTTP {e.code}: {e.read().decode()[:600]}(--local でローカルの文字起こしに切り替えられる)")
    return json.loads("".join(p.get("text", "") for p in res["candidates"][0]["content"]["parts"]))


def captions(root):
    """会議フォルダの vtt / srt の発話を [開始秒, 終了秒, 話者, 文] のリストで返す。
    なければ、取り込んだ Teams の docx(digest/work/transcript_*.md)の発話を使う。どちらもなければ None"""
    fs = sorted(p for p in root.iterdir() if p.suffix.lower() in (".vtt", ".srt"))
    if not fs:
        return teams_docx(root)
    out = []
    for f in fs:
        for block in re.split(r"\n\s*\n", f.read_text(encoding="utf-8", errors="replace").replace("\r", "")):
            m = re.search(r"(?:(\d{1,2}):)?(\d{2}):(\d{2})[.,](\d+) *--> *(?:(\d{1,2}):)?(\d{2}):(\d{2})[.,](\d+)", block)
            if not m:
                continue
            g = m.groups()
            a = int(g[0] or 0) * 3600 + int(g[1]) * 60 + int(g[2]) + float("0." + g[3])
            b = int(g[4] or 0) * 3600 + int(g[5]) * 60 + int(g[6]) + float("0." + g[7])
            body = " ".join(l.strip() for l in block[m.end():].split("\n")[1:] if l.strip())
            v = re.search(r"<v ([^>]+)>", body)
            text = re.sub(r"</?[^>]+>", "", body).strip()
            who = v.group(1) if v else ""
            if not v and (sp := re.match(r"^([^:：]{1,30})[:：] *(.*)$", text)):
                who, text = sp.groups()
            if text:
                out.append([round(a, 2), round(b, 2), who, text])
    return sorted(out)


def teams_docx(root):
    """Teams の文字起こし docx を pandoc で取り込んだ md(「話者** 1:23」の行のあとに発言が続く)の発話を
    [開始秒, 終了秒, 話者, 文] で返す。docx の時刻は発言の開始だけで秒単位なので、終了は次の発言の開始にする"""
    rows = []
    for f in sorted((root / "digest/work").glob("transcript_*.md")):
        lines = f.read_text(encoding="utf-8", errors="replace").splitlines()
        for i, line in enumerate(lines):
            m = re.match(r"^(.+?)\*\* (\d+(?::\d{2}){1,2})\\?$", line.strip())
            if not m:
                continue
            body = []
            for l in lines[i + 1:]:
                if not l.strip() or "**" in l:
                    break
                body.append(l.strip().rstrip("\\").strip())
            who = re.sub(r"!\[[^\]]*\]\([^)]*\)(\{[^}]*\})?|\*", "", m.group(1)).strip()
            t = 0
            for x in m.group(2).split(":"):
                t = t * 60 + int(x)
            if body:
                rows.append([t, who, " ".join(body)])
    if not rows:
        return None
    rows.sort(key=lambda r: r[0])
    return [[float(a), float(rows[i + 1][0] if i + 1 < len(rows) else a + 30), who, text] for i, (a, who, text) in enumerate(rows)]


def joined(pieces, **kw):
    """短い音声片をまとめて 1 回で文字起こしし、元の時刻の [開始, 終了, 語] を返す。
    Whisper は 30 秒に満たない入力も 30 秒ぶん計算するので、片ごとに起こすと数倍遅い。片の間に 1.5 秒の無音を挟んで 1 本にする"""
    import numpy as np
    gap = np.zeros(24000, dtype=np.float32)
    buf, table, pos = [], [], 0.0
    for t0, x in pieces:
        table.append((pos, pos + len(x) / 16000, t0)); buf += [x, gap]; pos += (len(x) + len(gap)) / 16000
    if not buf:
        return []
    segs = transcribe(np.concatenate(buf), language="ja", word_timestamps=True, vad_filter=True,
                      vad_parameters={"min_silence_duration_ms": 500}, condition_on_previous_text=False, **kw)
    out = []
    for s in segs:
        for w in s.words:
            mid = (w.start + w.end) / 2
            for a, b, t0 in table:
                if a - 0.3 <= mid <= b + 0.3:
                    out.append((round(t0 + w.start - a, 2), round(t0 + w.end - a, 2), w.word)); break
    return out


def glossary_terms(root):
    """用語集の語。プロジェクト(../digesta.md)と会議フォルダ(digesta.md)の「## 用語集」節を合わせる。
    行頭の「- 」が語、その子の箇条の「聞き違い:」を見る。同じ語は会議フォルダのものが勝つ"""
    rows = {}
    for local, f in ((False, root.parent / "digesta.md"), (True, root / "digesta.md")):
        if not f.exists():
            continue
        on, term = False, None
        for line in re.sub(r"<!--.*?-->", "", f.read_text(encoding="utf-8"), flags=re.S).splitlines():
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
            m = re.match(r"^---\n(.*?)\n---\n", f.read_text(encoding="utf-8"), re.S)
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
        for s in json.load(open(work / "win" / f"{a}.json", encoding="utf-8")):
            if lo is None or (s["end"] >= lo and s["start"] <= hi):
                print(f"{s['start']:8.2f}-{s['end']:8.2f} {s['who'] + ': ' if s.get('who') else ''}{s['text']}")


def norm(t):
    import unicodedata
    return re.sub(r"[^0-9A-Za-z\u3040-\u30ff\u4e00-\u9fff]", "", unicodedata.normalize("NFKC", t))


def plain(wav):
    return transcribe(audio(wav), language="ja", vad_filter=True, condition_on_previous_text=False)


def cut_edges(work, starts, cuts):
    """クリップの切れ目で音が途切れていないかを、元の録画の音声(audio16k.wav)の音量で調べる。文字起こしはしない。
    切れ目の前後 30 ミリ秒がずっと鳴っていれば(周りの発話の大きさから DIP dB 以内)、語の途中で切れている疑いとする。
    VAD は文の間の短い間(ま)も発話の続きとみなすので使わない。字幕の文と聞き取りも比べないので、言い回しを整えた字幕でも誤検出にならない"""
    import wave

    import numpy as np
    DIP, QUIET = -15.0, -30.0  # 鳴っているとみなす音量、無音とみなす音量(どちらも周りの発話の大きさとの差 dB)
    with wave.open(str(work / "audio16k.wav")) as f:
        sr = f.getframerate()
        x = np.frombuffer(f.readframes(f.getnframes()), dtype=np.int16).astype(np.float32) / 32768.0

    def db(t):  # t の前後 15 ミリ秒の音量(dBFS)
        seg = x[max(0, int((t - 0.015) * sr)):max(1, int((t + 0.015) * sr))]
        return 20 * np.log10(np.sqrt(np.mean(seg ** 2)) + 1e-9)

    total, bad = 0, []
    for c in cuts:
        for t, topic in enumerate(c.get("topics") or []):
            name = f"t{c['chapter']}{t}"
            o = starts.get(name)
            for cl in topic.get("clips") or []:
                a, b = float(cl["start"]), float(cl["end"])
                subs = cl.get("subs") or []
                for kind, e, sub in (("頭", a, subs[:1]), ("終わり", b, subs[-1:])):
                    total += 1
                    level = np.percentile([db(u) for u in np.arange(e - 2, e + 2, 0.02)], 90)  # 周りの発話の大きさ
                    gap = min(db(e + d) for d in (-0.03, -0.015, 0, 0.015, 0.03)) - level
                    if gap < DIP or level < -50:  # 間で切れている、または周りが無音
                        continue
                    near = [u for u in np.arange(-1.0, 1.0, 0.01) if db(e + u) - level < QUIET]
                    before = max((u for u in near if u < 0), default=None)
                    after = min((u for u in near if u > 0), default=None)
                    at = f"動画 {o + (0 if kind == '頭' else b - a):7.2f}" if o is not None else "動画 -"
                    bad.append(f"  {at} [{name}] クリップの{kind}({e:.2f} 秒)で音が途切れている({gap:+.0f} dB)。近くの無音: "
                               + " / ".join(f"{e + u:.2f}" for u in (before, after) if u is not None)
                               + (f" / 字幕「{str(sub[0][2]).replace(chr(92) + 'N', ' ')[:40]}」" if sub else ""))
                if o is not None:
                    o += b - a
    print(f"クリップの切れ目 {total} か所を元の録画の音量で調べた(文字起こしはしない)。音の途中で切れている疑い {len(bad)} か所")
    print("\n".join(bad))
    if bad:
        print("疑いの多くは耳では問題ない(切れ目にフェードが掛かるので、音の途中で切ってもなじむ)。耳で確かめ、気になる箇所だけ近くの無音(前 / 後)に start / end を移す。語を足すなら外側、前の人の言いかけを落とすなら内側")


def main():
    for f in (sys.stdout, sys.stderr):  # Windows のパイプ出力は既定が cp932 で、日本語の一部の文字で落ちる。UTF-8 にそろえる
        f.reconfigure(encoding="utf-8", errors="replace")
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    cmd, root, args = sys.argv[1], Path(sys.argv[2]).resolve(), sys.argv[3:]
    work = root / "digest/work"
    global ASR_CACHE
    ASR_CACHE = work / "asr_cache"
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
            blocks = [b for b in dst.read_text(encoding="utf-8").split("\n\n") if b.strip()]
            stamps = [re.match(r"^\[(\d+):(\d+):(\d+)\]", b) for b in blocks]
            if blocks and stamps[-1]:
                h, m_, sec = (int(x) for x in stamps[-1].groups())
                offset, kept = h * 3600 + m_ * 60 + sec, blocks[:-1]
                print(f"続きから起こす: {offset // 60}分{offset % 60:02d}秒から(やり直すなら --force)", flush=True)
        samples = audio(work / "audio16k.wav")[offset * 16000:]
        segs, _ = model().transcribe(samples, language="ja", vad_filter=True, condition_on_previous_text=False, initial_prompt=prompt_of(root))
        with open(dst, "w", encoding="utf-8") as f:
            f.write("".join(b + "\n\n" for b in kept)); f.flush()
            for s in segs:
                t = offset + int(s.start)
                f.write(f"[{t // 3600:02d}:{t % 3600 // 60:02d}:{t % 60:02d}] {s.text.strip()}\n\n"); f.flush()
        done.write_text("", encoding="utf-8")
        print(dst, "(話者の区別はない)")
    elif cmd == "windows":
        (work / "win").mkdir(parents=True, exist_ok=True)
        caps = None if "--asr" in sys.argv else captions(root)
        args = [x for x in args if not x.startswith("--")]
        if caps:
            print("vtt / srt(なければ Teams の docx)の発話の時刻を使う(文字起こしはしない。単語の時刻が要る区間は --asr で起こし直す)")
            for w in args:
                a, b = (int(x) for x in w.split("-"))
                out = [{"start": s, "end": e, "who": who, "text": t, "words": []} for s, e, who, t in caps if e >= a and s <= b]
                (work / "win" / f"{a}.json").write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")
                (work / "win" / f"{a}-{b}.txt").write_text("".join(f"{s['start']:8.2f}-{s['end']:8.2f} {s['who'] + ': ' if s['who'] else ''}{s['text']}\n" for s in out), encoding="utf-8")
                if "--print" in sys.argv:
                    show(work, [str(a)])
                else:
                    print(f"{a}-{b}: {len(out)} 文 → {work / 'win' / f'{a}-{b}.txt'}")
            return
        hint = prompt_of(root)
        for w in args:
            a, b = (int(x) for x in w.split("-"))
            wav = work / "win" / f"{a}.wav"
            subprocess.run(["ffmpeg", "-v", "error", "-ss", str(a), "-t", str(b - a), "-i", str(work / "audio16k.wav"), "-y", str(wav)], check=True)
            segs = transcribe(audio(wav), language="ja", word_timestamps=True, vad_filter=True, vad_parameters={"min_silence_duration_ms": 300},
                              condition_on_previous_text=False, initial_prompt=hint)
            out = [{"start": round(a + s.start, 2), "end": round(a + s.end, 2), "text": s.text.strip(),
                    "words": [[round(a + x.start, 2), round(a + x.end, 2), x.word] for x in s.words]} for s in segs]
            json.dump(out, open(work / "win" / f"{a}.json", "w", encoding="utf-8"), ensure_ascii=False)
            (work / "win" / f"{a}-{b}.txt").write_text("".join(f"{s['start']:8.2f}-{s['end']:8.2f} {s['text']}\n" for s in out), encoding="utf-8")
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
            for s in json.load(open(f, encoding="utf-8")):
                if any(w in s["text"] or norm(w) in norm(s["text"]) for w in words):
                    print(f"{s['start']:8.2f}-{s['end']:8.2f} {s['who'] + ': ' if s.get('who') else ''}{s['text']}"); hits += 1
        print(f"{hits} 件(区間 {', '.join(p.stem for p in sorted((work / 'win').glob('*.json'), key=lambda p: int(p.stem)))} から)")
    elif cmd == "words":
        w, a, b = args[0], float(args[1]), float(args[2])
        if not any(s["words"] for s in json.loads((work / "win" / f"{w}.json").read_text(encoding="utf-8"))):
            sys.exit(f"区間 {w} には単語の時刻がない(vtt / srt / docx から作った区間)。windows <dir> <区間> --asr で起こし直す")
        print(" ".join(f"{ws:.2f}|{t}" for s in json.load(open(work / "win" / f"{w}.json", encoding="utf-8")) for ws, we, t in s["words"] if a <= ws <= b))
    elif cmd == "check-narration":
        text = re.sub(r"<!--.*?-->", "", (root / "digest/narration.md").read_text(encoding="utf-8"), flags=re.S)
        cards = {n: " ".join(b.split()) for n, b in re.findall(r"^## +(\S+)[^\n]*\n(.*?)(?=^## |\Z)", text, re.S | re.M) if n != "読み"}
        if "--local" not in sys.argv and gemini_allowed(root):
            heard = gemini_transcribe(root, {n: work / "narr" / f"{n}.wav" for n in cards if (work / "narr" / f"{n}.wav").exists()})
            for name, src in cards.items():
                print(f"{name}\n  原稿: {src}\n  聞取: {heard.get(name, '(音声なし)')}", flush=True)
            print("聞き取りは Gemini。漢字や英字の表記が原稿と違って当然。読み(音)が違う箇所だけを問題にする")
            return
        for name, src in cards.items():
            wav = work / "narr" / f"{name}.wav"
            if not wav.exists():
                print(f"{name}: 音声なし"); continue
            print(f"{name}\n  原稿: {src}\n  聞取: {''.join(s.text for s in plain(wav))}", flush=True)
        print("聞き取りは漢字や英字の表記が原稿と違って当然。読み(音)が違う箇所だけを問題にする")
    elif cmd == "check-video":
        # 部品(timeline.txt の行)の開始秒。動画を作る前は timeline.txt がない(切れ目の検査は元の録画で見るので、動画の時刻を出さないだけ)
        tl = work / "timeline.txt"
        starts = {m.group(3): int(m.group(1)) * 60 + float(m.group(2))
                  for m in re.finditer(r"^\s*(\d+):(\d\d\.\d\d)\s+(\S+) \(([\d.]+)s\)", tl.read_text(encoding="utf-8") if tl.exists() else "", re.M)}
        # 欠けが起きるのはクリップの境目だけ。動画上のクリップの区間 [開始, 終了] を部品ごとに求める(digest.py は clips を単純につなぐ)
        clips, cuts = {}, yaml.safe_load((root / "digest/cuts.yaml").read_text(encoding="utf-8")) or []
        for c in cuts:
            for t, topic in enumerate(c.get("topics") or []):
                name = f"t{c['chapter']}{t}"
                if name not in starts or not topic.get("clips"):
                    continue
                o = starts[name]
                for cl in topic["clips"]:
                    d = float(cl["end"]) - float(cl["start"]); clips.setdefault(name, []).append((o, o + d)); o += d
        if "--asr" not in sys.argv:
            cut_edges(work, starts, cuts)
            return
        if not tl.exists():
            sys.exit("--asr は完成動画を聞くので、先に動画を作る(digest/work/timeline.txt がない)")
        E = 4.0  # 境目の前後に起こす秒数
        if "--reuse" in sys.argv and (work / "digest_asr.txt").exists():  # 聞き取りをやり直さず、保存済みの結果で照合だけする
            heard = [(float(m.group(1)), float(m.group(2)), m.group(3)) for m in re.finditer(r"^\s*([\d.]+)-\s*([\d.]+) (.*)$", (work / "digest_asr.txt").read_text(encoding="utf-8"), re.M)]
        else:
            spans = sorted(x for cs in clips.values() for a, b in cs for x in ([(a, b)] if b - a <= 2 * E + 1 else [(a, a + E), (b - E, b)]))
            merged = []
            for a, b in spans:
                if merged and a <= merged[-1][1] + 0.5:
                    merged[-1][1] = max(merged[-1][1], b)
                else:
                    merged.append([a, b])
            samples = audio(work / "digest.mp4")
            print(f"クリップ {sum(map(len, clips.values()))} 本の境目、計 {sum(b - a for a, b in merged):.0f} 秒を文字起こしする", flush=True)
            heard = joined([(a, samples[int(a * 16000):int(b * 16000)]) for a, b in merged])
            (work / "digest_asr.txt").write_text("".join(f"{a:7.2f}-{b:7.2f} {t}\n" for a, b, t in heard), encoding="utf-8")
        if "--print" in sys.argv:
            print("".join(f"{a:7.2f}-{b:7.2f} {t}\n" for a, b, t in heard), end="")
        # 字幕(work/seg/t*.ass)の先頭・末尾の語が、その時刻の聞き取りに含まれるかを調べる。含まれなければ欠けの疑い
        def sec(x):
            h, mi, se = x.split(":"); return int(h) * 3600 + int(mi) * 60 + float(se)
        total, bad = 0, []
        for name, off in starts.items():
            ass = work / "seg" / f"{name}.ass"
            if not ass.exists() or name not in clips:
                continue
            for line in ass.read_text(encoding="utf-8").splitlines():
                if not line.startswith("Dialogue:"):
                    continue
                p = line.split(",", 9); a, b = off + sec(p[1]), off + sec(p[2])
                text = re.sub(r"\{[^}]*\}", "", p[9]).replace("\\N", " ")
                text = re.sub(r"^\s*[QA]\.\s*", "", text)
                text = re.sub(r"[(（][^)）]*[)）]", "", text)  # 丸括弧の補足は字幕で足したものなので、音にはない
                n = norm(text)
                # 先頭はクリップの頭から、末尾はクリップの終わりまで、起こした範囲(E 秒)に入っている字幕だけを見る
                ends = [k for k, ok in (("先頭", any(ca - 0.1 <= a <= ca + E - 1.0 for ca, cb in clips[name])),
                                        ("末尾", any(cb - E + 1.0 <= b <= cb + 0.1 for ca, cb in clips[name]))) if ok]
                if len(n) < 4 or not ends:
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
                miss = [k for k, w in (("先頭", head), ("末尾", tail)) if k in ends and sim(w) < 0.6]
                if miss:
                    bad.append(f"  {a:7.2f}-{b:7.2f} [{name}] {'・'.join(miss)}が聞き取りにない: 字幕「{text.strip()}」/ 聞取「{''.join(t for s, e, t in heard if e >= a - 0.6 and s <= b + 0.6)[:60]}」")
        print(f"クリップの境目に掛かる字幕 {total} 本を照合(ナレーションは check-narration で見る)。欠けの疑い {len(bad)} 本(漢字の表記違いによる誤検出もある。疑いの箇所だけ耳か show で確かめる)")
        print("\n".join(bad))
        print(f"聞き取り: {work / 'digest_asr.txt'}")
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main()
