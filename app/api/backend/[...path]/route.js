export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const API = process.env.AEGIS_INTERNAL_API_URL || "http://127.0.0.1:8000";

export async function GET(request, context) {
  const { path = [] } = await context.params;
  if (!Array.isArray(path) || path.length === 0 || path.some((part) => part === "." || part === ".." || part.includes("/"))) {
    return Response.json({ detail: "Invalid API path." }, { status: 400 });
  }

  const incoming = new URL(request.url);
  const target = new URL(
    "/" + path.map((part) => encodeURIComponent(part)).join("/") + incoming.search,
    API,
  );

  try {
    const upstream = await fetch(target, {
      method: "GET",
      headers: { accept: request.headers.get("accept") || "application/json" },
      cache: "no-store",
      signal: AbortSignal.timeout(path[0] === "api" && path[1] === "protocol" && (path[3] === "contracts" || path[3] === "snapshot") ? 120_000 : 30_000),
    });
    return new Response(upstream.body, {
      status: upstream.status,
      headers: {
        "content-type": upstream.headers.get("content-type") || "application/json",
        "cache-control": "no-store",
        "x-content-type-options": "nosniff",
      },
    });
  } catch {
    return Response.json(
      { detail: "Local AEGIS API is unavailable. Check the Codespace services terminal." },
      { status: 503 },
    );
  }
}
