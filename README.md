# show-spark-v3

アニメシーズン視聴管理ツール。

- 要件 → [仕様.md](./仕様.md)
- 構成・開発ルール → [AGENT.md](./AGENT.md)

> **現在のステータス: 設計中（コード未実装）**
> 以下のコマンドはこれから実装する。

---

## 前提

- Node.js 22+
- Python 3.12+
- Docker
- Auth0 の dev テナント（Allowed Callback URLs に `http://localhost:3000/api/auth/callback` を追加しておく）

## セットアップ

```bash
npm install
npm run setup                          # apps/web の install と apps/api の venv 作成
cp apps/web/.env.example apps/web/.env.local
cp apps/api/.env.example  apps/api/.env  # Auth0 の Domain / Audience / Client ID を記入
npm run db:reset                       # ローカルDBを作成してシード投入
```

## 起動

```bash
npm run local
```

| | URL | プロセス |
|---|---|---|
| Web | http://localhost:3000 | `next dev` |
| API | http://localhost:8000 （docs: `/docs`） | `uvicorn --reload` |
| DB | localhost:5432 | Docker の `postgres:17` |

個別に起動する場合:

```bash
npm run local:db
npm run local:api
npm run local:web
```

開発はすべてローカルで完結させる。フロントだけ起動して DB や API を staging に向ける運用はしない。

## DB

```bash
npm run db:migrate    # db/migrations/*.sql を適用
npm run db:reset      # DROP → migrate → seed。壊したらこれで戻す
npm run db:psql       # psql で接続
```

## 型生成

```bash
npm run gen:types     # API 起動中に実行。packages/api-types を再生成する
```

生成物はコミットする。CI で差分が出ると fail する。

## テスト

```bash
npm test              # web + api のユニット/結合
npm run test:web
npm run test:api
npm run test:e2e      # Playwright（web を起動した状態で実行）
npm run lint
npm run typecheck
```

## 動作確認

ローカルで一通り触って確認する項目。

1. **同時編集** — ブラウザを2枚（別プロファイル・別ユーザー）で同じシーズンのボードを開く。片方でカードを別の曜日にドラッグし、もう片方に数秒以内で反映されること。
2. **入力の保護** — 上記の状態で、片方の詳細モーダルのメモ欄にフォーカスして入力し続ける。もう片方から同じ作品を編集しても、入力中の文字が消えないこと。
3. **ソート順** — シードに週跨ぎのデータ（配信=日曜 / 放送=土曜25:00）が入っている。並び順が逆転しないこと。
4. **PNG出力** — 出力してダウンロードし、確定作品だけが載ること、日本語が豆腐にならないこと、プレビューと一致すること。
5. **画像のリンク切れ** — シードに到達不能なURLが1件入っている。フォールバック表示が出ること。
6. **画面幅** — 1920px で8列が収まること。狭めたときに崩れないこと。

## デプロイ

| ブランチ | 環境 | 動作 |
|---|---|---|
| `develop` | staging | push で自動デプロイ |
| `main` | production | push で自動デプロイ |

フロントは Vercel、API は GitHub Actions から SAM でデプロイされる。

**DBマイグレーションだけは自動で走らない。** GitHub Actions の `db-migrate` ワークフローを手動 dispatch し、対象環境を選んで実行する。

staging はローカルで再現できないもの（API Gateway の JWT Authorizer、Lambda のコールドスタート、Supavisor 経由の接続）を確認する場所で、日常の開発では使わない。
