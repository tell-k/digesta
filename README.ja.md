# digesta

[English](README.md) | 日本語

会議や勉強会の録画と文字起こしから、次の3つを作る Claude Code のプラグイン(skill)。名前はラテン語で「整理してまとめたもの」。

| 成果物 | 内容 | 出力 |
|---|---|---|
| 議事録 | 決定事項や発表の要点をまとめた文書 | Markdown、指定すれば docx(`<名前>_要約.md`) |
| グラレコ画像 | 内容を1枚にまとめた手描き風の画像 | PNG(`<名前>_グラレコ_4k.png`、`_1920.png`) |
| ダイジェスト動画 | 発言者本人の声の切り抜きに、字幕、ナレーション付きのカード、BGM を付けた数分の動画 | mp4(`<名前>_ダイジェスト.mp4`、1920x1080) |

見た目は4つのスタイルから選べる。`doodle` は手描き風でキャラクターあり(勉強会向け)、`business` は白地・ゴシック体・直線でキャラクターなし(会議や報告向け)、`pop` はカラフルな議事録風で、人物のイラストを Gemini の画像生成で作る(明るく見せたい会議向け)、`mono` は黄・黒・グレーの3色だけの落ち着いた見た目。設定の `style` で切り替え、同じ内容を別のスタイルで出し直せる。

内容はすべてテキストで持つ。議事録、ナレーション原稿、カット表、ルールを直して同じコマンドを実行すれば、直した箇所に関係する部分だけが作り直される。

## インストール

Claude Code で、マーケットプレイス [tell-k/agent-skills](https://github.com/tell-k/agent-skills) を追加してからインストールする。

```
/plugin marketplace add tell-k/agent-skills
/plugin install digesta@tell-k
```

更新は `/plugin marketplace update tell-k` のあと `/plugin` から。手元のクローンを直接読み込むなら `claude --plugin-dir /path/to/digesta`。

## 使い方

Claude Code で、会議のフォルダを並べたプロジェクトのフォルダ(例: `tech-lunch/`)を開いて実行する。プラグインの skill なので、コマンド名は `/digesta:digesta`(環境によっては `/digesta` でも呼べる)。

```
/digesta <会議のディレクトリ> [minutes|image|video|all] [--fresh] [直したい内容]
```

| 例 | やること |
|---|---|
| `/digesta tech-lunch/012` | 議事録、画像、動画を全部作る |
| `/digesta tech-lunch/012 minutes` | 議事録だけ(数分で終わる) |
| `/digesta tech-lunch/012 minutes,image` | 議事録と画像 |
| `/digesta tech-lunch/012 image 章ごとにも分割して` | グラレコに加えて、章ごとの 16:9 画像(`<名前>_グラレコ_章N.png`)も出す。Slack のスレッドに1章ずつ貼るとき |
| `/digesta tech-lunch/012 video` | 動画だけ。テキストを直したあとの作り直しもこれ |
| `/digesta tech-lunch/012 minutes docx でも出して` | 議事録を docx でも出す |
| `/digesta tech-lunch/012 video BGM を小さく` | 直したい内容を文章で添える |
| `/digesta tech-lunch/012 --fresh` | 既存のテキストを捨てて、素材から書き直す |

会議 1 回につき新しいセッションで始めると、Claude Code の使用量が少なくて済む(長いセッションの続きで始めると、会話の文脈を毎回読み直すぶんが数倍になる)。skill の中では、カット表・グラレコ・検査の 3 工程をサブエージェントに任せ、文字起こしやフレームの確認は保存したファイルから必要な部分だけ読む作りにしてある(`references/agents.md`)。

コマンドを使わず、「012 の議事録を作って」「ナレーションを直したから動画を更新して」と頼んでもよい。

所要時間の目安は、議事録が数分、画像が 10〜20 分、動画が初回 40〜60 分(素材の読み込みとカット選びを含む。ビルドだけなら 20〜30 分)。テキストを直したあとの動画の作り直しは、直した範囲によって 2〜10 分。

## 必要なもの

| もの | 用途 | 備考 |
|---|---|---|
| macOS | 動作確認した環境 | Intel Mac で確認。文字起こしは Apple シリコンのほうが速い |
| [uv](https://docs.astral.sh/uv/) | スクリプトの実行 | Python の依存は自動で入る |
| ffmpeg | 動画と音声の処理 | libass 付き(Homebrew 版でよい) |
| pandoc | docx の文字起こしの取り込み、議事録の docx 出力 | なくても Markdown の議事録は作れる |
| Gemini API キー | 動画のナレーション(Gemini TTS)と BGM(Lyria) | 任意。なければ macOS の音声、BGM なしで作る。Lyria は課金が有効なキーが必要 |
| Docker | VOICEVOX でナレーションを作るとき | 任意 |

フォント(Google Fonts の OFL フォント5種)と描画用の Chromium は、初回に自動でダウンロードする。フォントは `~/.cache/digesta/fonts/` に置かれる。

### Gemini API キーの置き方

プロジェクトのフォルダ(例: `tech-lunch/`)に `.env` を作り、次の1行を書く。

```
GEMINI_API_KEY=ここにキー
```

キーは次の順に探し、最初に見つかったものを使う。

1. 会議のフォルダの `.env`(例: `tech-lunch/012/.env`)
2. プロジェクトのフォルダの `.env`(例: `tech-lunch/.env`)
3. コマンドを実行した場所の `.env`
4. 環境変数 `GEMINI_API_KEY`
5. `~/.config/digesta/gemini.env`(キーだけの1行でも、`GEMINI_API_KEY=...` の形でもよい)

`.env` では `GOOGLE_API_KEY` という名前でも読む。どこから読んでいるかは `digest.py status <会議>` の「Gemini API キー」の行で分かる(キー本体は表示しない)。

注意:

- キーをチャットに貼らない。クリップボードから書き込むなら、Claude Code とは別のターミナルで `printf 'GEMINI_API_KEY=%s\n' "$(pbpaste)" >> .env` とする。
- `.env` を git で管理するフォルダに置くなら、`.gitignore` に `.env` を入れる。
- 他人に渡す成果物(`output/`)に `.env` は含まれない。フォルダごと共有するときは `.env` を外す。

## 入力

会議1回分のフォルダに、次を置く。

- **録画**: mp4 / mov / m4v / mkv / webm。音声だけ(m4a / mp3 / wav)でも議事録と画像は作れる
- **文字起こしやメモ**: docx(Google Meet の Gemini メモなど)、vtt / srt(Zoom や Teams の字幕)、txt、md。なくても、ローカルで全編を文字起こしして作れる(時間がかかり、話者の区別はつかない)

## フォルダ構成

```
<プロジェクト>/                 例: tech-lunch/
├── digesta.md                 プロジェクト共通の設定・ルール・用語集  ← 人が編集する
└── <会議>/                    例: 012/
    ├── 録画と文字起こし        元素材。skill は変更しない
    ├── digesta.md             この会議の設定・ルール・用語集        ← 人が編集する
    ├── digest/
    │   ├── minutes.md         議事録の正本                         ← 人が編集する
    │   ├── grareco.html       グラレコ本体                         ← 人が編集する
    │   ├── icons.js           この会議だけの追加イラスト           ← 人が編集する
    │   ├── episode.yaml       動画のカードの文言                   ← 人が編集する
    │   ├── cuts.yaml          動画のカット表と字幕                 ← 人が編集する
    │   ├── narration.md       動画のナレーション原稿               ← 人が編集する
    │   ├── lib/               描画ライブラリ(自動生成。編集しない)
    │   └── work/              中間ファイルとキャッシュ(消してよい)
    └── output/                成果物
```

`digest/` と、プロジェクト・会議の `digesta.md` は、最初に実行したときに作られる。

## 直し方

成果物を見て直したくなったら、正本のテキストを編集して同じコマンドを実行する。Claude に文章で頼んでもよい。

| 直したいもの | 編集するファイル | 実行 |
|---|---|---|
| 議事録の文言 | `digest/minutes.md` | `minutes` |
| グラレコの文言やレイアウト | `digest/grareco.html` | `image` |
| ナレーションの言い回し、読み方 | `digest/narration.md` | `video` |
| 字幕、切り抜く場面、言葉の頭切れ | `digest/cuts.yaml` | `video` |
| カードの文言(タイトル、まとめ、締めの告知) | `digest/episode.yaml` | `video` |
| 声、BGM の有無や音量、議事録の形式 | 会議かプロジェクトの `digesta.md` の設定 | `video` / `minutes` |
| スタイル(手描き風 ↔ ビジネス) | 設定の `style`。グラレコはスタイル用に書き直す(`grareco.<style>.html`) | `image` → `video` |

動画は、変わった部分だけを作り直す。ナレーションを1文直せば、そのカードの音声と映像だけがやり直しになる。

YAML を手で直すときは、値に「 #」(空白のあとのシャープ)や「: 」を含む場合に引用符で囲む。囲まないと、そこから後ろが欠ける。

## ルールと設定

ルールは自由記述の Markdown で、3層ある。下にあるものほど優先される。

| 層 | ファイル | 書くこと |
|---|---|---|
| skill 共通 | `references/rules.md` | どの会議にも効くこと。事実の扱い、表記、秘密情報 |
| プロジェクト共通 | `<プロジェクト>/digesta.md` | 会議の種類、議事録の型、動画の尺、締めの告知、使わない素材。最後の「## 用語集」に人名・用語の表記、読み、聞き違い |
| 会議ごと | `<会議>/digesta.md` | プロジェクト共通と同じ形で、その会議だけの条件。「12:30〜14:00 は顧客の画面なので使わない」「◯◯さんの名前は文字起こしだと△△になる」など |

どのファイルも冒頭に `---` で挟んだ設定欄がある。会議ごとの設定が、プロジェクト共通の設定を上書きする。

| キー | 値 | 既定 | 説明 |
|---|---|---|---|
| `style` | `doodle` / `business` / `pop` / `mono`、または `styles_path` にあるスタイル名 | `doodle` | 見た目のスタイル |
| `styles_path` | フォルダのパス(`:` 区切りかリスト) | 空 | 同梱していないスタイルを探すフォルダ。下の「独自のスタイル」を参照 |
| `image_model` | モデル ID | `gemini-3.1-flash-image` | pop のキャラクター画像の生成に使う |
| `external_api` | `ask` / `allow` / `deny` | `ask` | Gemini にナレーション原稿などを送ってよいか。下の「外部送信」を参照 |
| `minutes_format` | `md` / `docx` / `both` | `md` | 議事録の出力形式 |
| `narration` | `gemini` / `voicevox` / `say` / `none` | `gemini` | 動画のナレーションの作り方 |
| `voice` | 声の名前 | `Leda` | gemini の声 |
| `voice_style` | 英文 | 明るい若い女性の語り | gemini への口調の指示 |
| `bgm` | `lyria` / `none` / ファイルのパス | `lyria` | 動画の BGM。パスは会議のディレクトリからの相対 |
| `bgm_gain` | 数値 | `0.166` | BGM の基準音量。声がある間は自動でさらに下がる |
| `bgm_prompt` | 英文 | スタイルの既定 | Lyria への曲の指示。doodle は明るいウクレレ、business は静かなピアノ |
| `clean_audio` | `true` / `false` | `true` | 元音声の整音(低域カット、軽いノイズ除去、軽いコンプレッサー) |
| `credit` | 文字列 | 空 | 動画の締めカード最下部の表記 |
| `output_dir` | パス | `output` | 成果物の出力先 |
| `video` | ファイル名 | 自動 | 録画が複数あるときに指定する |
| `asr_prompt` | 文字列 | 空 | 文字起こしに渡す固有名詞のヒント |

## 外部送信

- **議事録と画像**は、外部に何も送らずに作る(素材を読むのは、この Claude Code のセッション自身)。
- **動画**の既定は、ナレーションが Gemini TTS、BGM が Lyria で、ナレーション原稿(会議の要約 10 文ほど)と音楽の指示が Google に送られる。
- **pop スタイルのキャラクター**は Gemini の画像生成で作る。送られるのは `digest/chars.yaml` に書いた見た目とポーズの英文だけ(人名や会議の内容は書かない)。
- プロジェクトで初めて動画を作るときに、送ってよいかを一度だけ尋ねる。答えは `digesta.md` の `external_api` に記録され、以後は尋ねない。
- `deny` にすると、ナレーションは macOS の音声、BGM なしになる。ローカルで自然な声を使いたいときは `narration: voicevox` にする。

## 利用規約とクレジット

- **VOICEVOX** を使うときは、動画内か投稿文にクレジット表記(例: `VOICEVOX:四国めたん`)が要る。社内限定・非公開でも例外はない。`credit` に書かないとビルドが止まる。
- **Gemini TTS / Lyria** には、クレジット表記の義務が見当たらなかった(2026-10 時点)。生成した音声には、聞こえない電子透かし(SynthID)が入る。
- **フォント**(Yusei Magic、Zen Kurenaido、Klee One、Zen Maru Gothic、Mochiy Pop One)は SIL Open Font License。
- **rough.js**(手描き風の線)は MIT License。`assets/styles/*/rough.js` に同梱している。

## 気をつけること

- 自動の文字起こしは人名を聞き違える。成果物に出た人名のうち、文字起こしだけが根拠のものは「要確認」として報告されるので、目を通す。
- Claude は音を聞けない。ナレーションの読みは文字起こしで検証しているが、声の抑揚、BGM の音量、整音の効き具合は耳で確かめる。
- Gemini TTS は実行のたびに読みや抑揚が少し変わる。同じ原稿でも、作り直すと別のテイクになる。
- 気に入った BGM は `work/` の外にコピーし、`bgm: そのパス` に固定しておくと、設定や skill の更新で作り直されない。
- `digest/work/` を消すとキャッシュがなくなり、次の動画ビルドは全部作り直しになる(ナレーションと BGM も再生成される)。

## 独自のスタイル

企業のブランド配色など、公開しないスタイルは別のフォルダ(別リポジトリでもよい)に `<スタイル名>/style.yaml` などを置き、プロジェクトの `digesta.md` の設定で探す場所に足す。

```yaml
---
styles_path: ~/src/my-digesta-themes/styles
style: mybrand
---
```

環境変数 `DIGESTA_STYLES_PATH` でも指定できる。スタイルの作り方は `skills/digesta/references/styles.md` の「新しいスタイルを追加する」。

## 中身

```
digesta/
├── .claude-plugin/plugin.json   プラグインの定義
├── README.md                    このファイル
└── skills/digesta/
    ├── SKILL.md                 Claude が読む手順
    ├── scripts/
    │   ├── digest.py            ビルドツール(init / status / minutes / image / video / narration / bgm / voices / sheet / grid / crop / frames / plan)
    │   ├── asr.py               文字起こし(カット点の特定、音声の検証)
    │   └── usage.py             セッションのトークン使用量の集計
    ├── references/
    │   ├── rules.md             共通ルール
    │   ├── agents.md            サブエージェントに任せる工程
    │   ├── minutes-guide.md     議事録の作り方
    │   ├── grareco-guide.md     グラレコ画像の作り方(doodle)
    │   ├── styles.md            スタイルの選び方・切り替え方・追加の仕方、business のグラレコの書き方
    │   └── video-guide.md       ダイジェスト動画の作り方
    └── assets/
        ├── styles/
        │   ├── doodle/          手描き風スタイル(イラスト部品、カード、動画の枠、グラレコ雛形)
        │   ├── business/        ビジネススタイル(同上。ピクトグラムは単色の線画)
        │   ├── pop/             カラフルな議事録風スタイル(キャラクターは Gemini で生成)
        │   └── mono/            黄・黒・グレーの3色スタイル
        ├── templates/           ひな形(ルール、議事録、動画の3つのテキスト)
        ├── examples/            作例(架空の勉強会 study/)
        └── reference.docx       議事録 docx の体裁のひな形
```

スクリプトは単体でも使える(`<digesta>` はこのリポジトリの場所)。

```bash
uv run <digesta>/skills/digesta/scripts/digest.py --help
uv run <digesta>/skills/digesta/scripts/digest.py status tech-lunch/012
uv run <digesta>/skills/digesta/scripts/digest.py minutes tech-lunch/012 --format both
uv run <digesta>/skills/digesta/scripts/digest.py video tech-lunch/012
```

プロジェクトで最初に実行したときに `digesta.md` が作られるので、会議の種類や表記の決まりを書き足す。

## 困ったとき

| 症状 | 対処 |
|---|---|
| 「外部 API に内容を送る。…まだ確認が取れていない」で止まる | `digesta.md` の `external_api` を `allow` か `deny` にする |
| 「Gemini の API キーがない」 | プロジェクトのフォルダの `.env` に `GEMINI_API_KEY=...` を書く。`digest.py status` で読み込み元を確認できる |
| Lyria が HTTP 429 や課金のエラーになる | 課金が有効なキーにするか、`bgm: none` にする |
| 「Chromium がない」 | `uv run --with playwright playwright install chromium-headless-shell` |
| 「VOICEVOX エンジンに繋がらない」 | Docker を起動して `docker run -d --name voicevox_digesta -p 127.0.0.1:50021:50021 voicevox/voicevox_engine:cpu-latest` |
| 「録画ファイルが 2 個ある」 | 会議の `digesta.md` の設定に `video: ファイル名` を書く |
| カードの文言が途中で切れる | YAML の値に「 #」か「: 」がある。引用符で囲む |
| 言葉の頭や語尾が切れている | `digest/cuts.yaml` の `start` を前へ、`end` を後ろへ 0.2〜0.4 秒ずらす |
| 文字起こしが遅い | Intel Mac では実時間より遅い。候補区間だけを起こす作りなので、全編の文字起こし(`asr.py full`)は必要なときだけ使う |

## ライセンス

MIT License(`LICENSE`)。同梱の rough.js は MIT License、フォントは初回にダウンロードする SIL Open Font License のもの。
