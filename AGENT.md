# AGENT.md

このリポジトリの構成と開発ルール。要件は [仕様.md](./仕様.md)、コマンドは [README.md](./README.md) を参照。ここには両者に書かないこと（構成の意図とルール）だけを書く。

---

## リポジトリ構成

単一リポジトリに web と api を同居させる。npm workspaces / Turborepo は使わない（TS と Python で言語が異なり、共通ビルドグラフの利点がないため）。ルートの `package.json` はタスクランナー専用で、アプリの依存を持たない。

```
show-spark-v3/
├── package.json                 # スクリプトのみ
├── docker-compose.yml           # ローカル用 Postgres 1コンテナ
│
├── apps/
│   ├── web/                     # Next.js。Vercel の Root Directory に指定する
│   │   ├── src/
│   │   │   ├── app/
│   │   │   │   ├── dashboard/
│   │   │   │   └── seasons/[slug]/      # slug は 2026-autumn 形式
│   │   │   ├── components/
│   │   │   │   ├── ui/          # shadcn/ui の生成物。直接編集しない
│   │   │   │   ├── board/       # Kanban / Column / AnimeCard / SizeSwitcher
│   │   │   │   ├── detail/      # DetailModal（自動保存）
│   │   │   │   └── export/      # PngPreview。このDOMがそのまま出力画像になる
│   │   │   ├── features/        # 画面をまたぐドメインロジック
│   │   │   │   ├── sort/
│   │   │   │   ├── sync/
│   │   │   │   └── weekday/
│   │   │   ├── lib/             # api-client.ts / auth.ts
│   │   │   └── styles/fonts/    # 日本語Webフォント（同一オリジン配信）
│   │   └── e2e/                 # Playwright
│   │
│   └── api/                     # FastAPI
│       ├── src/app/
│       │   ├── main.py          # FastAPI インスタンス + Mangum handler
│       │   ├── routers/         # seasons / animes / tags / members
│       │   ├── schemas/         # Pydantic
│       │   ├── services/        # ユースケース
│       │   ├── repositories/    # SQL
│       │   ├── db.py
│       │   ├── auth.py
│       │   └── core/config.py
│       ├── tests/{unit,integration}/
│       └── template.yaml        # AWS SAM
│
├── packages/api-types/          # OpenAPI から生成した TS 型（生成物をコミット）
├── db/
│   ├── migrations/              # 連番の素のSQL
│   └── seed.sql
├── docs/                        # ADR
└── .github/workflows/
```

S3 は使わない。作品画像は外部URLの参照のみ、出力PNGはブラウザでダウンロードするだけで、保存すべき実体が存在しない。将来必要になったら追加する。

---

## API の層と責務

```
routers/  →  services/  →  repositories/  →  db
```

- **routers** — HTTP の入出力だけ。ビジネスロジックを書かない。
- **schemas** — Pydantic で境界バリデーション。範囲制約（曜日 1-7、時刻 0-1799）はここで弾く。
- **services** — ユースケース。**権限判定はここに集約する**（`season_member.role` の確認）。routers や repositories に散らさない。
- **repositories** — SQL を書いてよい唯一の層。他の層に SQL 文字列を置かない。
- **db.py** — 接続管理。Lambda のコンテナ再利用を前提にモジュールスコープで保持する。

Lambda は1関数にまとめる。HTTP API の `$default` ルートから Mangum 経由で FastAPI に流す。エンドポイントごとに関数を分けない（この規模ではコールドスタート面が増えるだけ）。

## フロントの層と責務

- **features/** に置くのは**副作用のない純関数**。React に依存させない。テストの主対象。
  - `sort/` — 一覧のソート。週跨ぎ比較を含む。
  - `sync/` — ポーリング結果とローカル状態のマージ。フォーカス保護の判定。
  - `weekday/` — 曜日と時刻の整形。
- **components/board/**, **detail/** は表示と操作のみ。判断ロジックは features に置く。
- **components/ui/** は shadcn/ui の生成物。手で直さず、必要ならラッパを作る。
- ソートは API の ORDER BY ではなくクライアント側で行う。ポーリング結果と同じ関数で並べ替えたほうが同期時の整合が取りやすいため（30件規模なので性能上の問題はない）。

---

## 環境差の吸収

### 認証

本番は API Gateway の JWT Authorizer が検証済み claims を `requestContext` に入れる。ローカルには API Gateway がないため、`auth.py` で吸収する。

- Lambda 実行時 → `requestContext.authorizer.jwt.claims.sub` を読むだけ。検証コードは持たない。
- ローカル実行時 → `Authorization` ヘッダの JWT を検証なしでデコードして `sub` を取る。

後者は `APP_ENV=local` のときだけ有効にし、それ以外の値のときは**起動時に例外を投げて落とす**。認証を素通しするコードパスなので、環境変数の設定ミスで本番に載る事故を構造的に塞ぐ。

Auth0 のローカルエミュレータは存在しないため、ローカルでも dev テナントの本物を使う。

### DB 接続

本番は Supavisor の Transaction mode（6543）経由。prepared statement を無効化する必要がある。ローカルは Postgres 直結なので prepared statement が有効でも動いてしまい、**ローカルで通って本番で落ちる**。これを避けるため、無効化設定（`statement_cache_size=0` 相当）はローカルでも同じく適用する。**環境で分岐させない。**

Session mode（5432）は Lambda から使わない。接続枯渇を起こす。

### ローカルスタックの方針

- **Supabase CLI のローカルスタックは使わない。** 利用するのは Postgres だけで、Auth/Realtime/Storage/Studio まで含む十数コンテナを起動する理由がない。素の `postgres:17` 1コンテナで足りる。
- **SAM local は使わない。** 呼び出しごとに Docker コンテナが起動して反復が遅い。SAM はデプロイ専用。API Gateway 固有の挙動は staging で確認する。
- **開発はすべてローカルで完結させる。** フロントだけ起動して DB/API を staging に向ける運用はしない。環境が混ざると何を見ているか判別できなくなり、staging のスキーマを壊すと他の作業も止まる。

---

## 型の同期

`packages/api-types` は FastAPI の `/openapi.json` から `openapi-typescript` で生成する。手書きしない。生成物はコミットし、CI で再生成して差分が出たら fail させる。これで型ズレを構造的に防ぐ。

---

## マイグレーション

- Alembic は使わず、`db/migrations/` に連番の素のSQLを置く。Lambda に同梱すると本番への適用経路が曖昧になるため、アプリから独立させる。
- 適用は明示的な操作に限る。CI/CD で自動実行しない。スキーマ変更はロールバックが難しく、配信中に壊れると復旧できない。
- `season.updated_at` は配下の anime やタグ紐付けの変更でも更新する必要がある。アプリ側の書き忘れを構造的に防ぐため **DBトリガー**で実装する。
- `seed.sql` には検証用の異常系を意図的に含める（週跨ぎデータ、到達不能な画像URL）。

---

## ブランチと環境

| ブランチ | 環境 | フロント | API | DB |
|---|---|---|---|---|
| `develop` | staging | Vercel ブランチドメイン | AWS staging スタック | Supabase staging プロジェクト |
| `main` | production | Vercel 本番ドメイン | AWS prod スタック | Supabase prod プロジェクト |

- Vercel は Production Branch を `main` に設定し、Root Directory を `apps/web` にする。
- API は GitHub Actions が `apps/api/**` の変更を検知して `sam build && sam deploy`。AWS 認証情報はリポジトリに置かず、**GitHub OIDC で AssumeRole** する。
- ワークフローは `paths:` フィルタで分ける（`web-ci` / `api-ci` / `api-deploy` / `db-migrate`）。monorepo でも無関係な CI を回さないため。

Supabase の Free プランはアクティブなプロジェクト数に上限があり、staging と prod で枠を使い切る可能性がある。また一定期間アクセスがないとプロジェクトが一時停止するため、シーズンの合間は staging が止まっていることがある。

---

## 実装上の事故りやすい点

詳細は [仕様.md](./仕様.md) にある。ここでは実装時に踏みやすい箇所だけ挙げる。

- `stream_weekday`（配信曜日）と `air_weekday`（放送曜日）を、変数名・カラム名・UIラベルのすべてで区別する。日本語で「曜日」とだけ書かない。
- 週跨ぎのソート比較を絶対曜日で行わない。仕様の式どおりに比較する。ここは必ずユニットテストで固定してから実装する。
- 詳細モーダルの自動保存とポーリングは競合する。**フォーカス中のフィールドはポーリング結果で上書きしない。** この保護がないと配信中に入力が消える。

---

## 開発の進め方

- 新機能・バグ修正はテストから書く（RED → GREEN → REFACTOR）。特に `features/` の純関数と `services/` の権限判定。
- コミットは Conventional Commits（`feat:` / `fix:` / `refactor:` / `docs:` / `test:` / `chore:`）。
- 1ファイルは 200〜400行を目安、800行を上限とする。
- 秘密情報はコミットしない。`.env.example` にはキー名だけを書き、値を入れない。
