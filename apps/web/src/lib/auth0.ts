import { AuthorizationError } from "@auth0/nextjs-auth0/errors";
import { Auth0Client } from "@auth0/nextjs-auth0/server";
import { NextResponse } from "next/server";

/** ログイン後の規定パス */
export const HOME_PATH = "/apps";
/** ログイン前の規定パス */
export const LOGIN_PATH = "/auth/login";

export const SDK_LOGIN_PATH = "/api/auth/login";
export const SDK_LOGOUT_PATH = "/api/auth/logout";

export const auth0 = new Auth0Client({
  routes: {
    login: SDK_LOGIN_PATH,
    logout: SDK_LOGOUT_PATH,
    callback: "/api/auth/callback",
    backChannelLogout: "/api/auth/backchannel-logout",
    profile: "/api/auth/profile",
    accessToken: "/api/auth/access-token",
  },

  authorizationParameters: {
    // audience を設定してアクセストークンをJWTにする
    audience: process.env.AUTH0_AUDIENCE,
    // Universal Login の IdP 選択を飛ばして Google へ直行する
    connection: "google-oauth2",
    // 既定値と同じだが、offline_access を落とすと再ログインを強いられるため明示する
    scope: "openid profile email offline_access",
  },

  async onCallback(error, ctx, _session) {
    const base = ctx.appBaseUrl ?? process.env.APP_BASE_URL!;

    if (error) {
      const url = new URL("/auth/error", base);
      // Action の deny は access_denied + description に理由が入る
      const reason =
        error instanceof AuthorizationError ? error.cause.message : error.code;
      url.searchParams.set("reason", reason ?? "unknown");
      return NextResponse.redirect(url);
    }

    return NextResponse.redirect(new URL(ctx.returnTo ?? HOME_PATH, base));
  },
});

/**
 * ログアウト後にログイン画面へ戻す絶対URL。
 * SDK が post_logout_redirect_uri にそのまま渡すため絶対URLである必要があり、
 * かつ Auth0 の Allowed Logout URLs に完全一致で登録されていなければならない。
 */
export function buildLogoutReturnTo(): string {
  const base = process.env.APP_BASE_URL;
  if (!base) {
    throw new Error("APP_BASE_URL が未設定です");
  }
  return new URL(LOGIN_PATH, base).toString();
}
