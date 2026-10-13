# スタイル

見た目は skill の `assets/styles/<名前>/` にまとまっていて、設定の `style` で選ぶ。テキスト(議事録、原稿、カット表、カードの文言)はスタイルに依存しないので、同じ会議を別のスタイルで出し直せる。

| スタイル | 向き | 特徴 |
|---|---|---|
| `doodle`(既定) | 勉強会、社内イベント、くだけた共有 | クリーム色の紙、手書きフォント、揺れる線の枠、人物アイコン、明るい BGM |
| `business` | 定例会議、報告、社外にも見せるもの | 白地、濃紺、ゴシック体(BIZ UDPGothic)、直線の枠、人物なし(名前の文字だけ)、単色の線画ピクトグラム、静かな BGM |
| `mono` | 落ち着いた記録。カラフルすぎるのは避けたいが、business ほど硬くしたくないとき | 黄・黒・グレーの3色だけ。白地、手書きフォント、黒い枠線、黄色のハイライト、黒地に白抜きの強調。イラストは doodle と同じ(色が3色に寄る)。静かなギターの BGM |
| `pop` | 会議の記録を明るく見せたいとき、参加者の顔ぶれを出したいとき | 白地にカラフルなパステルの帯と太い枠、手書きの見出し、番号付きパネル、下部に決定事項とネクストアクション。**キャラクターは Gemini の画像生成**で作った水彩風イラスト(`chars.yaml`)。明るいポップスの BGM |

## 切り替え方

1. プロジェクト全体か、その会議の `digesta.md` の設定に `style: business` と書く。
2. グラレコは、スタイルごとに書き方が違うので、そのスタイル用の HTML を書く。`digest/grareco.<style>.html` があればそれが使われ、なければ `digest/grareco.html`。両方のスタイルを残したいときは `grareco.doodle.html` と `grareco.business.html` のように分ける。雛形は `digest/lib/grareco-base.html`(選んだスタイルのものが同期される)。
3. 会議ごとの追加イラストも同様に、`digest/icons.<style>.js` があればそれを使う。
4. `digest.py image` → `digest.py video`。動画は本編の切り抜きを使い回し、カードと枠だけ撮り直す。BGM はスタイルの既定の指示文が違うので、作り直される(固定したいなら `bgm:` にファイルを指定)。
5. 見比べたいときは、会議の `digesta.md` の `output_dir` を `output_business` などにして出し分ける。

ユーザーが「硬い感じに」「キャラなしで」「ビジネス向けに」と言ったら business、「もっとゆるく」「手描き風に」なら doodle、「カラフルに」「議事録っぽいグラレコ」「人のイラストを入れて」なら pop、「色を抑えて」「3色くらいで」「黄色と黒で」なら mono。

mono のグラレコは doodle と同じ部品で書く。`data-box` の色名は `yellow`(薄い黄の塗り)、`gray`(グレーの線)、`white`、`none` だけを使い、強調は `<mark>`(薄い黄)か `.xl`(黒地に白抜き)にする。doodle 用に書いた HTML から色指定を置き換えるだけで移せる。

## pop スタイルのキャラクター(Gemini 画像生成)

pop は人物を Gemini の画像生成モデル(`image_model`、既定 `gemini-3.1-flash-image`)で作る。1枚ずつ API を呼ぶので、`external_api: allow` が必要。

1. `digest/chars.yaml` に、キャラクターの名前(ファイル名になる英数字)と、見た目・ポーズの英文を書く。**実在の人物の似顔絵にはしない。人名、会社名、会議の内容は書かない**(Google に送られるのはこの文だけ)。発表の内容を暗示する小物(猫、雲の中の箱、うちわ)を持たせると、グラレコで何の話か伝わる。
   **年齢、体型、ひげ、しわなど、本人が見て気にしそうな特徴は書かない。** スタイルの共通指示(`char_style`)が全員を「清潔感のある成人」に同じ調子でデフォルメするので、区別は髪型・髪色・服の色・小物・ポーズで付ける。性別も書かなくてよい(`A person with …` でよい)。本人が目にする成果物なので、似せることより、見て嫌な気持ちにならないことを優先する(ユーザーの指示)。
   ```yaml
   - name: minato
     prompt: An adult man in his 40s with short black hair and glasses, wearing a purple shirt, smiling and holding a small cat.
   ```
2. `digest.py chars <会議>` で生成する。出力は `digest/chars/<name>.jpg`(白背景の JPEG。`mix-blend-mode: multiply` で白が消えるので、色の帯の上にも置ける)。プロンプトが同じなら再生成しない。やり直しは `--only 名前 --force`。
3. 生成した画像は必ず見る。写真調になっていないか、人数が1人か、文字が入っていないか。写真調になるときは、スタイルの共通指示(`style.yaml` の `char_style`)が効いていない可能性があるので、`digest.py status` で `style: pop` になっているか確かめる。
4. 使う場所:
   - 動画: `episode.yaml` の章に `char: minato` と書くと、章タイトルカード、まとめカード、本編の枠の右下に出る。オープニングの一覧にも出る。
   - グラレコ: `<img class="char" src="chars/minato.jpg">`。ヘッダーの参加者一覧(`.cast`)と、各パネルの右下(`.panel img.char`)が定位置。
5. 画像は `digest/chars/` に残る(`work/` ではない)。生成に費用がかかるので、消さない。

### pop のグラレコの部品

doodle の部品(`tag` `big` `xl` `note` `bub` `chip` `ar` `qa` `data-box`)に加えて:

| 部品 | 書き方 | 用途 |
|---|---|---|
| パネル | `<section class="panel c1" data-box="purple,purple" data-sw="4" data-r="18">` | 章。`c1`〜`c7` でテーマ色。`data-box` の色名は PAL の名前 |
| リボン | `<span class="ribbon" style="background:var(--c1)">決定事項</span>` | 角が斜めの帯見出し |
| 薄い帯 | `<div class="tint">…</div>` | パネル内の小区画 |
| 参加者 | `<div class="cast"><div class="p"><img class="char" src="chars/x.jpg">名前<br><span class="k">(役)</span></div>…</div>` | ヘッダーの顔ぶれ |
| 工程 | `<div class="steps"><div class="st" data-box="white,purple" data-sw="2"><i data-ico="cat" data-s="40"></i><b>見出し</b>補足</div><span class="ar">→</span>…</div>` | 流れ |
| 決定事項 / タスク表 | `<ol class="dec">` / `<table class="todo">` | 下部 |

パネルの右下にキャラを置くときは、重なる要素に `style="margin-right:215px"` を付けて避ける。

## business スタイルでのグラレコの書き方

雛形 `grareco-base.html`(business)の構成は、会議の議事録を1枚にしたもの。

```
ヘッダー: タイトル / 日時・場所 / 参加者(文字) / アジェンダ(番号付き)
本体:     議題(章)ごとの番号付きパネル。3列が基本
下部:     決定事項(番号付き) / ネクストアクション(タスク・担当・期限の表)
```

勉強会のように決定事項がない会議では、下部を「各発表の持ち帰り」と「連絡事項・次回」に読み替える。

部品(CSS クラス):

| 部品 | 書き方 | 用途 |
|---|---|---|
| パネル | `<section class="panel c1">` | 章。`c1`〜`c3` でテーマ色。ヘッダーは `<div class="hd"><span class="num">1</span><div><div class="ttl">題名</div><div class="who">発表: ◯◯</div></div></div>` |
| 札 | `<span class="tag">見出し</span>` | 枠線だけの小さな見出し |
| 強調 | `<div class="big">…</div>` / `<span class="xl">数字</span>` / `<mark>語</mark>` | 太字、大きい色文字、青太字(蛍光ペンの代わり) |
| 注記 | `<div class="note">…</div>` | 補足。グレーの小さめの文字 |
| 枠 | `<div class="box">…</div>` / `<div class="tint">…</div>` | 細い罫線の枠 / 薄い色の帯 |
| 工程 | `<div class="steps"><div class="st"><b>A</b>補足</div><span class="ar">→</span>…</div>` | 流れ |
| チェック箇条書き | `<ul class="pts"><li>…</li></ul>` | 項目 |
| 質疑 | `<span class="qa">Q</span>` | 質疑の印 |
| ○△ | `<span class="ok">○</span>` / `<span class="ng">△</span>` | 可否 |
| 決定事項 | `<ol class="dec">` | 下部の番号付き |
| タスク表 | `<table class="todo">` | 下部の表(タスク・担当・期限) |
| ピクトグラム | `<i data-ico="名前" data-s="36" data-c="blue"></i>` | 単色の線画。`data-c` はテーマ色の名前か色コード |

doodle と同じ `data-box` 属性も使えるが、揺れない直線の枠に変換される。

ピクトグラムの名前(`assets/styles/business/pict.js`): `calendar` `check` `bulb` `target` `chart` `trend` `people` `person` `clock` `flag` `warning` `question` `note` `rocket` `doc` `gear` `cloud` `server` `laptop` `phone` `mail` `chat` `search` `money` `home` `wrench` `shield` `arrow` `cycle` `thermo` `pin` `mic` `list` `numbered`。人物の絵は用意していない(人は名前の文字で表す)。

追加するときは `digest/icons.business.js` に、`Object.assign(ICONS, { 名前(p) { p.rect(...); p.path("M…"); } })` の形で書く。ペンのメソッドは `rect(x,y,w,h,r)` `circ(cx,cy,r)` `line(x1,y1,x2,y2,太さ)` `path(d,塗り,太さ)` `poly(点)` `dot(cx,cy,r)` `text(x,y,文字,サイズ)`。100x100 の枠に、太さ4前後の線で、塗りなしで描く。

書き方の心得:

- 装飾より情報の密度。1パネルに「要点の見出し → 根拠や経緯 → 結論」の順で並べる。
- 強調は色文字(`mark`)と太字だけ。蛍光ペンや吹き出しは使わない。
- 発表者・参加者は文字で書く(`.who`、ヘッダーの `.kv`)。
- 数字と固有名詞は正確に。business の読者は内容を仕事に使う。

## 同梱していないスタイルを使う(styles_path)

企業のブランド配色など、公開しないスタイルは skill の外のフォルダに置き、設定 `styles_path` で探す場所に足す。フォルダの中身は `assets/styles/` と同じ形(`<スタイル名>/style.yaml` など)。

```yaml
---
styles_path: ~/src/my-digesta-themes/styles   # プロジェクトか会議の digesta.md の冒頭に書く
style: mybrand
---
```

- 複数あるときは `:` 区切りか YAML のリスト。相対パスはプロジェクトのフォルダ(会議の親)から解決する。
- 環境変数 `DIGESTA_STYLES_PATH` にも同じ形式で書ける(全プロジェクトに効かせたいとき)。
- 同じ名前のスタイルは、`styles_path` > `DIGESTA_STYLES_PATH` > 同梱、の順に先に見つかったものを使う。
- 実際に使われたフォルダは `digest.py status` の「スタイルのフォルダ」に出る。

## 新しいスタイルを追加する

`assets/styles/<名前>/`(公開しないなら `styles_path` のフォルダの `<名前>/`)に次を置く。既存のスタイルをコピーして直すのが早い。キャラクター画像を使うスタイルは、`style.yaml` に `char_style`(画像生成プロンプトの共通の前置き)を書き、cards / frame / grareco で `../chars/<name>.jpg` を参照する。

| ファイル | 役割 |
|---|---|
| `style.yaml` | 名前、説明、フォント(Google Fonts の OFL フォント。ファイル名: [フォルダ, family, weight])、字幕フォント、動画の背景色 `paper`、BGM の既定の指示文 |
| `cards.html` | 動画のカード5種(opening / chapter / recap / ending / outro)と、任意でサムネイル(`<section id="thumb">`。タイトルスライドの体裁。動画の先頭フレームと `_サムネイル.png` になる。無ければ opening の完成状態を使う)。`#id=…&ch=…&nd=…&img=…` で内容を切り替え、`window.seek(ms)` と `window.END` と `window.READY` を実装する |
| `frame.html` | 本編の枠。`#ch=…&topic=…`。スライド領域(44,104 から 1344x756)を透明にする |
| 描画部品の JS | `ICONS` / `icon()` / `mountIcons()` / `mountBoxes()` / `mountArrows()` / `PAL`(章の色名 → `{hex, tint}`)を定義する。cards / frame / grareco から呼ばれる |
| `grareco-base.html` | グラレコの雛形。`lib/fonts.css` と `lib/<描画部品>.js` と `lib/icons.js` を読み込み、描画が終わったら `window.READY = true` にする |

`episode.yaml` の項目(`chapters[].color` の色名、`face`、`deco`、`recap`、`ending`、`outro`)はすべてのスタイルで同じ意味に解釈されるようにする。使わない項目は無視してよい(business は `face` を無視する)。
