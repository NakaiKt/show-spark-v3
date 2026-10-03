# Web

show-spark のフロントエンド（Next.js + `@auth0/nextjs-auth0` v4）。

- プロジェクト全体の起動 → [README.md](../../README.md)
- 構成・開発ルール → [AGENT.md](../../AGENT.md)

コマンドはすべて `apps/web` で実行する。

## 初回セットアップ

```bash
npm install
mkdir -p env
touch env/.env.local
```

`env/.env.local` に下記の環境変数を書く。

## 環境変数

`apps/web/env/.env.local` に書く。`npm run dev` が起動のたびに `apps/web/.env.local` へコピーするため、`apps/web/.env.local` を直接編集しても上書きされて消える。コミットしない。

| 変数                  | 値                                                                  |
| --------------------- | ------------------------------------------------------------------- |
| `APP_BASE_URL`        | `http://localhost:3000`                                             |
| `AUTH0_DOMAIN`        | Auth0 dev テナントのドメイン（例: `dev-xxxx.us.auth0.com`）          |
| `AUTH0_CLIENT_ID`     | Auth0 の Application の Client ID                                   |
| `AUTH0_CLIENT_SECRET` | Auth0 の Application の Client Secret                               |
| `AUTH0_SECRET`        | セッション cookie の暗号鍵。`openssl rand -hex 32` の出力           |
| `AUTH0_AUDIENCE`      | Auth0 の APIs に登録した API の Identifier。API を呼ぶ処理で必要になる |

## Auth0 の Application 設定

Auth0 の Application → Settings に登録する。完全一致で照合されるため、末尾のスラッシュも含めて揃える。

| 項目                  | 値                                        |
| --------------------- | ----------------------------------------- |
| Allowed Callback URLs | `http://localhost:3000/api/auth/callback` |
| Allowed Logout URLs   | `http://localhost:3000/auth/login`        |
| Allowed Web Origins   | `http://localhost:3000`                   |

SDK のルートは `src/lib/auth0.ts` の `routes` で `/api/auth/*` に設定している。パスを変えたら上の表も合わせる。

## 起動

```bash
npm run dev
```

http://localhost:3000 で待ち受ける。コード変更で自動リロード。

ログインの動作確認には DB と API も必要。まとめて起動する方法は [README.md](../../README.md) の「フロント＋DB＋API」を参照。

## コマンド

| コマンド         | 内容                                           |
| ---------------- | ---------------------------------------------- |
| `npm run dev`    | `env/.env.local` をコピーして開発サーバーを起動 |
| `npm run build`  | 本番ビルド                                     |
| `npm run start`  | 本番ビルドを起動                               |
| `npm run lint`   | Biome でリントとフォーマットを検査する         |
| `npm run format` | Biome でフォーマットを適用する                 |

## つまずいたら

| 症状                                    | 対処                                                                      |
| --------------------------------------- | ------------------------------------------------------------------------- |
| `.env.local` を編集したのに反映されない | `env/.env.local` を編集して `npm run dev` を再起動する                    |
| Auth0 で `Callback URL mismatch`        | Allowed Callback URLs を `http://localhost:3000/api/auth/callback` にする |
| ログアウト後に Auth0 のエラー画面が出る | Allowed Logout URLs に `http://localhost:3000/auth/login` を登録する      |
| ログイン後 `/auth/error?reason=registration_closed` に飛ぶ | Auth0 の Post-Login Action で拒否されている。Action の `SIGNUP_ENABLED` を確認する |
