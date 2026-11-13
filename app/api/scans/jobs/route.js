export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const API = process.env.AEGIS_INTERNAL_API_URL || "http://127.0.0.1:8000";

export async function GET(request) {
  const token = process.env.AEGIS_SCAN_TOKEN;
  if (!token) {
    return Response.json({ detail: "Secure scan gateway is not configured." }, { status: 503 });
  }
  try {
    const incoming = new URL(request.url);
    const limit = Math.min(200, Math.max(1, Number(incoming.searchParams.get("limit") || 50)));
    const upstream = await fetch(API + "/api/scans/jobs?limit=" + limit, {
      headers: { Authorization: "Bearer " + token },
      cache: "no-store",
      signal: AbortSignal.timeout(10_000),
    });
    return new Response(await upstream.arrayBuffer(), {
      status: upstream.status,
      headers: {
        "content-type": upstream.headers.get("content-type") || "application/json",
        "cache-control": "no-store",
        "x-content-type-options": "nosniff",
      },
    });
  } catch {
    return Response.json({ detail: "Could not retrieve scan history." }, { status: 502 });
  }
}
