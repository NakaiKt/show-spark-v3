import { auth0, HOME_PATH, LOGIN_PATH } from "@/lib/auth0";
import { NextResponse, type NextRequest } from "next/server";

/** ログイン必須の領域 */
const PROTECTED_PREFIX = "/apps";
/** ログイン領域 */
const AUTH_UI_PREFIX = "/auth";
/** SDK がマウントするルート。判定から必ず除外する */
const SDK_AUTH_PREFIX = "/api/auth";

const isUnder = (pathname: string, prefix: string) =>
  pathname === prefix || pathname.startsWith(`${prefix}/`);

/**
 * auth0.middleware() が付けた Set-Cookie を引き継いでリダイレクトする。
 * 素の NextResponse.redirect を返すとセッションのローリング更新が捨てられる。
 */
function redirectKeepingCookies(to: URL, from: NextResponse): NextResponse {
  const res = NextResponse.redirect(to);
  for (const cookie of from.cookies.getAll()) {
    res.cookies.set(cookie);
  }
  return res;
}

export async function proxy(request: NextRequest) {
  const authResponse = await auth0.middleware(request);
  const { pathname, search } = request.nextUrl;

  // SDK 自身のルート。ここに触れると認証フローが成立しない
  if (isUnder(pathname, SDK_AUTH_PREFIX)) {
    return authResponse;
  }

  const isProtected = isUnder(pathname, PROTECTED_PREFIX);
  const isAuthUi = isUnder(pathname, AUTH_UI_PREFIX);

  // 公開ページはセッションを引かずに素通しする
  if (!isProtected && !isAuthUi) {
    return authResponse;
  }

  const session = await auth0.getSession(request);

  if (isProtected && !session) {
    const to = new URL(LOGIN_PATH, request.nextUrl.origin);
    to.searchParams.set("returnTo", `${pathname}${search}`);
    return redirectKeepingCookies(to, authResponse);
  }

  if (isAuthUi && session) {
    return redirectKeepingCookies(
      new URL(HOME_PATH, request.nextUrl.origin),
      authResponse,
    );
  }

  return authResponse;
}

export const config = {
  matcher: [
    "/((?!_next/static|_next/image|favicon.ico|sitemap.xml|robots.txt).*)",
  ],
};
