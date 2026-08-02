# AGENT.md

このリポジトリの構成と開発ルール。要件は [仕様書](./docs/v0.1/仕様書.md)、コマンドは [README.md](./README.md) を参照。ここには両者に書かないこと（構成の意図とルール）だけを書く。

---

## リポジトリ構成

単一リポジトリに web と api を同居させる。npm workspaces / Turborepo は導入しない（TS と Python で言語が異なり、共通ビルドグラフの利点がないため）。ルートの `package.json` はタスクランナーで、アプリの依存は持たない。開発ツール（dbmate）だけを `devDependencies` に置く。

```
show-spark-v3/
├── package.json                 # スクリプトと開発ツールのみ
├── docker-compose.yml           # ローカル用 Postgres 1コンテナ
├── .env.example                 # DATABASE_URL などの雛形
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
│   ├── migrations/              # dbmate のマイグレーション（タイムスタンプ版）
│   └── seed.sql
├── docs/v0.1/                   # 仕様書・設計文書
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
- ソートはクライアント側で行う。ポーリング結果と同じ関数で並べ替えたほうが同期時の整合が取りやすい（30件規模なので性能上の問題はない）。

---

## データベースの規約

### 主キーと識別子

- **外部サービスが発行する識別子を主キーにしない。** 主キーは内部採番の `uuid`（`gen_random_uuid()`）とする。
- Auth0 の `sub` は `app_user.sub` に unique 列として持つ。アカウントリンクや認証基盤の変更で `sub` が変わっても、1行1列の更新で復旧できる。
- 他テーブルからユーザーを参照するときは `app_user.id` を指す。

### 時刻

- 発生時刻を記録する列は `timestamptz`（= `timestamp with time zone`）。UTC の一瞬として保存される。
- ドメイン固有の時刻表現は整数で持つ。`air_time_min` は 0〜1799 の分で、24:00〜29:59 を許容する。時刻型では表現できない。

### updated_at

`set_updated_at()` トリガー関数を全テーブルで共有する。`before update` で接続すれば、アプリが書き忘れても更新される。

```sql
create trigger <テーブル名>_set_updated_at
  before update on <テーブル名>
  for each row
  execute function set_updated_at();
```

`season.updated_at` は配下の `anime` やタグ紐付けの変更でも更新する必要がある。これは自分の行しか触らない `set_updated_at()` では実現できないため、親を更新する別のトリガー関数を用意する。

### 制約

- 起きてはいけない重複には unique 制約を付ける。「たぶん起きない」ではなく「起きたら不具合」なら、DB で拒否させて表面化させる。
- 外部から提供される任意項目（OIDC の `name` / `picture` など）は nullable にする。欠落時に `not null` 違反でログインが落ちるのを避ける。表示側でフォールバックを用意する。

---

## マイグレーション

dbmate で管理する。マイグレーションの中身は素の SQL。

- ファイルは `npx dbmate new <名前>` で生成する。ファイル名はタイムスタンプ版で、適用順は名前順。
- `-- migrate:up` と `-- migrate:down` のマーカー行が必須。
- 適用済みは DB 内の `schema_migrations` テーブルで管理される。同じものが二度当たらない。
- **一度でも staging や prod に適用したマイグレーションは編集しない。** 変更が必要なら新しいマイグレーションを追加する。
- 適用は明示的な操作に限る。CI/CD で自動実行しない。スキーマ変更はロールバックが難しく、配信中に壊れると復旧できない。
- `seed.sql` には検証用の異常系を意図的に含める（週跨ぎデータ、到達不能な画像URL）。

スキーマダンプ（`dbmate dump`）は `DBMATE_NO_DUMP_SCHEMA=true` で無効化している。この機能はホスト側の `pg_dump` を呼ぶため、サーバと同じ 18 系のクライアントが必要になる。

---

## 環境差の吸収

### 認証

本番は API Gateway の JWT Authorizer が検証済み claims を `requestContext` に入れる。ローカルには API Gateway がないため、`auth.py` で吸収する。

- Lambda 実行時 → `requestContext.authorizer.jwt.claims.sub` を読むだけ。検証コードは持たない。
- ローカル実行時 → `Authorization` ヘッダの JWT を検証なしでデコードして `sub` を取る。

後者は `APP_ENV=local` のときだけ有効にし、それ以外の値のときは**起動時に例外を投げて落とす**。認証を素通しするコードパスなので、環境変数の設定ミスで本番に載る事故を構造的に塞ぐ。

Auth0 のローカルエミュレータは存在しないため、ローカルでも dev テナントの本物を使う。

### DB 接続

本番は Neon の Pooler（ホスト名に `-pooler` が付くエンドポイント）経由。中身は PgBouncer の transaction mode なので prepared statement を無効化する必要がある。ローカルは Postgres 直結なので prepared statement が有効でも動いてしまい、**ローカルで通って本番で落ちる**。これを避けるため、無効化設定（`statement_cache_size=0` 相当）はローカルでも同じく適用する。**環境で分岐させない。**

Neon の直結エンドポイントは Lambda から使わない。接続枯渇を起こす。マイグレーション（DDL）は Pooler ではなく直結から流す。

SSL の要否は環境で異なる。Neon は `sslmode=require`、ローカルの Postgres は非SSLのため `sslmode=disable`。接続文字列で吸収する。

### ローカルスタックの方針

- **ローカルDBは `postgres:18` コンテナ1つで動かす。** バージョンは Neon 側に合わせる。ずれると、ローカルで通ったSQLが本番で落ちる。
- **SAM local は使わない。** 呼び出しごとに Docker コンテナが起動して反復が遅い。SAM はデプロイ専用。API Gateway 固有の挙動は staging で確認する。
- **開発はすべてローカルで完結させる。** フロントだけ起動して DB/API を staging に向ける運用はしない。環境が混ざると何を見ているか判別できなくなり、staging のスキーマを壊すと他の作業も止まる。

---

## 型の同期

`packages/api-types` は FastAPI の `/openapi.json` から `openapi-typescript` で生成する。手書きしない。生成物はコミットし、CI で再生成して差分が出たら fail させる。これで型ズレを構造的に防ぐ。

---

## ブランチと環境

| ブランチ | 環境 | フロント | API | DB |
|---|---|---|---|---|
| `develop` | staging | Vercel ブランチドメイン | AWS staging スタック | Neon staging プロジェクト |
| `main` | production | Vercel 本番ドメイン | AWS prod スタック | Neon prod プロジェクト |

- Vercel は Production Branch を `main` に設定し、Root Directory を `apps/web` にする。
- API は GitHub Actions が `apps/api/**` の変更を検知して `sam build && sam deploy`。AWS 認証情報はリポジトリに置かず、**GitHub OIDC で AssumeRole** する。
- ワークフローは `paths:` フィルタで分ける（`web-ci` / `api-ci` / `api-deploy` / `db-migrate`）。無関係な CI を回さないため。

staging と prod は Neon の別プロジェクトとして作成し、接続文字列を共有しない。

Neon はアイドル時に自動サスペンドし、アクセスが来ると1秒未満で自動復帰する。シーズンの合間に触らない期間が続いても、手動の復帰操作は要らない。

---

## 実装上の事故りやすい点

詳細は [仕様書](./docs/v0.1/仕様書.md) にある。ここでは実装時に踏みやすい箇所だけ挙げる。

- `stream_weekday`（配信曜日）と `air_weekday`（放送曜日）を、変数名・カラム名・UIラベルのすべてで区別する。日本語で「曜日」とだけ書かない。
- 週跨ぎのソート比較を絶対曜日で行わない。仕様の式どおりに比較する。ここは必ずユニットテストで固定してから実装する。
- 詳細モーダルの自動保存とポーリングは競合する。**フォーカス中のフィールドはポーリング結果で上書きしない。** この保護がないと配信中に入力が消える。
- メールアドレスは小文字に正規化してから保存する。unique 制約は大文字小文字を区別するため、正規化しないと重複を取りこぼす。

---

## 開発の進め方

- 新機能・バグ修正はテストから書く（RED → GREEN → REFACTOR）。特に `features/` の純関数と `services/` の権限判定。
- コミットは Conventional Commits（`feat:` / `fix:` / `refactor:` / `docs:` / `test:` / `chore:`）。
- 1ファイルは 200〜400行を目安、800行を上限とする。
- 秘密情報はコミットしない。`.env.example` にはキー名とローカル専用の値だけを書く。
