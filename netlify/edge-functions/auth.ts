// テスト公開中の関係者限定アクセス制御（全ページ）。
// ID とパスワードは Netlify の環境変数 SITE_USER / SITE_PASS に置く（リポジトリには書かない）。
// 入り方は2通り：
//   1) 日本語のログイン画面（Cookie で 30 日間保持。ブラウザの認証ダイアログは使わない）
//   2) Basic 認証ヘッダー（curl -u などの確認用。従来どおり）
import type { Config, Context } from "@netlify/edge-functions";

const COOKIE = "sg_test_session";
const COOKIE_DAYS = 30;

// 長さが違っても同じ時間で比較する（タイミング攻撃対策）
const safeEqual = (a: string, b: string) => {
  const enc = new TextEncoder();
  const x = enc.encode(a), y = enc.encode(b);
  let diff = x.length ^ y.length;
  for (let i = 0; i < Math.max(x.length, y.length); i++) diff |= (x[i] ?? 0) ^ (y[i] ?? 0);
  return diff === 0;
};

// Cookie の値＝HMAC-SHA256（鍵：パスワード、本文：固定文字列＋ID）。パスワードを変えると全員の Cookie が無効になる
const sessionToken = async (user: string, pass: string) => {
  const enc = new TextEncoder();
  const key = await crypto.subtle.importKey("raw", enc.encode(pass), { name: "HMAC", hash: "SHA-256" }, false, ["sign"]);
  const sig = await crypto.subtle.sign("HMAC", key, enc.encode("shibagaki-test-site:v1:" + user));
  return Array.from(new Uint8Array(sig)).map((b) => b.toString(16).padStart(2, "0")).join("");
};

const getCookie = (request: Request, name: string) => {
  const raw = request.headers.get("cookie") ?? "";
  for (const part of raw.split(";")) {
    const [k, ...v] = part.trim().split("=");
    if (k === name) return v.join("=");
  }
  return "";
};

const escapeHtml = (s: string) =>
  s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");

const safeNext = (next: string) => (next.startsWith("/") && !next.startsWith("//") ? next : "/");

const loginPage = (next: string, error = "") =>
  new Response(
    `<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<meta name="robots" content="noindex, nofollow">
<title>関係者限定 | 柴垣医院 ホームページ（テスト公開）</title>
<style>
  body { margin: 0; font-family: -apple-system, "Hiragino Sans", "Noto Sans JP", sans-serif; background: #f4f6f8; color: #2c4256; }
  main { max-width: 26rem; margin: 10vh auto 0; padding: 0 1.5rem; }
  .card { background: #fff; border: 1px solid #dde5ec; border-radius: 8px; padding: 1.5rem; }
  h1 { font-size: 1.15rem; font-weight: 600; margin: 0 0 .5rem; }
  p { font-size: .95rem; line-height: 1.7; margin: 0 0 1rem; }
  label { display: block; font-size: .9rem; margin: .8rem 0 .3rem; }
  input { width: 100%; box-sizing: border-box; font-size: 1.05rem; padding: .6rem .7rem; border: 1px solid #bfcad6; border-radius: 6px; }
  button { width: 100%; margin-top: 1.2rem; padding: .75rem; font-size: 1rem; border: 0; border-radius: 6px; background: #526c6e; color: #fff; cursor: pointer; }
  .error { background: #fdecea; color: #a8322a; border-radius: 6px; padding: .6rem .8rem; font-size: .9rem; margin-bottom: .5rem; }
</style>
</head>
<body>
<main>
  <div class="card">
    <h1>柴垣医院 ホームページ（テスト公開）</h1>
    <p>このサイトは関係者限定です。お知らせした ID とパスワードを入力してください。</p>
    ${error ? `<div class="error">${escapeHtml(error)}</div>` : ""}
    <form method="post" action="/__login" autocomplete="on">
      <input type="hidden" name="next" value="${escapeHtml(next)}">
      <label for="user">ID</label>
      <input id="user" name="user" type="text" autocomplete="username" autocapitalize="none" autocorrect="off" spellcheck="false" required>
      <label for="pass">パスワード</label>
      <input id="pass" name="pass" type="password" autocomplete="current-password" required>
      <button type="submit">入る</button>
    </form>
  </div>
</main>
</body>
</html>`,
    {
      status: 401,
      headers: { "Content-Type": "text/html; charset=utf-8", "Cache-Control": "no-store" },
    },
  );

export default async (request: Request, context: Context) => {
  const user = Netlify.env.get("SITE_USER") ?? "";
  const pass = Netlify.env.get("SITE_PASS") ?? "";
  if (!user || !pass) {
    return new Response("認証情報が未設定です（SITE_USER / SITE_PASS）。", { status: 503 });
  }
  const url = new URL(request.url);
  const token = await sessionToken(user, pass);

  // ログイン画面からの送信
  if (url.pathname === "/__login" && request.method === "POST") {
    const form = await request.formData();
    const u = String(form.get("user") ?? "").trim();
    const p = String(form.get("pass") ?? "");
    const next = safeNext(String(form.get("next") ?? "/"));
    if (!(safeEqual(u, user) && safeEqual(p, pass))) {
      return loginPage(next, "ID またはパスワードが違います。");
    }
    return new Response(null, {
      status: 303,
      headers: {
        Location: next,
        "Set-Cookie": `${COOKIE}=${token}; Path=/; Max-Age=${COOKIE_DAYS * 86400}; HttpOnly; Secure; SameSite=Lax`,
        "Cache-Control": "no-store",
      },
    });
  }

  // 1) Cookie
  let ok = safeEqual(getCookie(request, COOKIE), token);

  // 2) Basic 認証ヘッダー（curl 等の確認用）
  if (!ok) {
    const header = request.headers.get("authorization") ?? "";
    if (header.startsWith("Basic ")) {
      let decoded = "";
      try { decoded = atob(header.slice(6)); } catch { decoded = ""; }
      const sep = decoded.indexOf(":");
      if (sep >= 0) ok = safeEqual(decoded.slice(0, sep), user) && safeEqual(decoded.slice(sep + 1), pass);
    }
  }

  if (!ok) return loginPage(url.pathname + url.search);

  const response = await context.next();
  response.headers.set("Cache-Control", "private, no-store");
  return response;
};

export const config: Config = { path: "/*" };
