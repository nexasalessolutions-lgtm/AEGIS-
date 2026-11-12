export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const API = process.env.AEGIS_API_URL || "https://aegis-api-v3-production.up.railway.app";

export async function POST(_request, context) {
  const token = process.env.AEGIS_SCAN_TOKEN;
  if (!token) {
    return Response.json({ detail: "Secure scan gateway is not configured." }, { status: 503 });
  }
  try {
    const { slug } = await context.params;
    if (!slug || !/^[a-zA-Z0-9._-]{1,120}$/.test(slug)) {
      return Response.json({ detail: "Invalid protocol slug." }, { status: 400 });
    }
    const upstream = await fetch(API + "/api/scans/protocol/" + encodeURIComponent(slug), {
      method: "POST",
      headers: { Authorization: "Bearer " + token },
      cache: "no-store",
      signal: AbortSignal.timeout(210_000),
    });
    const body = await upstream.arrayBuffer();
    return new Response(body, {
      status: upstream.status,
      headers: {
        "content-type": upstream.headers.get("content-type") || "application/json",
        "cache-control": "no-store",
        "x-content-type-options": "nosniff",
      },
    });
  } catch (error) {
    return Response.json(
      { detail: error?.name === "TimeoutError" ? "Static analysis timed out." : "Could not reach the analysis service." },
      { status: 502 },
    );
  }
}
