#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["pyyaml>=6", "playwright>=1.45", "pillow>=10"]
# ///
"""会議の録画と文字起こしから、議事録・グラレコ画像・ダイジェスト動画を作るビルドツール。

usage: uv run digest.py <command> <会議のディレクトリ> [options]

  init       digest/ のひな形を作り、音声抽出と文字起こしの取り込みをする
  minutes    digest/minutes.md を output/ に出す                     [--format md|docx|both]
  sheet      元動画のコンタクトシート(全体像の把握用)を作る          [--step 秒]
  grid       指定秒のフレームにグリッドを重ねて出す(クロップ座標の特定用)  秒 ...
  crop       指定秒のフレームから画面共有の領域を自動で検出し、crop の値を出す    秒 ...
  frames     完成動画の確認用に、区切りごとのフレームを 1 枚の一覧にする         [--all]
  plan       episode.yaml / cuts.yaml / narration.md を検査し、ビルド前に尺の見積もりを出す
  image      digest/grareco.html を描画して output/ に PNG を出す           [--split]
             --split で、章ごとのパネル(.panel / .col)も 16:9 の画像(<名前>_グラレコ_章N.png)に切り出す(Slack にスレッドで貼る用)
  narration  digest/narration.md から音声を合成する                  [--only 名前,名前] [--force]
  bgm        BGM を生成する                                          [--force]
  video      動画を作る(変わった部分だけ作り直す)                      [--force] [--no-bgm]
  voices     声のサンプルを作る                                      声の名前 ...
  chars      digest/chars.yaml のキャラクター画像を Gemini で生成する     [--only 名前,名前] [--force]
  status     設定と、各成果物が最新かどうかを表示する

人が編集するのは digest/ 直下のテキスト(minutes.md / narration.md / cuts.yaml / episode.yaml / grareco.html / icons.js)と、
設定・ルール・人名と用語の用語集を書く digesta.md(プロジェクト直下と会議フォルダ。会議のほうが優先)。
digest/lib と digest/work は自動生成なので編集しない。
"""
import argparse, base64, hashlib, json, math, os, re, shutil, subprocess, sys, urllib.error, urllib.parse, urllib.request
from pathlib import Path

import yaml

SKILL = Path(__file__).resolve().parent.parent
FONT_CACHE = Path.home() / ".cache/digesta/fonts"
VIDEO_EXT, AUDIO_EXT = (".mp4", ".mov", ".m4v", ".mkv", ".webm"), (".m4a", ".mp3", ".wav", ".aac")
STYLES = SKILL / "assets/styles"
DEFAULTS = {
    "style": "doodle",  # 見た目のスタイル。styles_path の各フォルダか assets/styles/ にあるフォルダ名(doodle / business / …)
    # 追加のスタイルを探すフォルダ。os.pathsep(":")区切りの文字列か YAML のリスト。相対パスはプロジェクトのフォルダ(会議の親)から。
    # 環境変数 DIGESTA_STYLES_PATH も同じ形式で足せる。同じ名前のスタイルは、設定 > 環境変数 > 同梱 の順に先に見つかったものを使う
    "styles_path": "",
    # 外部 API(Gemini TTS / Lyria)に原稿を送ってよいか。ask=未確認(使おうとすると止まる)、allow=送ってよい、deny=送らない(say と BGM なしに切り替える)
    "external_api": "ask",
    "minutes_format": "md",  # 議事録の出力形式: md / docx / both
    "narration": "gemini",  # gemini / voicevox / say / none
    "voice": "Leda",  # gemini の声
    "voice_style": "a young woman in her early twenties narrating a friendly internal recap video in Japanese; bright, cheerful and natural, clear articulation, slightly brisk pace",
    "gemini_tts_model": "gemini-3.8-flash-tts",
    "image_model": "gemini-3.1-flash-image",  # キャラクター画像の生成に使うモデル
    "voicevox_speaker": 2,  # 四国めたん(ノーマル)
    "say_voice": "Kyoko",
    "bgm": "lyria",  # lyria / none / 音声ファイルのパス(会議のディレクトリからの相対)
    "bgm_model": "lyria-3.5",
    "bgm_gain": 0.166,  # BGM の基準音量。-12 LUFS 前後の曲を約 -28 LUFS に下げる値
    "bgm_prompt": "",  # 空ならスタイルの既定(style.yaml)を使う
    "clean_audio": True,  # 元音声の整音(低域カット・軽いノイズ除去・軽いコンプレッサー)
    "credit": "",  # 締めカードの最下部に出す表記。voicevox を使うなら必須(例: ナレーション VOICEVOX:四国めたん)
    "fps": 24,
    "asr_prompt": "",  # 文字起こしに渡す固有名詞のヒント(asr.py が使う)
    "output_dir": "output",
}
# 合成は RGB で行い、最後に一度だけ bt709 リミテッドレンジへ変換する(カードと本編で色を揃えるため)
RGB_IN = "in_color_matrix=bt709:in_range=tv:out_range=pc,format=gbrp"
TOYUV = "scale=out_color_matrix=bt709:out_range=tv,format=yuv420p"
TAG = ["-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709", "-color_range", "tv"]
CLEAN = "highpass=f=70,afftdn=nr=10:nf=-45:tn=1,acompressor=threshold=-21dB:ratio=2.5:attack=8:release=180:makeup=1.5"
ASS_HEAD = """[Script Info]
ScriptType: v4.00+
PlayResX: 1920
PlayResY: 1080
WrapStyle: 2

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Sub,{font},56,&H0022262B,&H0022262B,&H00FFFFFF,&H00000000,0,0,0,0,100,100,1,0,1,0,0,5,60,60,0,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""


# ---------- 共通 ----------
def die(msg):
    sys.exit("エラー: " + msg)


def run(cmd, cwd=None):
    r = subprocess.run([str(c) for c in cmd], capture_output=True, text=True, cwd=cwd)
    if r.returncode:
        die("コマンド失敗: " + " ".join(str(c) for c in cmd[:6]) + " …\n" + r.stderr[-3000:])
    return r


def dur_of(p):
    return float(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(p)]))


def ts(t):
    return f"{int(t // 60)}:{t % 60:05.2f}"


def ass_ts(t):
    return f"{int(t // 3600)}:{int(t % 3600 // 60):02d}:{t % 60:05.2f}"


def sha(*parts):
    h = hashlib.sha256()
    for p in parts:
        h.update(p if isinstance(p, bytes) else json.dumps(p, ensure_ascii=False, sort_keys=True, default=str).encode())
        h.update(b"\0")
    return h.hexdigest()[:20]


def fresh(path, key):
    """path が key と同じ入力から作られていれば True(作り直し不要)"""
    k = Path(str(path) + ".key")
    return Path(path).exists() and k.exists() and k.read_text() == key


def mark(path, key):
    Path(str(path) + ".key").write_text(key)


def style_dirs(setting, base):
    """スタイルを探すフォルダの一覧。設定 styles_path、環境変数 DIGESTA_STYLES_PATH、同梱の assets/styles の順"""
    items = setting if isinstance(setting, list) else str(setting or "").split(os.pathsep)
    items += os.environ.get("DIGESTA_STYLES_PATH", "").split(os.pathsep)
    dirs = [(base / Path(i).expanduser()).resolve() for i in map(str.strip, map(str, items)) if i]
    return list(dict.fromkeys(dirs + [STYLES]))


def frontmatter(path):
    """Markdown 冒頭の --- で挟んだ YAML を dict で返す"""
    if not path.exists():
        return {}
    s = path.read_text()
    m = re.match(r"^---\n(.*?)\n---\n", s, re.S)
    return (yaml.safe_load(m.group(1)) or {}) if m else {}


def glossary_terms(ep):
    """プロジェクトと会議フォルダの用語集を合わせて {表記: 語} で返す。同じ語は会議フォルダのものが丸ごと勝つ
    (読みを書かずに語だけ書けば、その会議ではプロジェクトの読み替えを止められる)"""
    return {**{r["表記"]: r for r in glossary(ep.digesta)}, **{r["表記"]: r for r in glossary(ep.digesta_local)}}


def glossary(path):
    """digesta.md の「## 用語集」節を [{表記, 読み, 聞き違い, メモ}] で返す。
    行頭の「- 」が語。その子の箇条の「読み:」「聞き違い:」が値、それ以外の子の箇条がメモ"""
    if not path.exists():
        return []
    rows, on = [], False
    for line in re.sub(r"<!--.*?-->", "", path.read_text(), flags=re.S).splitlines():
        if re.match(r"^##\s", line):
            on = line[2:].strip().startswith("用語集")
            continue
        if not on:
            continue
        m = re.match(r"^- +(.+?)\s*$", line)
        if m:
            rows.append({"表記": m.group(1), "読み": "", "聞き違い": "", "メモ": ""})
            continue
        m = re.match(r"^\s+[-*] +(.+?)\s*$", line)
        if m and rows:
            k = re.match(r"^(読み|聞き違い)\s*[:：]\s*(.*)$", m.group(1))
            if k:
                rows[-1][k.group(1)] = k.group(2)
            else:
                rows[-1]["メモ"] = (rows[-1]["メモ"] + " " + m.group(1)).strip()
    return rows


class Ep:
    """会議1回分のディレクトリ"""

    def __init__(self, d):
        self.root = Path(d).resolve()
        if not self.root.is_dir():
            die(f"ディレクトリがない: {d}")
        self.name = self.root.name
        self.digest = self.root / "digest"
        self.lib = self.digest / "lib"
        self.work = self.digest / "work"
        # 設定・ルール・用語集のファイル: プロジェクト共通(../digesta.md)と、会議ごと(digesta.md)
        self.digesta = self.root.parent / "digesta.md"
        self.digesta_local = self.root / "digesta.md"
        # 設定: 既定 < プロジェクト共通(../digesta.md) < 会議(digesta.md)
        # ../digest-rules.md と digest/rules.md は以前の置き場所。あればそれぞれの層の下に読む
        self.cfg = {**DEFAULTS, **frontmatter(self.root.parent / "digest-rules.md"), **frontmatter(self.digesta),
                    **frontmatter(self.digest / "rules.md"), **frontmatter(self.digesta_local)}
        unknown = set(self.cfg) - set(DEFAULTS) - {"video"}
        if unknown:
            print("注意: 知らない設定キー(無視する):", ", ".join(sorted(unknown)))
        if self.cfg["external_api"] == "deny":  # 外部送信しない設定なら、ローカルで済む方法に切り替える
            if self.cfg["narration"] == "gemini":
                self.cfg["narration"] = "say"
            if self.cfg["bgm"] == "lyria":
                self.cfg["bgm"] = "none"
        self.out = self.root / self.cfg["output_dir"]
        self.fps = int(self.cfg["fps"])
        self.style_dirs = style_dirs(self.cfg["styles_path"], self.root.parent)
        self.style_dir = next((d / str(self.cfg["style"]) for d in self.style_dirs if (d / str(self.cfg["style"]) / "style.yaml").exists()), None)
        if not self.style_dir:
            names = sorted({p.name for d in self.style_dirs if d.is_dir() for p in d.iterdir() if (p / "style.yaml").exists()})
            die(f"スタイル '{self.cfg['style']}' がない。使えるのは: " + ", ".join(names) + "\n探したフォルダ: " + ", ".join(map(str, self.style_dirs)))
        self.style = yaml.safe_load((self.style_dir / "style.yaml").read_text()) or {}
        self.fonts = {k: tuple(v) for k, v in (self.style.get("fonts") or {}).items()}
        # 引用符なしの 0xf0f0f0 は YAML が整数(15790320)として読む。そのまま文字列にして ffmpeg に渡すと
        # 先頭6桁「157903」の濃い緑になり、カードの出入りが緑を経由していた。16進に戻して渡す
        paper = self.style.get("paper", "0xffffff")
        self.paper = f"0x{paper:06x}" if isinstance(paper, int) else str(paper)
        if not self.cfg["bgm_prompt"]:
            self.cfg["bgm_prompt"] = self.style.get("bgm_prompt", "")
        self.ass_head = ASS_HEAD.format(font=self.style.get("subtitle_font", "sans-serif"))

    def need_digest(self):
        if not self.digest.is_dir():
            die(f"{self.digest} がない。先に init を実行する")
        self.work.mkdir(exist_ok=True)

    def need_external(self, what):
        """外部 API を使う前に、送ってよいと確認済みかを見る"""
        if self.cfg["external_api"] != "allow":
            die(f"{what} は外部 API に内容を送る。このプロジェクトではまだ確認が取れていない(external_api: {self.cfg['external_api']})。\n"
                f"ユーザーに「ナレーション原稿と音楽の指示を Google(Gemini)に送ってよいか」を確認し、答えを {self.digesta} の冒頭の設定に\n"
                "external_api: allow(送ってよい)か external_api: deny(送らない。macOS の音声・BGM なしになる)として書いてから、もう一度実行する")

    def media(self, kinds=VIDEO_EXT):
        if self.cfg.get("video"):
            return self.root / self.cfg["video"]
        vs = sorted(p for p in self.root.iterdir() if p.suffix.lower() in kinds)
        if len(vs) != 1:
            die(f"録画ファイルが {len(vs)} 個ある({'/'.join(kinds)})。会議の digesta.md の設定に video: ファイル名 を書いて指定する")
        return vs[0]

    @property
    def video(self):
        return self.media(VIDEO_EXT)

    # 成果物のファイル名は日本語で分かりやすく(例: 2026-10-02_ダイジェスト.mp4)
    NAMES = {"minutes": "要約", "image": "グラレコ", "movie": "ダイジェスト", "thumb": "サムネイル"}

    def doc(self, kind, ext):
        return self.out / f"{self.name}_{self.NAMES.get(kind, kind)}.{ext}"

    def image(self, size):
        return self.out / f"{self.name}_{self.NAMES['image']}_{size}.png"

    @property
    def grareco_src(self):
        """グラレコの HTML。スタイルごとに grareco.<style>.html があればそれを、なければ grareco.html"""
        styled = self.digest / f"grareco.{self.cfg['style']}.html"
        return styled if styled.exists() else self.digest / "grareco.html"

    @property
    def movie(self):
        return self.out / f"{self.name}_{self.NAMES['movie']}.mp4"

    @property
    def thumb(self):
        return self.out / f"{self.name}_{self.NAMES['thumb']}.png"

    def episode(self):
        """episode.yaml に cuts.yaml の話題(題名・アイコン)を合わせたもの。カードと枠が読む"""
        f = self.digest / "episode.yaml"
        if not f.exists():
            die("digest/episode.yaml がない")
        ep = yaml.safe_load(f.read_text()) or {}
        cuts = self.cuts(required=False)
        for i, ch in enumerate(ep.get("chapters", [])):
            ch["n"] = i + 1
            ch.setdefault("who", ""); ch.setdefault("face", [])
            if ch.get("color") not in ("coral", "magenta", "orange", "teal", "blue", "purple", "green"):
                die(f"episode.yaml: {i + 1}章の color は coral/magenta/orange/teal/blue/purple/green のどれか")
            ch["topics"] = [{"title": t["title"], "icons": t.get("icons", [])} for t in cuts.get(i + 1, [])]
        ep.setdefault("label", self.name); ep.setdefault("number", ""); ep.setdefault("badge", "ダイジェスト")
        ep.setdefault("series", ""); ep.setdefault("date", "")
        ep["credit"] = self.cfg["credit"]
        return ep

    def cuts(self, required=True):
        """cuts.yaml → {章番号: [話題, ...]}"""
        f = self.digest / "cuts.yaml"
        if not f.exists():
            if required:
                die("digest/cuts.yaml がない")
            return {}
        data = yaml.safe_load(f.read_text()) or []
        return {int(c["chapter"]): c.get("topics", []) for c in data}

    def narration(self):
        """narration.md → ({カード名: 原稿}, {読み替え})。読み替えには用語集の読みも入る"""
        f = self.digest / "narration.md"
        if not f.exists():
            die("digest/narration.md がない")
        text = re.sub(r"<!--.*?-->", "", f.read_text(), flags=re.S)
        # 読み替え: プロジェクトの用語集(../digesta.md) < 会議フォルダの用語集(digesta.md) < narration.md の「## 読み」
        cards, yomi = {}, {k: r["読み"] for k, r in glossary_terms(self).items() if r.get("読み")}
        for name, body in re.findall(r"^## +(\S+)[^\n]*\n(.*?)(?=^## |\Z)", text, re.S | re.M):
            if name == "読み":
                for k, v in re.findall(r"^[-*] *(.+?) *[:=>→]+ *(.+?) *$", body, re.M):
                    yomi[k] = v
            else:
                cards[name] = " ".join(body.split())
        return cards, yomi


# ---------- 準備 ----------
def ensure_fonts(fonts):
    FONT_CACHE.mkdir(parents=True, exist_ok=True)
    for fn, (gdir, _, _) in fonts.items():
        p = FONT_CACHE / fn
        if p.exists() and p.stat().st_size > 100_000:
            continue
        for _ in range(3):
            try:
                urllib.request.urlretrieve(f"https://raw.githubusercontent.com/google/fonts/main/ofl/{gdir}/{fn}", p)
            except Exception:
                pass
            if p.exists() and p.stat().st_size > 100_000:
                break
        else:
            die(f"フォントを取得できない: {fn}")


def sync_lib(ep, with_episode=True):
    """選ばれたスタイルのファイルを digest/lib に同期し、fonts.css と episode.js を作る。スタイルと icons.js の内容ハッシュを返す(episode の中身は含めない)"""
    ensure_fonts(ep.fonts)
    ep.lib.mkdir(parents=True, exist_ok=True)
    for f in ep.lib.iterdir():  # 別のスタイルの残骸を消す
        if f.name not in ("fonts.css", "episode.js", "icons.js") and not (ep.style_dir / f.name).exists():
            f.unlink()
    for f in ep.style_dir.iterdir():
        if not (ep.lib / f.name).exists() or (ep.lib / f.name).read_bytes() != f.read_bytes():
            shutil.copy(f, ep.lib / f.name)
    css = "".join(f'@font-face{{font-family:"{fam}";font-weight:{w};src:url("{(FONT_CACHE / fn).as_uri()}")}}\n' for fn, (_, fam, w) in ep.fonts.items())
    (ep.lib / "fonts.css").write_text(css)
    # 会議ごとの追加イラスト: icons.<style>.js があればそれを、なければ icons.js を lib/icons.js として使う
    icons = ep.digest / "icons.js"
    if not icons.exists():
        icons.write_text("// この会議だけの追加イラスト。書き方は skill の references/grareco-guide.md を参照\nObject.assign(ICONS, {\n});\n")
    styled = ep.digest / f"icons.{ep.cfg['style']}.js"
    src_icons = styled if styled.exists() else icons
    if not (ep.lib / "icons.js").exists() or (ep.lib / "icons.js").read_bytes() != src_icons.read_bytes():
        shutil.copy(src_icons, ep.lib / "icons.js")
    parts = [f.read_bytes() for f in sorted(ep.style_dir.iterdir()) if f.name not in ("style.yaml", "grareco-base.html")] + [src_icons.read_bytes(), css.encode()]
    if with_episode and (ep.digest / "episode.yaml").exists():
        e = ep.episode()
        (ep.lib / "episode.js").write_text("const EP = " + json.dumps(e, ensure_ascii=False, indent=1) + ";\n")
    return sha(*parts)


def ep_slice(e, kind, ch=None):
    """カードや枠が実際に使う項目だけを取り出す。ここが変わったときだけ、そのカードや枠を作り直す"""
    chs = e["chapters"]
    head = [e.get(k) for k in ("label", "number", "badge")]
    c = chs[ch - 1] if ch else {}
    pick = lambda keys: {k: c.get(k) for k in keys}
    if kind == "frame":
        return [head, [[x.get(k) for k in ("n", "short", "who", "title", "color")] for x in chs], pick(("who", "title", "sub", "color", "face", "deco", "topics", "char"))]
    if kind == "opening":
        return [head, e.get("series"), e.get("date"), e.get("opening_bubble"), [[x.get(k) for k in ("n", "who", "title", "color", "face", "deco", "char")] for x in chs]]
    if kind == "chapter":
        return pick(("n", "who", "title", "sub", "sub_card", "color", "face", "deco", "char"))
    if kind == "recap":
        return pick(("n", "who", "color", "face", "deco", "recap", "recap_title", "char"))
    if kind == "ending":
        return e.get("ending")
    return [e.get("outro"), e.get("credit")]


def cmd_init(ep, a):
    ep.digest.mkdir(exist_ok=True); ep.work.mkdir(exist_ok=True)
    tpl = SKILL / "assets/templates"
    if not ep.digesta_local.exists() and not (ep.digest / "rules.md").exists():
        shutil.copy(tpl / "digesta-meeting.md", ep.digesta_local); print("作成:", ep.digesta_local, "(この会議の設定・ルール・用語集)")
    if not ep.digesta.exists() and not (ep.root.parent / "digest-rules.md").exists():
        shutil.copy(tpl / "digesta.md", ep.digesta); print("作成:", ep.digesta, "(プロジェクト共通の設定・ルール・用語集)")
    sync_lib(ep, with_episode=False)
    v = ep.media(VIDEO_EXT + AUDIO_EXT)
    info = json.loads(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration:stream=codec_type,width,height,r_frame_rate", "-of", "json", str(v)]))
    vs = next((s for s in info["streams"] if s["codec_type"] == "video"), None)
    print(f"録画: {v.name} / {ts(float(info['format']['duration']))}" + (f" / {vs['width']}x{vs['height']} / {vs['r_frame_rate']} fps" if vs else " / 音声のみ(動画は作れない。議事録とグラレコは作れる)"))
    wav = ep.work / "audio16k.wav"
    if not wav.exists():
        run(["ffmpeg", "-v", "error", "-y", "-i", v, "-vn", "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le", wav]); print("作成: digest/work/audio16k.wav")
    import_transcripts(ep)
    print("次: 素材とルールを読んでから、minutes.md / grareco.html / episode.yaml / cuts.yaml / narration.md を書く")


def import_transcripts(ep):
    """文字起こしや会議メモ(docx / vtt / srt / txt / md)を digest/work/transcript_*.md に取り込む"""
    found = []
    for f in sorted(ep.root.iterdir()):
        ext, dst = f.suffix.lower(), ep.work / f"transcript_{len(found) + 1}.md"
        if ext == ".docx" and shutil.which("pandoc"):
            if not dst.exists():
                run(["pandoc", f, "-t", "markdown", "--wrap=none", "-o", dst])
        elif ext in (".vtt", ".srt"):
            if not dst.exists():
                dst.write_text(caption_to_md(f.read_text(errors="replace")))
        elif ext in (".txt", ".md") and f.name.lower() not in ("readme.md", "todo.md"):
            if not dst.exists():
                shutil.copy(f, dst)
        else:
            continue
        found.append(f"{dst.relative_to(ep.root)} ← {f.name}")
    if found:
        print("文字起こし・メモ:\n  " + "\n  ".join(found))
    else:
        print("文字起こしが見つからない。全編をローカルで起こすなら: uv run asr.py full <dir>(Intel Mac では録画時間より長くかかる)")


def caption_to_md(text):
    """vtt / srt の字幕を「[時:分:秒] 話者: 発言」の行にまとめる(同じ話者の連続は1行にする)"""
    out, cur = [], None
    for block in re.split(r"\n\s*\n", text.replace("\r", "")):
        m = re.search(r"(\d{1,2}):(\d{2}):(\d{2})[.,]\d+ *--> ", block) or re.search(r"()(\d{2}):(\d{2})[.,]\d+ *--> ", block)
        if not m:
            continue
        t = f"{int(m.group(1) or 0):02d}:{m.group(2)}:{m.group(3)}"
        body = " ".join(l.strip() for l in block[m.end():].split("\n")[1:] if l.strip())
        body = re.sub(r"</?[^>]+>", lambda x: (x.group(0)[3:-1] + ": ") if x.group(0).startswith("<v ") else "", body).strip()
        if not body:
            continue
        sp = re.match(r"^([^::]{1,30})[::] *(.*)$", body)
        who, say = (sp.group(1), sp.group(2)) if sp else ("", body)
        if cur and cur[1] == who and len(cur[2]) < 400:
            cur[2] += " " + say
        else:
            cur = [t, who, say]; out.append(cur)
    return "\n\n".join(f"[{t}] {who + ': ' if who else ''}{say}" for t, who, say in out) + "\n"


def cmd_minutes(ep, a):
    """digest/minutes.md(正本)を output/ に出す。docx は pandoc で変換する"""
    ep.need_digest()
    src = ep.digest / "minutes.md"
    if not src.exists():
        die("digest/minutes.md がない")
    fmt = a.format or ep.cfg["minutes_format"]
    if fmt not in ("md", "docx", "both"):
        die("議事録の形式は md / docx / both のどれか")
    ep.out.mkdir(exist_ok=True)
    if fmt in ("md", "both"):
        shutil.copy(src, ep.doc("minutes", "md")); print("出力:", ep.doc("minutes", "md"))
    if fmt in ("docx", "both"):
        if not shutil.which("pandoc"):
            die("docx の出力には pandoc が必要(brew install pandoc)")
        run(["pandoc", src, "-f", "gfm", "-o", ep.doc("minutes", "docx"), "--reference-doc", SKILL / "assets/reference.docx"])
        print("出力:", ep.doc("minutes", "docx"))


def cmd_sheet(ep, a):
    ep.need_digest()
    v, d = ep.video, dur_of(ep.video)  # 音声のみの録画では使えない
    tmp = ep.work / "sheet"; tmp.mkdir(exist_ok=True)
    for f in tmp.glob("*.jpg"):
        f.unlink()
    times = list(range(a.step // 2, int(d), a.step))
    for t in times:
        run(["ffmpeg", "-v", "error", "-ss", t, "-i", v, "-frames:v", "1", "-vf",
             f"scale=640:-1,drawtext=text='{t // 60}m{t % 60:02d}s ({t}s)':fontcolor=yellow:fontsize=30:box=1:boxcolor=black@0.7:x=8:y=8", "-y", tmp / f"{t:05d}.jpg"])
    cols = 4
    run(["ffmpeg", "-v", "error", "-pattern_type", "glob", "-i", str(tmp / "*.jpg"), "-vf", f"tile={cols}x{math.ceil(len(times) / cols)}", "-frames:v", "1", "-y", ep.work / "sheet.jpg"])
    shutil.rmtree(tmp)
    print(f"{len(times)} フレーム → {ep.work / 'sheet.jpg'}")


def cmd_grid(ep, a):
    ep.need_digest()
    for t in a.args:
        out = ep.work / f"grid_{float(t):g}.jpg"
        run(["ffmpeg", "-v", "error", "-ss", t, "-i", ep.video, "-frames:v", "1", "-vf", "drawgrid=w=100:h=100:t=1:c=red@0.6", "-y", out])
        print(out, "(赤線は 100px 間隔。crop は 幅:高さ:左:上)")


def cmd_crop(ep, a):
    """画面共有の領域を自動で検出する。録画は「左に共有画面、右に参加者タイル、上下に黒帯」が多いので、
    黒い列・行の割合から共有画面の矩形を求め、16:9 に整えた crop(幅:高さ:左:上)を出す。grid で目視するより速い"""
    ep.need_digest()
    from PIL import Image, ImageDraw
    for t in a.args:
        raw = ep.work / f"crop_{float(t):g}.png"
        run(["ffmpeg", "-v", "error", "-ss", t, "-i", ep.video, "-frames:v", "1", "-y", raw])
        im = Image.open(raw).convert("L"); W, H = im.size; px = im.load()
        dark = lambda v: v < 40
        col = [sum(dark(px[x, y]) for y in range(0, H, 4)) / (H / 4) for x in range(W)]
        # 左端から、暗くない列が続く範囲 = 共有画面。幅 24px 以上の暗い帯で終わる
        x0 = next((x for x in range(W) if col[x] < 0.9), 0)
        x1, runlen = W, 0
        for x in range(x0, W):
            runlen = runlen + 1 if col[x] >= 0.97 else 0
            if runlen >= 24:
                x1 = x - runlen + 1; break
        row = [sum(dark(px[x, y]) for x in range(x0, x1, 4)) / max(1, (x1 - x0) / 4) for y in range(H)]
        ys = [y for y in range(H) if row[y] < 0.9]
        y0, y1 = (ys[0], ys[-1] + 1) if ys else (0, H)
        w = x1 - x0; h = round(w * 9 / 16)
        if h > y1 - y0:  # 共有画面が 16:9 より横長なら、高さに合わせて幅を狭める
            h = y1 - y0; w = round(h * 16 / 9); x0 = x0 + (x1 - x0 - w) // 2
        y = min(max(0, y0 + (y1 - y0 - h) // 2), H - h)
        w, h = w - w % 2, h - h % 2
        crop = f"{w}:{h}:{x0}:{y}"
        pv = Image.open(raw).convert("RGB"); d = ImageDraw.Draw(pv); d.rectangle([x0, y, x0 + w, y + h], outline=(255, 0, 0), width=4)
        pv.thumbnail((960, 540)); pv.save(raw)
        print(f"{float(t):g}s: 共有画面 x={x0}〜{x1} y={y0}〜{y1} → crop: '{crop}'  (確認用 {raw})")
    print("章の切り抜きは episode.yaml の chapters[].crop に、途中で変わるなら cuts.yaml の clips[].crop に書く。共有なし(タイルだけ)なら書かない")


def cmd_frames(ep, a):
    """完成動画の確認用に、区切り(カードと本編カット)ごとに 1 フレームを抜いて 1 枚にまとめる。
    10 秒おきに何十枚も抜いて読むより、この 1 枚で字幕・枠・カードの文字切れをまとめて見る"""
    ep.need_digest()
    from PIL import Image, ImageDraw
    seg, lst = ep.work / "seg", ep.work / "seg/list.txt"
    if not lst.exists():
        die("先に video を実行する")
    order = re.findall(r"'(.+)\.mkv'", lst.read_text())
    starts = {m.group(2): m.group(1) for m in re.finditer(r"^\s*(\d+:\d\d\.\d\d)\s+(\S+) ", (ep.work / "timeline.txt").read_text(), re.M)} if (ep.work / "timeline.txt").exists() else {}
    tmp = ep.work / "frames"; tmp.mkdir(exist_ok=True)
    for f in tmp.glob("*.png"):
        f.unlink()
    tiles = []
    for n in order:
        f = seg / f"{n}.mkv"; d = dur_of(f)
        if n.startswith("c_"):
            times = [d * 0.6]
        else:
            times = [min(1.5, d / 2), max(d - 1.2, d / 2)] if a.all else [min(1.5, d / 2)]
        for t in times:
            out = tmp / f"{len(tiles):03d}.png"
            run(["ffmpeg", "-v", "error", "-ss", f"{t:.2f}", "-i", f, "-frames:v", "1", "-vf", "scale=480:-1", "-y", out])
            tiles.append((out, f"{starts.get(n, '')} {n} +{t:.1f}s"))
    cols = 4; ims = [Image.open(t[0]) for t in tiles]; w, h = ims[0].size
    rows = math.ceil(len(ims) / cols); sheet = Image.new("RGB", (w * cols, h * rows), "white"); dr = ImageDraw.Draw(sheet)
    for i, (im, (_, label)) in enumerate(zip(ims, tiles)):
        x, y = (i % cols) * w, (i // cols) * h
        sheet.paste(im, (x, y)); dr.rectangle([x, y, x + 8 + 7 * len(label), y + 16], fill="black"); dr.text((x + 4, y + 2), label, fill="yellow")
    out = ep.work / "frames.png"; sheet.save(out); shutil.rmtree(tmp)
    print(f"{len(tiles)} フレーム → {out}(左上の黄色が完成動画での開始位置と区切り名。--all で本編カットの最後のフレームも)")


# ---------- ブラウザ ----------
def browser(w=1920, h=1080, scale=1):
    from playwright.sync_api import sync_playwright
    p = sync_playwright().start()
    try:
        b = p.chromium.launch()
    except Exception:
        # Playwright の版に合う Chromium が未取得のとき、キャッシュ済みの headless shell で代用する
        cands = sorted(Path.home().glob("Library/Caches/ms-playwright/chromium_headless_shell-*/chrome-headless-shell-*/chrome-headless-shell")) + \
            sorted(Path.home().glob(".cache/ms-playwright/chromium_headless_shell-*/chrome-headless-shell-*/chrome-headless-shell"))
        if not cands:
            die("Chromium がない。次を実行する: uv run --with playwright playwright install chromium-headless-shell")
        b = p.chromium.launch(executable_path=str(cands[-1]))
    return p, b, new_page(b, w, h, scale)


def new_page(b, w=1920, h=1080, scale=1):
    pg = b.new_page(viewport={"width": w, "height": h}, device_scale_factor=scale)
    pg.on("pageerror", lambda e: print("pageerror:", e))
    return pg


# ---------- 画像 ----------
def cmd_image(ep, a):
    ep.need_digest()
    src = ep.grareco_src
    if not src.exists():
        die(f"digest/grareco.html(または grareco.{ep.cfg['style']}.html)がない。digest/lib/grareco-base.html をコピーして書く")
    sync_lib(ep, with_episode=False)
    ep.out.mkdir(exist_ok=True)
    p, b, pg = browser()
    pg.goto(src.as_uri()); pg.wait_for_function("window.READY === true", timeout=30000)
    w, h = pg.evaluate("[document.body.offsetWidth, document.body.offsetHeight]")  # body に指定した設計サイズ
    pg.close()
    for size, px in (("4k", 3840), ("1920", 1920)):
        pg = new_page(b, w, h, px / w)  # 設計サイズと同じビューポートで開き直す(レイアウトがビューポート基準のため)
        if size == "4k":
            pg.on("console", lambda m: print("  console:", m.text))
        pg.goto(src.as_uri()); pg.wait_for_function("window.READY === true", timeout=30000)
        if size == "4k":
            sw, sh = pg.evaluate("[document.documentElement.scrollWidth, document.documentElement.scrollHeight]")
            if sw > w or sh > h:
                print(f"注意: 内容がはみ出している(本体 {w}x{h} に対して {sw}x{sh})。文字量かサイズを調整する")
        pg.screenshot(path=str(ep.image(size))); pg.close()
        print("出力:", ep.image(size))
    if getattr(a, "split", False):
        split_panels(ep, b, src, w, h)
    b.close(); p.stop()


def split_panels(ep, b, src, w, h):
    """章ごとのパネルを 16:9 の画像に切り出す。パネルの要素(.panel か main > section)を白地の 16:9 枠の中央に収める"""
    pg = new_page(b, w, h, 2)
    pg.goto(src.as_uri()); pg.wait_for_function("window.READY === true", timeout=30000)
    rects = pg.evaluate("""() => [...document.querySelectorAll('main > section, .panel')].filter((e, i, a) => a.indexOf(e) === i).map(e => { const r = e.getBoundingClientRect(); return [r.x, r.y, r.width, r.height]; })""")
    m = re.match(r"rgba?\((\d+),\s*(\d+),\s*(\d+)", pg.evaluate("getComputedStyle(document.body).backgroundColor") or "")
    bg = "0x%02x%02x%02x" % tuple(int(v) for v in m.groups()) if m else "white"
    out = []
    pg.evaluate("""() => { window.__panels = [...document.querySelectorAll('main > section, .panel')].filter((e, i, a) => a.indexOf(e) === i);
      window.__others = [...document.querySelectorAll('header, footer, body > *:not(main)')]; }""")
    for i, (x, y, pw, ph) in enumerate(rects, 1):
        pg.evaluate(f"""() => {{ window.__panels.forEach((e, k) => e.style.visibility = k === {i - 1} ? 'visible' : 'hidden'); window.__others.forEach(e => e.style.visibility = 'hidden'); }}""")
        # パネルを含む 16:9 の矩形(余白付き)。ページからはみ出す分は画像側で白く埋める
        pad = 24
        cw, chh = pw + pad * 2, ph + pad * 2
        if cw / chh < 16 / 9:
            cw = chh * 16 / 9
        else:
            chh = cw * 9 / 16
        cx, cy = x + pw / 2 - cw / 2, y + ph / 2 - chh / 2
        tmp = ep.work / f"panel_{i}.png"
        pg.screenshot(path=str(tmp), clip={"x": max(0, cx), "y": max(0, cy), "width": min(cw, w - max(0, cx)), "height": min(chh, h - max(0, cy))})
        dst = ep.out / f"{ep.name}_{ep.NAMES['image']}_章{i}.png"
        run(["ffmpeg", "-v", "error", "-y", "-i", tmp, "-vf", f"pad={int(cw * 2)}:{int(chh * 2)}:(ow-iw)/2:(oh-ih)/2:color={bg},scale=1920:1080", dst])
        tmp.unlink(); out.append(dst)
    pg.evaluate("() => { window.__panels.concat(window.__others).forEach(e => e.style.visibility = ''); }")
    pg.close()
    print(f"分割: {len(out)} 枚 → " + ", ".join(p.name for p in out))


# ---------- ナレーション ----------
ENV_DIRS = []  # .env を探すディレクトリ(会議 → プロジェクト → 実行した場所)。main で設定する


def dotenv_value(path, name):
    """.env 形式のファイルから name の値を読む(KEY=VALUE、export 付き、引用符、# コメントに対応)"""
    for line in path.read_text(errors="replace").splitlines():
        m = re.match(rf"^\s*(?:export\s+)?{re.escape(name)}\s*=\s*(.*?)\s*$", line)
        if m:
            v = m.group(1)
            if v[:1] in "'\"" and v[-1:] == v[:1]:
                return v[1:-1]
            return re.sub(r"\s+#.*$", "", v)
    return None


def gemini_key_source():
    """Gemini の API キーと、その出どころ(表示用。キー本体は表示しない)を返す。
    優先順: 会議の .env → プロジェクトの .env → 実行した場所の .env → 環境変数 → ~/.config/digesta/gemini.env"""
    seen = []
    for d in ENV_DIRS:
        f = d / ".env"
        if f in seen or not f.is_file():
            continue
        seen.append(f)
        for name in ("GEMINI_API_KEY", "GOOGLE_API_KEY"):
            v = dotenv_value(f, name)
            if v:
                return v, f"{f}({name})"
    for name in ("GEMINI_API_KEY", "GOOGLE_API_KEY"):
        if os.environ.get(name):
            return os.environ[name], f"環境変数 {name}"
    for f in (Path.home() / ".config/digesta/gemini.env",):
        if f.is_file():
            # キーだけの行でも、GEMINI_API_KEY=... の形でも読む。# で始まる行(古いキーのメモなど)と空行は飛ばす
            v = dotenv_value(f, "GEMINI_API_KEY")
            if not v:
                lines = [l.strip() for l in f.read_text(errors="replace").splitlines()]
                lines = [l for l in lines if l and not l.startswith("#")]
                v = lines[0].strip("'\"") if lines else None
            return v, str(f)
    return None, None


def gemini_key():
    k, src = gemini_key_source()
    if not k:
        die("Gemini の API キーがない。プロジェクトか会議のフォルダの .env に GEMINI_API_KEY=... と書く(~/.config/digesta/gemini.env でもよい)。中身は表示しないこと")
    # 改行や空白を含むキーをそのまま送ると、HTTP ライブラリがエラー文の中にキー本体を表示してしまう。ここで止める
    if re.search(r"\s", k) or len(k) < 20:
        die(f"Gemini の API キーの形式がおかしい({src})。1 行に 1 つのキーだけを書く(コメント行は # で始める)。中身は表示しないこと")
    return k


def gemini_audio(body, what):
    req = urllib.request.Request("https://generativelanguage.googleapis.com/v1beta/interactions", data=json.dumps(body).encode(),
                                 headers={"x-goog-api-key": gemini_key(), "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=900) as r:
            res = json.load(r)
    except urllib.error.HTTPError as e:
        die(f"{what} HTTP {e.code}: {e.read().decode()[:600]}")
    audio = [c for s in res.get("steps", []) if s.get("type") == "model_output" for c in s.get("content", []) if c.get("type") == "audio"]
    if not audio:
        die(f"{what}: 音声が返ってこなかった: " + json.dumps(res, ensure_ascii=False)[:600])
    return base64.b64decode(audio[-1]["data"])


def tts(ep, text, dst, voice=None):
    c, eng = ep.cfg, ep.cfg["narration"]
    if eng == "gemini":
        ep.need_external("Gemini TTS のナレーション")
        dst.write_bytes(gemini_audio({
            "model": c["gemini_tts_model"],
            "input": [{"type": "user_input", "content": [{"type": "text", "text": text, "annotations": [{"type": "speech_metadata", "style": c["voice_style"]}]}]}],
            "response_format": {"type": "audio", "mime_type": "audio/wav"},
            "generation_config": {"speech_config": [{"voice": voice or c["voice"]}]}}, "Gemini TTS"))
    elif eng == "voicevox":
        vv, sp = "http://127.0.0.1:50021", c["voicevox_speaker"]
        try:
            q = urllib.parse.urlencode({"text": text, "speaker": sp})
            with urllib.request.urlopen(urllib.request.Request(f"{vv}/audio_query?{q}", method="POST"), timeout=60) as r:
                query = json.load(r)
        except urllib.error.URLError:
            die("VOICEVOX エンジンに繋がらない。起動する: docker run -d --name voicevox_digesta -p 127.0.0.1:50021:50021 voicevox/voicevox_engine:cpu-latest")
        query.update({"speedScale": 1.08, "intonationScale": 1.15, "prePhonemeLength": 0.05, "postPhonemeLength": 0.1, "outputSamplingRate": 48000})
        print("   読み:", query["kana"])
        req = urllib.request.Request(f"{vv}/synthesis?speaker={sp}", data=json.dumps(query).encode(), headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=300) as r:
            dst.write_bytes(r.read())
    elif eng == "say":
        run(["say", "-v", c["say_voice"], "-r", "185", "--data-format=LEI16@48000", "-o", dst, text])
    else:
        die(f"narration の値が不正: {eng}")


def narr_key(ep, text):
    c = ep.cfg
    return sha(c["narration"], c["voice"], c["voice_style"], c["gemini_tts_model"], c["voicevox_speaker"], c["say_voice"], text)


def apply_yomi(text, yomi):
    """長い語から順に読み替える。英字で始まる/終わる語は、前後が英字のとき(単語の途中)は置き換えない(OpenAI の AI など)"""
    for k in sorted(yomi, key=len, reverse=True):
        pat = ("(?<![A-Za-z])" if k[:1].isascii() and k[:1].isalpha() else "") + re.escape(k) + ("(?![A-Za-z])" if k[-1:].isascii() and k[-1:].isalpha() else "")
        text = re.sub(pat, lambda m, v=yomi[k]: v, text)
    return text


def cmd_narration(ep, a, quiet=False):
    ep.need_digest()
    if ep.cfg["narration"] == "none":
        if not quiet:
            print("narration: none(ナレーションなし)")
        return {}
    if ep.cfg["narration"] == "voicevox" and not ep.cfg["credit"]:
        die("VOICEVOX は規約でクレジット表記が必要。digesta.md の設定に credit: ナレーション VOICEVOX:キャラ名 を書く")
    cards, yomi = ep.narration()
    nd = ep.work / "narr"; nd.mkdir(exist_ok=True)
    only = set(a.only.split(",")) if getattr(a, "only", None) else None
    made = []
    for name, text in cards.items():
        dst, spoken = nd / f"{name}.wav", apply_yomi(text, yomi)
        key = narr_key(ep, spoken)
        if only and name not in only:
            continue
        if a.force or not fresh(dst, key):
            tts(ep, spoken, dst); mark(dst, key); made.append(name)
            print(f"合成: {name:8s} {dur_of(dst):5.2f}s")
    if not quiet or made:
        print(f"ナレーション {len(cards)} 本({ep.cfg['narration']}" + (f" / {ep.cfg['voice']}" if ep.cfg["narration"] == "gemini" else "") + f")。今回合成: {', '.join(made) or 'なし'}")
        if made:
            print("読みの確認: uv run asr.py check-narration <dir>(読み間違いがあれば narration --only 名前 --force で作り直す)")
    return cards


def cmd_voices(ep, a):
    ep.need_digest()
    if ep.cfg["narration"] != "gemini":
        die("声のサンプルは narration: gemini のときだけ")
    cards, yomi = ep.narration()
    text = apply_yomi(" ".join(list(cards.values())[:2]), yomi)
    out = ep.work / "voice_samples"; out.mkdir(exist_ok=True)
    for v in a.args:
        tts(ep, text, out / f"{v}.wav", voice=v)
        print(f"{v:12s} {dur_of(out / f'{v}.wav'):5.1f}s → {out / f'{v}.wav'}")


# ---------- キャラクター画像 ----------
def gemini_image(ep, prompt, dst):
    body = {"model": ep.cfg["image_model"], "input": [{"type": "text", "text": prompt}],
            "response_format": {"type": "image", "mime_type": "image/jpeg", "aspect_ratio": "1:1", "image_size": "1K"}}
    req = urllib.request.Request("https://generativelanguage.googleapis.com/v1beta/interactions", data=json.dumps(body).encode(),
                                 headers={"x-goog-api-key": gemini_key(), "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=600) as r:
            res = json.load(r)
    except urllib.error.HTTPError as e:
        die(f"Gemini 画像生成 HTTP {e.code}: {e.read().decode()[:600]}")
    imgs = [c for st in res.get("steps", []) if st.get("type") == "model_output" for c in st.get("content", []) if c.get("type") == "image"]
    if not imgs:
        die("Gemini 画像生成: 画像が返ってこなかった: " + json.dumps(res, ensure_ascii=False)[:600])
    dst.write_bytes(base64.b64decode(imgs[-1]["data"]))


def chars_spec(ep):
    """digest/chars.yaml → {名前: プロンプト}。スタイルの共通指示(style.yaml の char_style)を前に付ける"""
    f = ep.digest / "chars.yaml"
    if not f.exists():
        return {}
    data = yaml.safe_load(f.read_text()) or []
    base = ep.style.get("char_style", "")
    out = {}
    for c in data:
        out[c["name"]] = (base + " " + c["prompt"]).strip()
    return out


def cmd_chars(ep, a):
    ep.need_digest()
    spec = chars_spec(ep)
    if not spec:
        die("digest/chars.yaml がない。- {name: 名前, prompt: 見た目とポーズの英文} を並べて書く(人名や会議の内容は書かない)")
    cd = ep.digest / "chars"; cd.mkdir(exist_ok=True)
    only = set(a.only.split(",")) if getattr(a, "only", None) else None
    made = []
    for name, prompt in spec.items():
        if only and name not in only:
            continue
        dst = cd / f"{name}.jpg"
        key = sha("char", ep.cfg["image_model"], prompt)
        if a.force or not fresh(dst, key):
            ep.need_external("Gemini のキャラクター画像生成")
            gemini_image(ep, prompt, dst); mark(dst, key); made.append(name)
            print(f"生成: {name}")
    print(f"キャラクター {len(spec)} 体。今回生成: {', '.join(made) or 'なし'} → {cd}")
    if made:
        print("画像を見て、服装や向きが意図と違えば chars.yaml のプロンプトを直して chars --only 名前 --force")


def char_key(ep, name):
    f = ep.digest / "chars" / f"{name}.jpg"
    return hashlib.sha256(f.read_bytes()).hexdigest()[:16] if name and f.exists() else None


# ---------- BGM ----------
def cmd_bgm(ep, a, need=420):
    ep.need_digest()
    kind = ep.cfg["bgm"]
    if kind in ("none", None, False, ""):
        return None
    bd = ep.work / "bgm"; bd.mkdir(exist_ok=True)
    src, long = bd / "bgm.wav", bd / "bgm_long.wav"
    if kind == "lyria":
        key = sha("lyria", ep.cfg["bgm_model"], ep.cfg["bgm_prompt"])
        if getattr(a, "force", False) and a.cmd == "bgm" or not fresh(src, key):
            ep.need_external("Lyria の BGM 生成")
            raw = bd / "bgm_raw"
            raw.write_bytes(gemini_audio({"model": ep.cfg["bgm_model"], "input": ep.cfg["bgm_prompt"]}, "Lyria"))  # 既定の MP3 で受け取る
            run(["ffmpeg", "-v", "error", "-y", "-i", raw, "-ar", "48000", "-ac", "2", src]); raw.unlink(); mark(src, key)
            print(f"BGM 生成: {dur_of(src):.1f}s")
    else:
        f = ep.root / kind
        if not f.exists():
            die(f"bgm のファイルがない: {f}")
        key = sha("file", f.stat().st_size, f.stat().st_mtime)
        if not fresh(src, key):
            run(["ffmpeg", "-v", "error", "-y", "-i", f, "-ar", "48000", "-ac", "2", src]); mark(src, key)
    d = dur_of(src)
    n = max(1, math.ceil((need + 10) / max(d - 4, 1)))
    lkey = sha(Path(str(src) + ".key").read_text(), n)
    if not fresh(long, lkey):
        if n == 1:
            shutil.copy(src, long)
        else:  # つなぎ目をクロスフェードして必要な長さまで伸ばす
            ins = sum((["-i", src] for _ in range(n)), [])
            fc, prev = [], "[0:a]"
            for i in range(1, n):
                fc.append(f"{prev}[{i}:a]acrossfade=d=4:c1=tri:c2=tri[x{i}]"); prev = f"[x{i}]"
            run(["ffmpeg", "-v", "error", "-y", *ins, "-filter_complex", ";".join(fc), "-map", prev, long])
        mark(long, lkey)
    return long


# ---------- 動画 ----------
def crop_filter(crop):
    if crop == "full":  # スライド領域の指定なし: 画面全体を使う
        return f"scale=1344:756:force_original_aspect_ratio=decrease:flags=lanczos:{RGB_IN},pad=1344:756:(ow-iw)/2:(oh-ih)/2:white"
    w, h, *_ = (int(x) for x in str(crop).split(":"))
    if abs(w / h - 16 / 9) < 0.02:
        return f"crop={crop},scale=1344:756:flags=lanczos:{RGB_IN}"
    if w / h < 16 / 9:
        return f"crop={crop},scale=-2:756:flags=lanczos:{RGB_IN},pad=1344:756:(ow-iw)/2:0:white"
    return f"crop={crop},scale=1344:-2:flags=lanczos:{RGB_IN},pad=1344:756:0:(oh-ih)/2:white"


def enc(ep):
    return ["-c:v", "libx264", "-preset", "fast", "-crf", "15", *TAG, "-r", str(ep.fps), "-c:a", "pcm_s16le", "-ar", "48000", "-ac", "2"]


def build_topic(ep, e, ch, t, topic, frame, seg, force):
    crop_ch = e["chapters"][ch - 1].get("crop")
    clips = topic.get("clips") or []
    if not clips:
        die(f"cuts.yaml: {ch}章「{topic['title']}」に clips がない")
    clean = CLEAN if ep.cfg["clean_audio"] else "highpass=f=70"
    v = ep.video
    key = sha("topic", clips, crop_ch, clean, ep.ass_head, ep.paper, ep.fps, Path(str(frame) + ".key").read_text(), v.stat().st_size)
    out = seg / f"t{ch}{t}.mkv"
    if not force and fresh(out, key):
        return dur_of(out), False
    ass, off, inputs, fc = ep.ass_head, 0.0, [], []
    for i, c in enumerate(clips):
        a, b = float(c["start"]), float(c["end"])
        crop = c.get("crop") or crop_ch or "full"
        d = b - a
        inputs += ["-ss", f"{a:.3f}", "-t", f"{d:.3f}", "-i", v]
        fc.append(f"[{i}:v]{crop_filter(crop)},fps={ep.fps},setsar=1,fade=t=in:st=0:d=0.25:color=white,fade=t=out:st={d - 0.25:.3f}:d=0.25:color=white[v{i}]")
        fc.append(f"[{i}:a]aresample=48000,{clean},afade=t=in:st=0:d=0.06,afade=t=out:st={d - 0.1:.3f}:d=0.1[a{i}]")
        for s, e2, text in c.get("subs") or []:
            s2, e3 = off + max(float(s) - a, 0.0), off + min(float(e2) - a, d - 0.03)
            ass += f"Dialogue: 0,{ass_ts(s2)},{ass_ts(e3)},Sub,,0,0,0,,{{\\pos(960,972)}}{str(text).replace(chr(10), chr(92) + 'N')}\n"
        off += d
    n = len(clips)
    (seg / f"t{ch}{t}.ass").write_text(ass)
    fc.append("".join(f"[v{i}][a{i}]" for i in range(n)) + f"concat=n={n}:v=1:a=1[cv][ca]")
    fc.append(f"[cv]pad=1920:1080:44:104:color={ep.paper}[pv]")
    fc.append(f"[pv][{n}:v]overlay=0:0:format=gbrp,format=rgb24,subtitles=seg/t{ch}{t}.ass:fontsdir={FONT_CACHE},format=rgb24,"
              f"fade=t=in:st=0:d=0.3:color={ep.paper},fade=t=out:st={off - 0.3:.3f}:d=0.3:color={ep.paper},{TOYUV}[v]")
    fc.append("[ca]loudnorm=I=-16:TP=-1.5:LRA=11,aresample=48000,asetpts=N/SR/TB[a]")
    run(["ffmpeg", "-v", "error", "-y", *inputs, "-i", frame, "-filter_complex", ";".join(fc), "-map", "[v]", "-map", "[a]", "-t", f"{off:.3f}", *enc(ep), out], cwd=ep.work)
    mark(out, key)
    return off, True


def check_texts(ep):
    """episode.yaml / cuts.yaml / narration.md の誤りを集める。(エラー一覧, 警告一覧) を返す。
    ビルドで止まる誤り(YAML が読めない、章番号の不一致)と、できあがりがおかしくなる誤り(字幕が区間の外、原稿の見出し漏れ)を、ビルド前に出す"""
    errs, warns = [], []
    def load(name):
        f = ep.digest / name
        if not f.exists():
            errs.append(f"{name} がない"); return None
        try:
            return yaml.safe_load(f.read_text())
        except yaml.YAMLError as ex:
            m = getattr(ex, "problem_mark", None)
            where = f" {m.line + 1} 行目" if m else ""
            errs.append(f"{name}{where}: YAML として読めない({getattr(ex, 'problem', ex)})。「: 」や「 #」を含む文は引用符で囲む"); return None
    e, cuts = load("episode.yaml"), load("cuts.yaml")
    if e is None or cuts is None:
        return errs, warns
    chapters = e.get("chapters") or []
    if not chapters:
        errs.append("episode.yaml: chapters がない")
    for i, ch in enumerate(chapters, 1):
        if ch.get("color") not in ("coral", "magenta", "orange", "teal", "blue", "purple", "green"):
            errs.append(f"episode.yaml: {i}章の color が不正({ch.get('color')})")
        if len(str(ch.get("title", ""))) > 20 and not ch.get("sub"):
            warns.append(f"episode.yaml: {i}章の title が長い({len(str(ch.get('title')))}字)。短い呼び名を title に、正式名を sub に")
        for r in ch.get("recap") or []:
            t = re.sub(r"<[^>]+>", "", str(r.get("text", "")))
            if len(t) > 24:
                warns.append(f"episode.yaml: {i}章のまとめ「{t[:12]}…」が長い({len(t)}字。目安 22 字)")
            if " #" in str(r.get("text", "")) or " #" in str(r.get("sub", "")):
                warns.append(f"episode.yaml: {i}章のまとめに「 #」がある。引用符で囲んでいないと、そこから後ろが消える")
        if len(ch.get("recap") or []) > 3:
            warns.append(f"episode.yaml: {i}章のまとめが {len(ch['recap'])} 項目(3 項目まで)")
    cut_ch = [int(c.get("chapter", 0)) for c in (cuts if isinstance(cuts, list) else [])]
    for n in cut_ch:
        if n < 1 or n > len(chapters):
            errs.append(f"cuts.yaml: chapter {n} は episode.yaml にない(章は {len(chapters)} つ)")
    for i in range(1, len(chapters) + 1):
        if i not in cut_ch:
            warns.append(f"cuts.yaml: {i}章の切り抜きがない(カードだけの章になる)")
    for c in (cuts if isinstance(cuts, list) else []):
        n = c.get("chapter")
        for t in c.get("topics") or []:
            if len(str(t.get("title", ""))) > 14:
                warns.append(f"cuts.yaml: {n}章「{t.get('title')}」の題名が長い(目安 12 字)")
            for cl in t.get("clips") or []:
                try:
                    a0, b0 = float(cl["start"]), float(cl["end"])
                except Exception:
                    errs.append(f"cuts.yaml: {n}章「{t.get('title')}」の clip に start/end がない"); continue
                if b0 <= a0:
                    errs.append(f"cuts.yaml: {n}章「{t.get('title')}」の clip {a0}-{b0} は end が start 以下")
                prev = a0
                for sub in cl.get("subs") or []:
                    if not (isinstance(sub, list) and len(sub) == 3):
                        errs.append(f"cuts.yaml: {n}章「{t.get('title')}」の字幕 {sub!r} は [開始, 終了, 文] の形でない"); continue
                    sa, sb, txt = float(sub[0]), float(sub[1]), str(sub[2])
                    if sa < a0 - 0.05 or sb > b0 + 0.05:
                        errs.append(f"cuts.yaml: {n}章「{t.get('title')}」の字幕「{txt[:14]}…」({sa}-{sb})が clip {a0}-{b0} の外")
                    if sa < prev - 0.05:
                        warns.append(f"cuts.yaml: {n}章「{t.get('title')}」の字幕「{txt[:14]}…」の時刻が前の字幕より前")
                    prev = sb
                    for line in txt.split("\\N"):
                        if len(line) > 30:
                            warns.append(f"cuts.yaml: {n}章 字幕「{line[:14]}…」の 1 行が {len(line)} 字(目安 28 字)")
                    if txt.count("\\N") > 1:
                        warns.append(f"cuts.yaml: {n}章 字幕「{txt[:14]}…」が 3 行以上")
    cards, _ = ep.narration()
    want = ["opening"] + [x for i in range(1, len(chapters) + 1) for x in ([f"ch{i}"] + ([f"recap{i}"] if (chapters[i - 1].get("recap")) else []))]
    want += ["ending"] if e.get("ending") else []
    want += ["outro"] if e.get("outro") else []
    for w in want:
        if w not in cards:
            warns.append(f"narration.md: 「## {w}」がない(このカードは無音になる)")
    for c in cards:
        if c not in want:
            warns.append(f"narration.md: 「## {c}」に対応するカードがない(読まれない)")
    return errs, warns


def cmd_plan(ep, a):
    """ビルド前の検査と尺の見積もり。ビルドは 10〜20 分かかるので、尺の調整はこの数字を見てから"""
    ep.need_digest()
    errs, warns = check_texts(ep)
    for w in warns:
        print("注意:", w)
    for x in errs:
        print("誤り:", x)
    if errs:
        die(f"{len(errs)} 件の誤りを直してから video を実行する")
    e, cuts, (cards, _) = ep.episode(), ep.cuts(), ep.narration()
    def card_len(name, tail):
        wav = ep.work / "narr" / f"{name}.wav"
        if wav.exists():
            nd, how = dur_of(wav), ""
        elif name in cards:
            nd, how = len(cards[name]) / 6.2 + 0.4, "*"  # 日本語の読み上げは 1 秒 6 文字強。音声がまだなければ文字数から
        else:
            nd, how = 5.0, "*"
        return 0.5 + nd + tail + 0.7, how  # 0.5 は声の前の間、0.7 はアニメーションの余り(実測の平均)
    total, rows = 0.0, []
    def add(name, d, how=""):
        nonlocal total
        rows.append(f"  {ts(total):>8}  {name:<10} {d:5.1f}s{how}"); total += d
    d, how = card_len("opening", 0.7); add("opening", d, how)
    for ch in e["chapters"]:
        n = ch["n"]
        d, how = card_len(f"ch{n}", 0.7); add(f"ch{n}", d, how)
        for t, topic in enumerate(cuts.get(n, [])):
            d = sum(float(c["end"]) - float(c["start"]) for c in topic.get("clips") or [])
            add(f"t{n}{t}", d)
        if ch.get("recap"):
            d, how = card_len(f"recap{n}", 0.8); add(f"recap{n}", d, how)
    if e.get("ending"):
        if ep.image("1920").exists():
            d, how = card_len("ending", 1.5); add("ending", d, how)
        else:
            print("注意: グラレコ画像がまだないので、ending カードは入らない(先に image を実行する)")
    if e.get("outro"):
        d, how = card_len("outro", 3.0); add("outro", d, how)
    print("\n".join(rows))
    talk = sum(float(c["end"]) - float(c["start"]) for n in cuts for t in cuts[n] for c in t.get("clips") or [])
    print(f"見積もり: 全体 {ts(total)}(本編 {ts(talk)}、カード {ts(total - talk)})。* は音声未生成のため文字数からの推定(±15%)")
    if warns:
        print(f"注意 {len(warns)} 件(上に表示)。誤りはなし。video を実行できる")
    else:
        print("誤り・注意なし。video を実行できる")


def cmd_video(ep, a):
    ep.need_digest()
    errs, warns = check_texts(ep)
    for w in warns:
        print("注意:", w)
    if errs:
        for x in errs:
            print("誤り:", x)
        die(f"{len(errs)} 件の誤りを直してから video を実行する(digest.py plan で確かめられる)")
    libkey = sync_lib(ep)
    e = ep.episode()
    libkey = sha(libkey, sorted((c, char_key(ep, c)) for c in {x.get("char") for x in e.get("chapters", [])} if c))
    cuts = ep.cuts()
    chapters = e.get("chapters") or []
    if not chapters:
        die("episode.yaml に chapters がない")
    narr = cmd_narration(ep, argparse.Namespace(only=None, force=False), quiet=True)
    seg = ep.work / "seg"; seg.mkdir(exist_ok=True)
    fdir = ep.work / "frames"; fdir.mkdir(exist_ok=True)
    made = []

    # カードの並び。ナレーション原稿があるものだけ出す(ending はグラレコ画像があるときだけ)
    img = ep.image("1920")
    plan = [("opening", "id=opening", 0.7, ep_slice(e, "opening"))]
    for ch in chapters:
        n = ch["n"]
        plan.append((f"ch{n}", f"id=chapter&ch={n}", 0.7, ep_slice(e, "chapter", n)))
        plan += [("topic", n, t) for t in range(len(cuts.get(n, [])))]
        if ch.get("recap"):
            plan.append((f"recap{n}", f"id=recap&ch={n}", 0.8, ep_slice(e, "recap", n)))
    if e.get("ending") and img.exists():
        plan.append(("ending", f"id=ending&img={urllib.parse.quote(img.as_uri(), safe=':/')}", 1.5, ep_slice(e, "ending")))
    if e.get("outro"):
        plan.append(("outro", "id=outro", 3.0, ep_slice(e, "outro")))
    last_card = [p[0] for p in plan if p[0] != "topic"][-1]

    p = b = pg = None

    def page():
        nonlocal p, b, pg
        if pg is None:
            p, b, pg = browser()
        return pg

    order = []
    for item in plan:
        if item[0] == "topic":
            _, ch, t = item
            frame = fdir / f"frame_{ch}_{t}.png"
            fkey = sha("frame", libkey, ep_slice(e, "frame", ch), t)
            if a.force or not fresh(frame, fkey):
                pg_ = page()
                pg_.goto((ep.lib / "frame.html").as_uri() + f"#ch={ch}&topic={t}"); pg_.reload()
                pg_.wait_for_function("window.READY === true")
                pg_.screenshot(path=str(frame), omit_background=True); mark(frame, fkey)
            d, did = build_topic(ep, e, ch, t, cuts[ch][t], frame, seg, a.force)
            if did:
                made.append(f"t{ch}{t}"); print(f"本編 {ch}-{t + 1}「{cuts[ch][t]['title']}」 {d:.1f}s")
            order.append(f"t{ch}{t}")
            continue
        name, h, tail, used = item
        wav = ep.work / "narr" / f"{name}.wav"
        has_narr = name in narr and wav.exists()
        nd = dur_of(wav) if has_narr else 5.0
        out = seg / f"c_{name}.mkv"
        key = sha("card", libkey, used, h, tail, ep.fps, name == last_card, hashlib.sha256(wav.read_bytes()).hexdigest() if has_narr else nd,
                  img.stat().st_mtime if name == "ending" else 0, ep.paper, "thumb2" if name == "opening" else "")
        if a.force or not fresh(out, key):
            pg_ = page()
            pg_.goto((ep.lib / "cards.html").as_uri() + "#" + h + f"&nd={nd:.2f}"); pg_.reload()
            pg_.wait_for_function("window.READY === true")
            d = max(pg_.evaluate("window.END") / 1000 + 1.0, 0.5 + nd + tail)
            nf = math.ceil(d * ep.fps)
            fd = seg / f"c_{name}"; fd.mkdir(exist_ok=True)
            for f in fd.glob("*.jpg"):
                f.unlink()
            for i in range(nf):
                pg_.evaluate(f"seek({i * 1000 / ep.fps})")
                pg_.screenshot(path=str(fd / f"{i:05d}.jpg"), type="jpeg", quality=95)
            d = nf / ep.fps
            fo = 1.2 if name == last_card else 0.3  # 最後のカードはゆっくり消す
            audio = ["-i", wav] if has_narr else ["-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo"]
            af = "[1:a]aresample=48000,loudnorm=I=-17:TP=-1.5:LRA=11,aresample=48000,asetpts=N/SR/TB,adelay=500:all=1,apad[a]" if has_narr else "[1:a]anull[a]"
            base = f"[0:v]scale=in_color_matrix=bt601:in_range=pc:out_range=pc,format=rgb24,fade=t=out:st={d - fo:.3f}:d={fo}:color={ep.paper}"
            thumb_in = []
            if name == "opening":
                # サムネイル: 停止中のプレーヤーは先頭フレームを表示するので、それを先頭に置き、0.5 秒かけてオープニングの頭に溶かす。
                # スタイルの cards.html に id="thumb"(タイトルスライド)があればそれを、なければオープニングの完成状態を使う
                if 'id="thumb"' in (ep.lib / "cards.html").read_text():
                    pg_.goto((ep.lib / "cards.html").as_uri() + "#id=thumb"); pg_.reload()
                    pg_.wait_for_function("window.READY === true")
                pg_.evaluate("seek(window.END)")
                pg_.screenshot(path=str(ep.work / "thumb.png"))
                thumb_in = ["-loop", "1", "-framerate", ep.fps, "-t", "0.6", "-i", ep.work / "thumb.png"]
                vf = f"{base}[b];[2:v]format=rgba,fade=t=out:st={1 / ep.fps:.4f}:d=0.5:alpha=1[th];[b][th]overlay=eof_action=pass:format=gbrp,format=rgb24,{TOYUV}[v]"
            else:
                vf = f"{base},fade=t=in:st=0:d=0.3:color={ep.paper},{TOYUV}[v]"
            run(["ffmpeg", "-v", "error", "-y", "-framerate", ep.fps, "-i", fd / "%05d.jpg", *audio, *thumb_in, "-filter_complex",
                 f"{vf};{af}", "-map", "[v]", "-map", "[a]", "-t", f"{d:.3f}", *enc(ep), out])
            shutil.rmtree(fd)
            mark(out, key); made.append(f"c_{name}"); print(f"カード {name} {d:.1f}s")
        order.append(f"c_{name}")
    if b:
        b.close(); p.stop()

    # 結合
    (seg / "list.txt").write_text("".join(f"file '{n}.mkv'\n" for n in order))
    total, lines = 0.0, []
    for n in order:
        d = dur_of(seg / f"{n}.mkv"); lines.append(f"  {ts(total):>8}  {n} ({d:.1f}s)"); total += d
    bgm = None if a.no_bgm else cmd_bgm(ep, a, need=total)
    # 音声は、区切りごとに「時刻を捨ててサンプルの並びどおりに読み、映像の長さちょうどに切りそろえて」から
    # 1 本の WAV につなぐ。loudnorm は先読みのために冒頭約 3 秒のパケット時刻を乱し(0.019 秒間隔で詰め込み、
    # その後 2.3 秒飛ぶ)、サンプルも映像より数十 ms 短くなる。サンプルの並びは正しいので手元のプレーヤーは
    # 平気だが、時刻を信じる側(Google ドライブ等の再エンコード、aresample=async)は声を捨てて無音を埋める
    # (2026-10 に発生)。時刻を「そろえる」のではなく「付け直す」こと。
    fps = float(ep.fps)
    ins, fc, total = [], [], 0.0
    for i, n in enumerate(order):
        fr = int(subprocess.check_output(["ffprobe", "-v", "error", "-select_streams", "v", "-count_packets", "-show_entries", "stream=nb_read_packets", "-of", "csv=p=0", str(seg / f"{n}.mkv")]).split()[0].strip(b","))
        ns = round(fr * 48000 / fps); total += fr / fps
        ins += ["-i", seg / f"{n}.mkv"]
        fc.append(f"[{i}:a]aresample=48000,aformat=channel_layouts=stereo,asettb=1/48000,asetpts=N,apad=whole_len={ns},atrim=end_sample={ns},asetpts=N[a{i}]")
    fc.append("".join(f"[a{i}]" for i in range(len(order))) + f"concat=n={len(order)}:v=0:a=1[a]")
    voice = ep.work / "voice.wav"
    run(["ffmpeg", "-v", "error", "-y", *ins, "-filter_complex", ";".join(fc), "-map", "[a]", "-c:a", "pcm_s16le", voice])
    END = "asettb=1/48000,asetpts=N"
    mix = ["-i", voice, "-map", "0:v", "-map", "1:a", "-af", END]
    if bgm:
        # BGM は小さめに敷き、声(ナレーション・発表者)が入っている間はさらに下げる(サイドチェーン)
        mix = ["-i", voice, "-i", bgm, "-filter_complex",
               f"[2:a]aresample=48000,volume={ep.cfg['bgm_gain']},afade=t=in:st=0:d=1.0,afade=t=out:st={total - 3.0:.2f}:d=3.0[b];[1:a]asplit[m][k];"
               f"[b][k]sidechaincompress=threshold=0.05:ratio=4:attack=15:release=500[bd];[m][bd]amix=inputs=2:normalize=0:duration=first,alimiter=limit=0.84:level=false,{END}[a]",
               "-map", "0:v", "-map", "[a]"]
    tmp = ep.work / "digest.mp4"
    run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", seg / "list.txt", *mix, "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p", *TAG,
         "-r", ep.fps, "-c:a", "aac", "-b:a", "160k", "-ar", "48000", "-t", f"{total:.3f}", "-movflags", "+faststart", tmp])
    # 検査: 音声パケットの時刻が連続か(末尾の 1 個以外はすべて 1024 サンプル間隔のはず)
    pk = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "a", "-show_entries", "packet=pts", "-of", "csv=p=0", str(tmp)], capture_output=True, text=True).stdout.split()
    pts = [int(x.strip(",")) for x in pk if x.strip(",").lstrip("-").isdigit()]
    bad = sum(1 for x, y in zip(pts, pts[1:]) if y - x != 1024)
    if bad:
        sys.exit(f"音声パケットの時刻が不連続です({bad} か所)。このまま配ると Google ドライブ等のプレビューで音が崩れます: {tmp}")
    # 検査: 区切りを順に並べた音(時刻を無視)と、完成動画の音の長さが合うか。声が捨てられていれば合わない
    def nsamp(args):
        r = subprocess.run(["ffmpeg", "-v", "error", *args, "-vn", "-ac", "1", "-ar", "8000", "-f", "s16le", "-"], capture_output=True).stdout
        return len(r) // 2 / 8000
    got = nsamp(["-i", str(tmp)])
    if abs(total - got) > 0.1:
        sys.exit(f"完成動画の音の長さ({got:.2f}s)が映像の長さ({total:.2f}s)と合いません。結合で音が欠けたかずれています: {tmp}")
    # 検査: 時刻どおりに組み直しても音量の並びが変わらないか(時刻を信じる配布先での聞こえ方の模擬)
    def prof(extra):
        r = subprocess.run(["ffmpeg", "-v", "error", "-i", str(tmp), "-vn", *extra, "-ac", "1", "-ar", "8000", "-f", "s16le", "-"], capture_output=True).stdout
        import array
        x = array.array("h", r[: len(r) // 2 * 2]); h = 2000
        return [sum(abs(v) for v in x[k:k + h]) / h for k in range(0, len(x) - h + 1, h)]
    p0, p1 = prof([]), prof(["-af", "aresample=async=1:first_pts=0"])
    lost = sum(1 for u, v in zip(p0, p1) if u > 300 and v < u * 0.3)
    if lost or abs(len(p0) - len(p1)) > 4:
        sys.exit(f"時刻どおりに再生すると音が欠けます({lost * 0.25:.1f} 秒分)。Google ドライブ等のプレビューで声が消えます: {tmp}")
    ep.out.mkdir(exist_ok=True)
    shutil.copy(tmp, ep.movie)
    if (ep.work / "thumb.png").exists():
        shutil.copy(ep.work / "thumb.png", ep.thumb)  # Slack などに動画と一緒に添える用
    (ep.work / "timeline.txt").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))
    print(f"作り直した部分: {', '.join(made) or 'なし(結合のみ)'}")
    lu = subprocess.run(["ffmpeg", "-hide_banner", "-i", str(ep.movie), "-af", "ebur128=peak=true:framelog=quiet", "-f", "null", "-"], capture_output=True, text=True).stderr
    m = re.search(r"I:\s+(-?[\d.]+) LUFS[\s\S]*?Peak:\s+(-?[\d.]+) dBFS", lu[lu.rfind("Summary"):])
    print(f"出力: {ep.movie}({ts(total)}、BGM {'あり' if bgm else 'なし'}" + (f"、{m.group(1)} LUFS、ピーク {m.group(2)} dBFS" if m else "") + ")")
    if ep.thumb.exists():
        print(f"サムネイル: {ep.thumb}(動画の先頭フレームと同じ)")
    if not (e.get("ending") and img.exists()) and e.get("ending"):
        print("注意: グラレコ画像がまだないので、エンディング(グラレコ全景)のカードは入れていない。image の後に video を再実行する")


def cmd_status(ep, a):
    print("設定:")
    for k in ("style", "external_api", "minutes_format", "narration", "voice", "bgm", "bgm_gain", "clean_audio", "credit", "output_dir"):
        print(f"  {k}: {ep.cfg[k]!r}")
    print(f"  スタイルのフォルダ: {ep.style_dir}")
    print(f"  プロジェクト共通(設定・ルール・用語集): {ep.digesta}" + (f"(用語集 {len(glossary(ep.digesta))} 語)" if ep.digesta.exists() else "(なし)"))
    if ep.digesta_local.exists():
        print(f"  この会議(優先): {ep.digesta_local}(用語集 {len(glossary(ep.digesta_local))} 語)")
    if (ep.digest / "rules.md").exists():
        print(f"  注意: {ep.digest / 'rules.md'} は以前の置き場所。中身を {ep.digesta_local} に移して消す")
    if (ep.root.parent / "digest-rules.md").exists():
        print(f"  注意: {ep.root.parent / 'digest-rules.md'} は以前の置き場所。中身を digesta.md に移して消す")
    print(f"  Gemini API キー: {gemini_key_source()[1] or 'なし'}")
    if (ep.digest / "chars.yaml").exists():
        have = sorted(p.stem for p in (ep.digest / "chars").glob("*.jpg")) if (ep.digest / "chars").exists() else []
        print(f"  キャラクター画像: {', '.join(have) or 'なし'}(定義 {len(chars_spec(ep))} 体)")
    for label, f in [("録画", ep.media(VIDEO_EXT + AUDIO_EXT)), ("digesta.md", ep.digesta_local), ("minutes.md", ep.digest / "minutes.md"), ("グラレコ HTML", ep.grareco_src),
                     ("episode.yaml", ep.digest / "episode.yaml"), ("cuts.yaml", ep.digest / "cuts.yaml"), ("narration.md", ep.digest / "narration.md"),
                     ("議事録", ep.doc("minutes", "md") if ep.doc("minutes", "md").exists() else ep.doc("minutes", "docx")), ("画像 4K", ep.image("4k")), ("動画", ep.movie), ("サムネイル", ep.thumb)]:
        print(f"  {'○' if f.exists() else '×'} {label}: {f.relative_to(ep.root) if f.exists() else '(なし)'}")
    for src, out, what in [(ep.digest / "minutes.md", ep.doc("minutes", "md"), "議事録"), (ep.grareco_src, ep.image("4k"), "画像"), (ep.digest / "narration.md", ep.movie, "動画"), (ep.digest / "cuts.yaml", ep.movie, "動画"), (ep.digest / "episode.yaml", ep.movie, "動画")]:
        if src.exists() and out.exists() and src.stat().st_mtime > out.stat().st_mtime:
            print(f"  ※ {src.name} が{what}より新しい → 作り直しが必要")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=["init", "minutes", "sheet", "grid", "crop", "frames", "plan", "image", "narration", "bgm", "video", "voices", "chars", "status"])
    ap.add_argument("dir")
    ap.add_argument("args", nargs="*")
    ap.add_argument("--force", action="store_true", help="キャッシュを無視して作り直す")
    ap.add_argument("--only", help="narration / chars: 作り直す名前(カンマ区切り)")
    ap.add_argument("--no-bgm", action="store_true", help="video: BGM を入れない")
    ap.add_argument("--split", action="store_true", help="image: 章ごとのパネルも 16:9 の画像に切り出す")
    ap.add_argument("--step", type=int, default=150, help="sheet: フレーム間隔(秒)")
    ap.add_argument("--all", action="store_true", help="frames: 本編カットの最後のフレームも抜く")
    ap.add_argument("--format", choices=["md", "docx", "both"], help="minutes: 出力形式(省略時は設定の minutes_format)")
    a = ap.parse_args()
    ep = Ep(a.dir)
    ENV_DIRS[:] = [ep.root, ep.root.parent, Path.cwd()]
    {"init": cmd_init, "minutes": cmd_minutes, "sheet": cmd_sheet, "grid": cmd_grid, "crop": cmd_crop, "frames": cmd_frames, "plan": cmd_plan, "image": cmd_image, "narration": cmd_narration, "bgm": cmd_bgm,
     "video": cmd_video, "voices": cmd_voices, "chars": cmd_chars, "status": cmd_status}[a.cmd](ep, a)


if __name__ == "__main__":
    main()
