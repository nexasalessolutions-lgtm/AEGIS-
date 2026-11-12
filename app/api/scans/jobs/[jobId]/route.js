export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const API = process.env.AEGIS_API_URL || "https://aegis-api-v6-production.up.railway.app";

export async function GET(_request, context) {
  const token = process.env.AEGIS_SCAN_TOKEN;
  if (!token) {
    return Response.json({ detail: "Secure scan gateway is not configured." }, { status: 503 });
  }
  try {
    const { jobId } = await context.params;
    if (!jobId || !/^[0-9a-f-]{36}$/i.test(jobId)) {
      return Response.json({ detail: "Invalid scan job ID." }, { status: 400 });
    }
    const upstream = await fetch(API + "/api/scans/jobs/" + encodeURIComponent(jobId), {
      headers: { Authorization: "Bearer " + token },
      cache: "no-store",
      signal: AbortSignal.timeout(10_000),
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
  } catch {
    return Response.json({ detail: "Could not read the scan job status." }, { status: 502 });
  }
}
