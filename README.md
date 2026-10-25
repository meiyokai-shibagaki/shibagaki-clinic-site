# 柴垣医院 ホームページ（静的サイト）

医療法人社団明洋会 柴垣医院（自由が丘・戸越・久が原）のホームページを、サーバー側のプログラムを持たない静的サイトとして構築したものです。現在はテスト公開（関係者限定・Basic 認証付き）の段階です。

- 公開先（テスト）：https://shibagaki-clinic-test.netlify.app
- 本番ドメイン（予定）：https://shibagaki.clinic

## 構成の考え方

| 項目 | この構成 |
|---|---|
| 配信 | 生成済みの HTML を Netlify（CDN）で配信。WordPress や PHP など、サーバー側で動くプログラムは無い |
| セキュリティ | `netlify.toml` でセキュリティヘッダー（CSP・HSTS・X-Frame-Options ほか）を付与。認証情報はリポジトリに置かず、Netlify の環境変数で管理 |
| 問合せフォーム | 自前のフォーム5種（お問い合わせ／採用―応募／採用―見学・相談／地域連携―勉強会申込／地域連携―個別相談）。必須・入力形式・同意のチェックとスパム対策（ハニーポット）付き。送信は Netlify Forms |
| お知らせ・採用 | `src/data/news.json`・`src/data/recruit.json` に記述。編集画面（/admin/・Decap CMS）から追加・更新でき、保存すると自動でビルド・反映 |

デザイン・文章・写真は現行サイトのものを移植しています。本文フォントは Google Fonts の「Zen Old Mincho」です。

## フォルダ構成

```
.
├── build.py            … サイト生成スクリプト（Python 標準ライブラリのみ・外部パッケージ不要）
├── src/
│   ├── template.html   … 全ページ共通の骨組み
│   ├── base.css / site.js
│   ├── data/           … site.json（拠点・ナビ）・pages.json・news.json・recruit.json・slides.json・image_notes.json
│   ├── pages/          … 各ページの本文（HTML）とページ専用 CSS
│   └── forms/          … フォーム5種
├── site/               … 生成結果（公開されるファイル。画像・編集画面 /admin/ を含む）
├── netlify.toml        … ビルド・セキュリティヘッダー・エッジ関数の設定
├── netlify/edge-functions/auth.ts … テスト公開中の Basic 認証
├── tools/make_area_map.py … 訪問エリア地図（SVG）の生成
└── preview.sh          … ローカル確認用
```

## ローカルで見る

```bash
python3 build.py
./preview.sh   # http://localhost:8787
```

`build.py` は内部リンク切れを検査し、`sitemap.xml`・`robots.txt`・構造化データ（JSON-LD）を生成します。

## お知らせ・採用を追加する

- お知らせ：`src/data/news.json` に1件追加（日付・タイトル・本文・公開／下書き）。トップの「お知らせ」欄・一覧・詳細ページが自動で生成されます。
- 採用：`src/data/recruit.json` の `positions` に職種を追加。募集終了の切替も同じファイルで行い、応募フォームの職種選択肢も連動します。
- 編集画面：公開後は `/admin/` から同じ内容をブラウザで編集できます（Netlify Identity ＋ Git Gateway の有効化が必要）。

## 公開と更新

- GitHub の `main` にプッシュすると Netlify が自動でビルドして公開します（build：`python3 build.py`、publish：`site`）。
- 手動で出す場合は `netlify deploy --prod --build`（`--no-build` ではエッジ関数が同梱されず Basic 認証が外れるため使わない）。
- テスト公開の間は検索エンジンに載せない設定です（`X-Robots-Tag: noindex` と `<meta name="robots">`）。本番に切り替えるときは `src/data/site.json` の `production` を `true` にし、`netlify.toml` の `X-Robots-Tag` 行と `[[edge_functions]]`（Basic 認証）を外します。canonical・OGP・sitemap の URL は `production_base_url` に切り替わり、テストバナーが消えます。
- 関係者限定の入口（`netlify/edge-functions/auth.ts`）：日本語のログイン画面（ID とパスワード・Cookie で 30 日保持）と、確認用の Basic 認証ヘッダー（`curl -u`）の両方に対応。ID とパスワードは Netlify の環境変数（`SITE_USER` / `SITE_PASS`）で管理し、リポジトリには置きません。パスワードを変えると全員のログインが無効になります。

## ライセンス・著作権

サイトの文章・写真・ロゴの著作権は医療法人社団明洋会に帰属します。
