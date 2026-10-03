# show-spark-v3

アニメシーズン視聴管理ツール。

- 要件 → [仕様書](./docs/v0.1/仕様書.md)
- 構成・開発ルール → [AGENT.md](./AGENT.md)
- 構築の進め方 → [土台の構築](./docs/v0.1/土台の構築.md)

> **現在のステータス: DB・API・フロントの骨組みまで構築済み**
> ローカルの Postgres、マイグレーション、`/health` と `/me` の2エンドポイント、フロントの Google ログイン・ログアウトが動作する。フロントから `/me` を呼ぶ処理は未実装。

---

## 前提

| ツール  | バージョン | 必要な対象 |
| ------- | ---------- | ---------- |
| Docker  | —          | DB         |
| Node.js | 22+        | DB、Web    |
| Python  | 3.14       | API        |

WSL2 で Docker Desktop を使う場合は、Settings → Resources → WSL Integration で対象ディストロを有効にする。

## 依存関係

| やること                     | 必要なもの        |
| ---------------------------- | ----------------- |
| マイグレーション、データ操作 | DB                |
| API のユニットテスト         | Python 環境       |
| API の統合テスト             | DB ＋ Python 環境 |
| API の起動                   | DB ＋ Python 環境 |
| Web の起動                   | Web の依存関係    |
| ログインの動作確認           | DB ＋ API ＋ Web  |

---

# DB

## 初回セットアップ

```bash
npm install
cp .env.example .env
```

`.env` は編集不要。

## 起動

```bash
npm run local:db
npm run db:migrate
```

## コマンド

| コマンド                   | 内容                                                    |
| -------------------------- | ------------------------------------------------------- |
| `npm run local:db`         | コンテナを起動し、接続可能になるまで待つ                |
| `npm run local:db:stop`    | 停止する。データは残る                                  |
| `npm run local:db:destroy` | コンテナとボリュームを削除する。**データが消える**      |
| `npm run db:migrate`       | 未適用のマイグレーションを適用する                      |
| `npm run db:status`        | 適用状況を一覧表示する（`[X]` 適用済み / `[ ]` 未適用） |
| `npm run db:rollback`      | 直前のマイグレーションを1つ戻す                         |
| `npm run db:seed`          | `db/seed.sql` を流し込む                                |
| `npm run db:reset`         | DB を作り直し、全マイグレーションとシードを適用する     |
| `npm run db:psql`          | psql を開く                                             |

`db:migrate` は何度実行しても安全。適用済みかどうかは `schema_migrations` テーブルで管理される。

## psql

| 入力            | 内容                     |
| --------------- | ------------------------ |
| `\dt`           | テーブル一覧             |
| `\d テーブル名` | 列・制約・トリガーの定義 |
| `\l`            | データベース一覧         |
| `\q`            | 終了                     |

## マイグレーションを追加する

```bash
npx dbmate new add_season
```

`db/migrations/<タイムスタンプ>_add_season.sql` に書く。

```sql
-- migrate:up
create table season (
  ...
);

-- migrate:down
drop table season;
```

`-- migrate:up` と `-- migrate:down` は必須。

```bash
npm run db:migrate
```

staging や prod に適用済みのマイグレーションは編集しない。変更が必要なら新しいマイグレーションを追加する。

## 環境変数

`.env`（リポジトリ直下）。dbmate が読み込む。コミットしない。

| 変数                    | 値                                                                        |
| ----------------------- | ------------------------------------------------------------------------- |
| `DATABASE_URL`          | `postgres://showspark:showspark@127.0.0.1:5432/showspark?sslmode=disable` |
| `DBMATE_NO_DUMP_SCHEMA` | `true`                                                                    |

## 動作確認

```bash
npm run db:status     # Applied: 1 / Pending: 0
npm run db:psql
```

```sql
\dt
```

`app_user` と `schema_migrations` があれば正常。

---

# API

## 初回セットアップ

```bash
python3.14 -m venv apps/api/venv
apps/api/venv/bin/pip install -r apps/api/requirements.txt
mkdir -p apps/api/env
cp apps/api/.env.example apps/api/env/.env.local
```

`.env.local` は編集不要。

## 起動

```bash
npm run local:api
```

http://127.0.0.1:8000 で待ち受ける。コード変更で自動リロード。API ドキュメントは http://127.0.0.1:8000/docs。

## テスト

| コマンド                       | 内容                 | DB   |
| ------------------------------ | -------------------- | ---- |
| `npm run test:api:unit`        | ユニットテストのみ   | 不要 |
| `npm run test:api:integration` | 統合テストのみ       | 必要 |
| `npm run test:api`             | 全テスト             | 必要 |
| `npm run test:api:cov`         | 全テストとカバレッジ | 必要 |

統合テストが作る行は `sub` が `google-oauth2|test-` で始まるものだけで、各テストの前後に削除される。

## 環境変数

`apps/api/env/.env.local`。`npm run local:api` が読み込む。雛形は `apps/api/.env.example`。コミットしない。

| 変数           | 値                                                                        |
| -------------- | ------------------------------------------------------------------------- |
| `APP_ENV`      | `local`                                                                   |
| `DATABASE_URL` | `postgres://showspark:showspark@127.0.0.1:5432/showspark?sslmode=disable` |

`APP_ENV=local` のときだけ、署名検証なしの認証経路が有効になる。

テスト実行時は `tests/conftest.py` が値を設定するため、このファイルは読まれない。

## 動作確認

```bash
curl http://127.0.0.1:8000/health
# {"status":"ok"}

curl -i http://127.0.0.1:8000/me
# HTTP/1.1 401 Unauthorized
```

`/me` 用のトークンを組み立てる。

```bash
TOKEN=$(apps/api/venv/bin/python - <<'EOF'
import base64, json

def part(d):
    return base64.urlsafe_b64encode(json.dumps(d).encode()).rstrip(b"=").decode()

print(f'{part({"alg": "none"})}.{part({"sub": "google-oauth2|me", "email": "me@example.com", "name": "Me"})}.')
EOF
)

curl -H "Authorization: Bearer $TOKEN" http://127.0.0.1:8000/me
```

```json
{
  "id": "...",
  "sub": "google-oauth2|me",
  "email": "me@example.com",
  "name": "Me",
  "picture": null,
  "created_at": "2026-01-01T00:00:00+00:00",
  "updated_at": "...",
  "last_login_at": "..."
}
```

初回は `app_user` に行が作られ、2回目以降は `last_login_at` が更新される。

---

# Frontend

セットアップ・環境変数・単体での起動は [apps/web/README.md](./apps/web/README.md) を参照。

---

# フロント＋DB＋API

DB・API・Web の初回セットアップを済ませてから使う。

| URL                        | 内容 |
| -------------------------- | ---- |
| http://localhost:3000      | Web  |
| http://127.0.0.1:8000      | API  |
| http://127.0.0.1:8000/docs | API ドキュメント |

## 起動（VS Code）

コマンドパレット → `Tasks: Run Task` → `local` を選ぶ。

DB を起動して接続可能になるまで待ち、API と Web をそれぞれ別のターミナルパネルで起動する。パネルごとにログを追え、片方だけ止めて再起動できる。

| タスク      | 内容                         |
| ----------- | ---------------------------- |
| `local`     | DB → API と Web を並列で起動 |
| `local:db`  | DB のみ起動                  |
| `local:api` | API のみ起動                 |
| `local:web` | Web のみ起動                 |

## 起動（1つのターミナル）

```bash
npm run local
```

DB を起動してから、API と Web を1つのターミナルで並列に起動する。各行の先頭に `[api]` / `[web]` が付く。Ctrl+C で API と Web が両方止まる。片方が異常終了したときも、もう片方が止まる。

DB コンテナは止まらない。止めるときは `npm run local:db:stop` を実行する。

## 起動（ターミナルを分ける）

ターミナルを3つ使い、それぞれで実行する。

```bash
npm run local:db
```

```bash
npm run local:api
```

```bash
npm run local:web
```

## コマンド

| コマンド            | 内容                                              |
| ------------------- | ------------------------------------------------- |
| `npm run local`     | DB を起動してから、API と Web を並列で起動する     |
| `npm run local:db`  | DB コンテナを起動し、接続可能になるまで待つ        |
| `npm run local:api` | API を http://127.0.0.1:8000 で起動する            |
| `npm run local:web` | Web を http://localhost:3000 で起動する            |

---

# つまずいたら

## DB

| 症状                                        | 対処                                                                                        |
| ------------------------------------------- | ------------------------------------------------------------------------------------------- |
| `docker: command not found`                 | Docker Desktop の WSL Integration を有効化し、WSL を再起動する                              |
| `connection refused`                        | `npm run local:db`                                                                          |
| `SSL is not enabled on the server`          | `.env` の `DATABASE_URL` に `?sslmode=disable` を付ける                                     |
| `password authentication failed`            | `.env` と `docker-compose.yml` のユーザー名・パスワードを一致させる                         |
| `port is already allocated`                 | `docker-compose.yml` の `ports` を `127.0.0.1:55432:5432` に変え、`.env` のポートも合わせる |
| `file must contain '-- migrate:up' comment` | マイグレーションにマーカー行を追加する                                                      |
| `pg_dump: command not found`                | `.env` に `DBMATE_NO_DUMP_SCHEMA=true` を追加する                                           |
| コンテナが `unhealthy`                      | `docker compose logs db` を確認。`npm run local:db:destroy` して再作成                      |

## API

| 症状                                                            | 対処                                                     |
| --------------------------------------------------------------- | -------------------------------------------------------- |
| `venv/bin/python: No such file or directory`                    | API の初回セットアップを実行する                         |
| テストが「DBに接続できません」で止まる                          | `npm run local:db`                                       |
| `relation "app_user" does not exist`                            | `npm run db:migrate`                                     |
| `/health` が 503 を返す                                         | `npm run local:db`                                       |
| `RuntimeError: 未検証の認証経路はAPP_ENV=localでしか使えません` | `apps/api/env/.env.local` の `APP_ENV` を `local` にする |
