import { buildLogoutReturnTo, SDK_LOGOUT_PATH } from "@/lib/auth0";
import { Button } from "@/components/ui/button";

/**
 * ログアウトはアプリ側 cookie と Auth0 側 SSO セッションの両方を消す副作用であり、
 * リンク(GET)にするとプリフェッチやクローラで暴発しうる。
 * よってフォーム送信で行い、ボタンは native <button> のままにする。
 *
 * Base UI の Button は既定で type="button" を当てるため、
 * 送信させるには type="submit" を明示的に渡して上書きする必要がある。
 */
const LogoutButton = () => (
  <form action={SDK_LOGOUT_PATH} method="get">
    <input type="hidden" name="returnTo" value={buildLogoutReturnTo()} />
    <Button type="submit" variant="outline">
      ログアウト
    </Button>
  </form>
);

export default LogoutButton;
