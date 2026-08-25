import { SDK_LOGIN_PATH, HOME_PATH } from "@/lib/auth0";

type Props = { searchParams: Promise<{ returnTo?: string }> };

export default async function LoginPage({ searchParams }: Props) {
  const { returnTo } = await searchParams;

  // returnTo は SDK 側で toSafeRedirect により検証されるため、
  // ここではそのまま渡してよい（オープンリダイレクトにならない）
  const href = `${SDK_LOGIN_PATH}?returnTo=${encodeURIComponent(returnTo ?? HOME_PATH)}`;

  return (
    <main>
      <h1>show-spark</h1>
      <p>Google アカウントでログインしてください。</p>
      <a href={href}>Google でログイン</a>
    </main>
  );
}
