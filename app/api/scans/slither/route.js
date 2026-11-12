export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const API = process.env.AEGIS_API_URL || "https://aegis-api-v5-production.up.railway.app";
const MAX_BYTES = 4 * 1024 * 1024;

export async function POST(request) {
  const token = process.env.AEGIS_SCAN_TOKEN;
  if (!token) {
    return Response.json({ detail: "Secure scan gateway is not configured." }, { status: 503 });
  }
  try {
    const incoming = await request.formData();
    const file = incoming.get("file");
    if (!(file instanceof File)) {
      return Response.json({ detail: "A Solidity source ZIP is required." }, { status: 400 });
    }
    if (!file.name.toLowerCase().endsWith(".zip")) {
      return Response.json({ detail: "Upload a ZIP archive." }, { status: 400 });
    }
    if (file.size > MAX_BYTES) {
      return Response.json({ detail: "ZIP exceeds the 4 MB secure upload limit." }, { status: 413 });
    }
    const outgoing = new FormData();
    outgoing.set("file", file, file.name);
    const upstream = await fetch(API + "/api/scans/slither", {
      method: "POST",
      headers: { Authorization: "Bearer " + token, "X-Aegis-Client-IP": request.headers.get("x-forwarded-for") || request.headers.get("x-real-ip") || "unknown" },
      body: outgoing,
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
