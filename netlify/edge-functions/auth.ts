// 全ページに Basic 認証をかける（テスト公開用）。
// ID とパスワードは Netlify の環境変数 SITE_USER / SITE_PASS に置く（リポジトリには書かない）。
import type { Config, Context } from "@netlify/edge-functions";

const unauthorized = () =>
  new Response(
    "このページは関係者限定のテストサイトです。ID とパスワードを入力してください。",
    {
      status: 401,
      headers: {
        "WWW-Authenticate": 'Basic realm="Shibagaki test site", charset="UTF-8"',
        "Content-Type": "text/plain; charset=utf-8",
        "Cache-Control": "no-store",
      },
    },
  );

// 長さが違っても同じ時間で比較する（タイミング攻撃対策）
const safeEqual = (a: string, b: string) => {
  const enc = new TextEncoder();
  const x = enc.encode(a), y = enc.encode(b);
  let diff = x.length ^ y.length;
  for (let i = 0; i < Math.max(x.length, y.length); i++) diff |= (x[i] ?? 0) ^ (y[i] ?? 0);
  return diff === 0;
};

export default async (request: Request, context: Context) => {
  const user = Netlify.env.get("SITE_USER") ?? "";
  const pass = Netlify.env.get("SITE_PASS") ?? "";
  if (!user || !pass) {
    return new Response("認証情報が未設定です（SITE_USER / SITE_PASS）。", { status: 503 });
  }
  const header = request.headers.get("authorization") ?? "";
  if (!header.startsWith("Basic ")) return unauthorized();
  let decoded = "";
  try { decoded = atob(header.slice(6)); } catch { return unauthorized(); }
  const sep = decoded.indexOf(":");
  if (sep < 0) return unauthorized();
  const ok = safeEqual(decoded.slice(0, sep), user) && safeEqual(decoded.slice(sep + 1), pass);
  if (!ok) return unauthorized();
  const response = await context.next();
  response.headers.set("Cache-Control", "private, no-store");
  return response;
};

export const config: Config = { path: "/*" };
