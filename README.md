# show-spark-v3

アニメシーズン視聴管理ツール。

- 要件 → [仕様書](./docs/v0.1/仕様書.md)
- 構成・開発ルール → [AGENT.md](./AGENT.md)
- 構築の進め方 → [土台の構築](./docs/v0.1/土台の構築.md)

> **現在のステータス: DB のみ構築済み**
> ローカルの Postgres とマイグレーションが動作する。API とフロントは未実装。

---

## 前提

| ツール | バージョン | 用途 |
|---|---|---|
| Docker | — | ローカル Postgres の実行 |
| Node.js | 22+ | マイグレーションツール（dbmate）の実行 |

WSL2 で Docker Desktop を使う場合は、Docker Desktop の Settings → Resources → WSL Integration で対象ディストロを有効にする。有効になっていないと `docker` コマンドが見つからない。

## セットアップ

```bash
npm install
cp .env.example .env
npm run local:db
npm run db:migrate
```

`.env` は編集不要。ローカル用の値がそのまま入っている。

## 環境変数

`.env`（リポジトリ直下）に置く。dbmate が自動で読み込む。

| 変数 | 値 | 説明 |
|---|---|---|
| `DATABASE_URL` | `postgres://showspark:showspark@127.0.0.1:5432/showspark?sslmode=disable` | 接続先。`sslmode=disable` はローカルの Postgres が SSL 無しで動くため必要 |
| `DBMATE_NO_DUMP_SCHEMA` | `true` | スキーマダンプを無効化する。有効にするにはホストに `pg_dump` 18 系が必要 |

## コマンド

### コンテナの操作

| コマンド | 内容 |
|---|---|
| `npm run local:db` | Postgres コンテナを起動し、接続できるようになるまで待つ |
| `npm run local:db:stop` | コンテナを停止する。データは残る |
| `npm run local:db:destroy` | コンテナとボリュームを削除する。**データが消える** |

`local:db` はヘルスチェックが通るまでブロックする。プロンプトが戻った時点で接続可能。初回は Postgres イメージの取得で1〜2分かかる。

作業を終えるときは `local:db:stop` を使う。`local:db:destroy` はボリュームごと消すため、コンテナの設定を変えて初期化からやり直したいときに使う。

### マイグレーション

| コマンド | 内容 |
|---|---|
| `npm run db:migrate` | 未適用のマイグレーションをファイル名順に適用する |
| `npm run db:status` | 各マイグレーションの適用状況を一覧表示する |
| `npm run db:rollback` | 直前に適用したマイグレーションを1つ戻す |
| `npm run db:seed` | `db/seed.sql` を流し込む |
| `npm run db:reset` | DB を削除して作り直し、全マイグレーションとシードを適用する |

`db:migrate` は適用済みのものを飛ばすため、何度実行しても安全。適用済みかどうかは DB 内の `schema_migrations` テーブルで管理される。

`db:status` の出力は `[X]` が適用済み、`[ ]` が未適用。

`db:reset` はスキーマを壊したときの復旧手段。ローカルのデータは全て消える。

### 接続

| コマンド | 内容 |
|---|---|
| `npm run db:psql` | 対話的な SQL シェル（psql）を開く |

テーブルの中身を目で確認したいときに使う。psql はコンテナ内のものを使うため、ホストへのインストールは不要。

よく使う psql の入力:

| 入力 | 内容 |
|---|---|
| `\dt` | テーブル一覧 |
| `\d テーブル名` | テーブルの列・制約・トリガーの定義 |
| `\l` | データベース一覧 |
| `\q` | 終了 |

## マイグレーションを追加する

```bash
npx dbmate new add_season
```

`db/migrations/<タイムスタンプ>_add_season.sql` が生成される。中身を書く。

```sql
-- migrate:up
create table season (
  ...
);

-- migrate:down
drop table season;
```

`-- migrate:up` と `-- migrate:down` の行は必須。dbmate がこのコメントで適用用と巻き戻し用を区別するため、欠けるとエラーになる。

書けたら適用する。

```bash
npm run db:migrate
```

一度でも staging や prod に適用したマイグレーションは編集しない。変更が必要なら新しいマイグレーションを追加する。

## 動作確認

```bash
npm run db:status     # Applied: 1 / Pending: 0
npm run db:psql
```

```sql
\dt
\d app_user
\q
```

`app_user` と `schema_migrations` が存在すれば正常。

## つまずいたら

| 症状 | 対処 |
|---|---|
| `docker: command not found` | Docker Desktop の WSL Integration が無効。有効化後に WSL を再起動する |
| `connection refused` | コンテナが停止している。`npm run local:db` |
| `SSL is not enabled on the server` | `.env` の `DATABASE_URL` に `?sslmode=disable` が付いていない |
| `password authentication failed` | `.env` と `docker-compose.yml` のユーザー名・パスワードが不一致 |
| `port is already allocated` | 5432 が使用中。`docker-compose.yml` の `ports` を `127.0.0.1:55432:5432` に変え、`.env` のポートも合わせる |
| `file must contain '-- migrate:up' comment` | マイグレーションにマーカー行が無い |
| `pg_dump: command not found` | `.env` に `DBMATE_NO_DUMP_SCHEMA=true` が無い |
| コンテナが `unhealthy` | `docker compose logs db` でエラーを確認。ボリュームが壊れていれば `npm run local:db:destroy` して再作成 |
