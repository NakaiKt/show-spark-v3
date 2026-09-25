import { LOGIN_PATH } from "@/lib/auth0";

const MESSAGES: Record<string, string> = {
  // Post-Login Action の api.access.deny('registration_closed')
  registration_closed:
    "現在このアカウントは登録を受け付けていません。管理者に連絡してください。",
};

type Props = { searchParams: Promise<{ reason?: string }> };

export default async function AuthErrorPage({ searchParams }: Props) {
  const { reason } = await searchParams;

  return (
    <main>
      <h1>ログインできませんでした</h1>
      <p>
        {MESSAGES[reason ?? ""] ?? "時間をおいて、もう一度お試しください。"}
      </p>
      <a href={LOGIN_PATH}>ログイン画面に戻る</a>
    </main>
  );
}
