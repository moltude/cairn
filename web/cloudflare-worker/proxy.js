/**
 * Reverse-proxies quietmarch.to/cairn -> the Vercel-hosted Cairn web app.
 *
 * Not wired to Cloudflare's git-integration auto-deploy on purpose — deploys
 * are manual (paste into the dashboard's Quick Edit, or `wrangler deploy`).
 * See docs/VERCEL_DEPLOY_PLAN_2026-08-30.md §4 for why this exists and how
 * it's wired up.
 *
 * Bind this worker to two exact Routes on the quietmarch.to zone:
 *   - quietmarch.to/cairn
 *   - quietmarch.to/cairn/*
 * (Not the single broad pattern quietmarch.to/cairn* — that also matches
 * /cairnsomething, which the prefix-stripping below would mangle.)
 */
export default {
  async fetch(request, env, ctx) {
    const TARGET_ORIGIN = "https://cairn-web.vercel.app"; // <-- replace with your actual Vercel production alias

    const url = new URL(request.url);

    // Bare /cairn (no trailing slash) -> /cairn/, so the app's relative asset
    // paths (./dist/..., styles.css) resolve against the right directory.
    if (url.pathname === "/cairn") {
      url.pathname = "/cairn/";
      return Response.redirect(url.toString(), 308);
    }

    // Strip the /cairn prefix and proxy the rest to Vercel. Paths that don't
    // start with /cairn (e.g. hitting the workers.dev preview at its own
    // root) pass through unchanged instead of being mangled.
    const upstreamPath = url.pathname.startsWith("/cairn")
      ? url.pathname.slice("/cairn".length) || "/"
      : url.pathname;
    const upstreamUrl = TARGET_ORIGIN + upstreamPath + url.search;

    const upstreamHeaders = new Headers(request.headers);
    upstreamHeaders.delete("host");

    const upstreamResponse = await fetch(upstreamUrl, {
      method: request.method,
      headers: upstreamHeaders,
      body: ["GET", "HEAD"].includes(request.method) ? undefined : request.body,
      redirect: "manual", // so we can rewrite Location ourselves, not silently follow it
    });

    const responseHeaders = new Headers(upstreamResponse.headers);

    // Vercel's cleanUrls emits redirects like `Location: /index` — rewrite
    // those back under /cairn or the browser gets bounced into the blog root.
    if (upstreamResponse.status >= 300 && upstreamResponse.status < 400) {
      const location = responseHeaders.get("location");
      if (location) {
        const target = new URL(location, TARGET_ORIGIN);
        if (target.origin === TARGET_ORIGIN) {
          responseHeaders.set("location", "/cairn" + target.pathname + target.search);
        }
      }
    }

    return new Response(upstreamResponse.body, {
      status: upstreamResponse.status,
      statusText: upstreamResponse.statusText,
      headers: responseHeaders,
    });
  },
};
