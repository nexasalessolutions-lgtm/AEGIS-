from __future__ import annotations

import asyncio
import os
import re
import time
from typing import Any

import httpx
from fastapi import FastAPI, File, Header, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="AEGIS Read-only Intelligence API", version="0.2.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ORIGINS", "*").split(","),
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["authorization", "content-type"],
)

LLAMA = "https://api.llama.fi"
SOURCIFY = "https://sourcify.dev/server"
CHAIN_IDS = {
    "ethereum": 1, "optimism": 10, "bsc": 56, "gnosis": 100,
    "polygon": 137, "arbitrum": 42161, "avalanche": 43114, "base": 8453,
}
RPCS = {
    "ethereum": ["https://ethereum-rpc.publicnode.com", "https://1rpc.io/eth"],
    "arbitrum": ["https://arbitrum-one-rpc.publicnode.com", "https://1rpc.io/arb"],
    "optimism": ["https://optimism-rpc.publicnode.com", "https://1rpc.io/op"],
    "base": ["https://base-rpc.publicnode.com", "https://1rpc.io/base"],
    "polygon": ["https://polygon-bor-rpc.publicnode.com", "https://1rpc.io/matic"],
    "bsc": ["https://bsc-rpc.publicnode.com", "https://1rpc.io/bnb"],
    "avalanche": ["https://avalanche-c-chain-rpc.publicnode.com"],
    "gnosis": ["https://gnosis-rpc.publicnode.com"],
}
EIP1967 = {
    "implementation": "0x360894a13ba1a3210667c828492db98dca3e2076cc3735a920a3ca505d382bbc",
    "admin": "0xb53127684a568b3173ae13b9f8a6016e243e63b6e8ee1178d6a717850b5d6103",
    "beacon": "0xa3f0ad74e5423aebfd80d3ef4346578335a9a72aeaee59ff6cb3582b35133d50",
}
CACHE: dict[str, tuple[float, Any]] = {}

async def get_json(url: str, *, params: dict[str, str] | None = None, cache_key: str | None = None, ttl: int = 0) -> Any:
    now = time.monotonic()
    if cache_key and cache_key in CACHE:
        expires, value = CACHE[cache_key]
        if expires > now:
            return value
    async with httpx.AsyncClient(timeout=20, headers={"User-Agent": "AEGIS-DeFi-Intelligence/0.2 (+https://github.com/nexasalessolutions-lgtm/AEGIS-)"}) as client:
        response = await client.get(url, params=params)
        response.raise_for_status()
        value = response.json()
    if cache_key and ttl:
        if len(CACHE) > 250:
            CACHE.pop(next(iter(CACHE)))
        CACHE[cache_key] = (now + ttl, value)
    return value

async def rpc_call(chain: str, method: str, params: list[Any]) -> Any:
    last_error = "No RPC endpoints configured"
    async with httpx.AsyncClient(timeout=15) as client:
        for endpoint in RPCS[chain]:
            try:
                response = await client.post(
                    endpoint,
                    json={"jsonrpc": "2.0", "id": 1, "method": method, "params": params},
                )
                response.raise_for_status()
                payload = response.json()
                if payload.get("error"):
                    raise RuntimeError(payload["error"].get("message", "RPC error"))
                return payload.get("result")
            except Exception as exc:
                last_error = str(exc)
    raise HTTPException(502, f"All public RPC endpoints failed: {last_error}")

def address_from_word(word: str | None) -> str | None:
    if not word or word == "0x":
        return None
    address = "0x" + word[-40:]
    return None if address.lower() == "0x" + "0" * 40 else address

@app.middleware("http")
async def security_headers(request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Cache-Control"] = "no-store"
    return response

@app.get("/health")
async def health():
    return {"status": "ok", "service": "aegis-api", "mode": "read-only", "version": "0.2.0"}

@app.get("/api/chains")
async def chains():
    return [{"id": key, "label": key.title(), "chainId": CHAIN_IDS[key]} for key in RPCS]

@app.get("/api/capabilities")
async def capabilities():
    return {
        "liveReadOnly": [
            "DeFiLlama protocol registry and details",
            "EVM bytecode and account metadata at a pinned block",
            "EIP-1967 implementation/admin/beacon slot inspection",
            "Sourcify verified-source and proxy metadata lookup",
            "Protocol address candidate extraction",
        ],
        "staticAnalysis": ["Slither worker implementation is deployed separately"],
        "notImplemented": [
            "Persistent scan job queue and findings database",
            "Full contract ownership attribution and all proxy standards",
            "Aderyn and Mythril execution",
            "Foundry/Anvil protocol-specific fork reproduction",
            "Multi-user identity, tenancy, audit log and report signing",
        ],
        "safety": "Live-chain access is read-only. Static-analysis signals are not confirmed vulnerabilities. Fork simulations do not by themselves prove live exploitability.",
    }

@app.get("/api/protocols")
async def protocols(
    chain: str | None = None,
    category: str | None = None,
    q: str | None = None,
    limit: int = Query(100, ge=1, le=500),
):
    try:
        rows = await get_json(LLAMA + "/protocols", cache_key="protocols", ttl=300)
        items = []
        for item in rows:
            supported = item.get("chains") or []
            if chain and chain.lower() not in [str(c).lower() for c in supported]:
                continue
            if category and category.lower() not in str(item.get("category", "")).lower():
                continue
            if q and q.lower() not in (str(item.get("name", "")) + " " + str(item.get("slug", ""))).lower():
                continue
            items.append({
                "name": item.get("name"), "slug": item.get("slug"),
                "category": item.get("category"), "chains": supported,
                "tvl": item.get("tvl"), "url": item.get("url"),
                "symbol": item.get("symbol"), "chainTvls": item.get("chainTvls", {}),
            })
        items.sort(key=lambda x: float(x.get("tvl") or 0), reverse=True)
        return {"items": items[:limit], "count": min(len(items), limit), "source": "DeFiLlama", "generatedAt": time.time()}
    except httpx.HTTPError as exc:
        raise HTTPException(502, "Protocol registry upstream request failed") from exc

@app.get("/api/protocol/{slug}/contracts")
async def protocol_contract_candidates(slug: str):
    if not re.fullmatch(r"[a-zA-Z0-9._-]{1,120}", slug):
        raise HTTPException(400, "Invalid protocol slug")
    try:
        protocol = await get_json(LLAMA + "/protocol/" + slug, cache_key="protocol:" + slug, ttl=120)
    except httpx.HTTPError as exc:
        raise HTTPException(502, "Protocol detail upstream request failed") from exc
    found: dict[str, dict[str, Any]] = {}
    visited = 0

    def walk(value: Any, path: str, depth: int = 0):
        nonlocal visited
        if depth > 9 or visited > 8000 or value is None:
            return
        visited += 1
        if isinstance(value, str):
            pattern = re.compile(r"(?:([a-zA-Z][a-zA-Z0-9_-]{1,24}):)?(0x[a-fA-F0-9]{40})")
            for match in pattern.finditer(value):
                address = match.group(2)
                if address.lower() == "0x" + "0" * 40:
                    continue
                prefix = (match.group(1) or "").lower()
                chain = prefix if prefix in RPCS else next((c for c in RPCS if c in path.lower()), None)
                key = (chain or "unknown") + ":" + address.lower()
                found.setdefault(key, {
                    "chain": chain, "address": address,
                    "sourcePath": path, "attribution": "unverified_candidate",
                })
        elif isinstance(value, list):
            for index, item in enumerate(value[:500]):
                walk(item, f"{path}[{index}]", depth + 1)
        elif isinstance(value, dict):
            for key, item in list(value.items())[:500]:
                walk(item, f"{path}.{key}", depth + 1)

    walk(protocol, "protocol")
    return {
        "protocolSlug": slug,
        "candidates": list(found.values())[:250],
        "count": len(found),
        "source": "DeFiLlama protocol payload",
        "warning": "Extracted addresses are unverified candidates. Chain attribution and protocol ownership must be independently validated.",
    }

@app.get("/api/protocol/{slug}")
async def protocol(slug: str):
    if not re.fullmatch(r"[a-zA-Z0-9._-]{1,120}", slug):
        raise HTTPException(400, "Invalid protocol slug")
    try:
        data = await get_json(LLAMA + "/protocol/" + slug, cache_key="protocol:" + slug, ttl=120)
        return {"protocol": data, "source": "DeFiLlama"}
    except httpx.HTTPStatusError as exc:
        raise HTTPException(exc.response.status_code, "Protocol not found upstream") from exc
    except httpx.HTTPError as exc:
        raise HTTPException(502, "Protocol detail upstream request failed") from exc

@app.get("/api/contract/inspect")
async def inspect_contract(chain: str, address: str):
    key = chain.lower()
    if key not in RPCS:
        raise HTTPException(400, f"Unsupported chain. Supported: {', '.join(RPCS)}")
    if not re.fullmatch(r"0x[a-fA-F0-9]{40}", address):
        raise HTTPException(400, "Invalid EVM address")
    block_tag = await rpc_call(key, "eth_blockNumber", [])
    code, nonce, balance = await asyncio.gather(
        rpc_call(key, "eth_getCode", [address, block_tag]),
        rpc_call(key, "eth_getTransactionCount", [address, block_tag]),
        rpc_call(key, "eth_getBalance", [address, block_tag]),
    )
    if code == "0x":
        raise HTTPException(404, "No contract bytecode at this address on the selected chain")
    implementation_word, admin_word, beacon_word = await __import__("asyncio").gather(
        rpc_call(key, "eth_getStorageAt", [address, EIP1967["implementation"], block_tag]),
        rpc_call(key, "eth_getStorageAt", [address, EIP1967["admin"], block_tag]),
        rpc_call(key, "eth_getStorageAt", [address, EIP1967["beacon"], block_tag]),
    )
    implementation = address_from_word(implementation_word)
    admin = address_from_word(admin_word)
    beacon = address_from_word(beacon_word)
    implementation_code = None
    if implementation:
        implementation_code = await rpc_call(key, "eth_getCode", [implementation, block_tag])
    verified_source = None
    verification = "not_found"
    try:
        verified_source = await get_json(
            f"{SOURCIFY}/v2/contract/{CHAIN_IDS[key]}/{address}",
            params={"fields": "all"},
            cache_key=f"sourcify:{key}:{address.lower()}",
            ttl=600,
        )
        verification = verified_source.get("match", "verified")
    except httpx.HTTPError:
        pass
    return {
        "chain": key, "chainId": CHAIN_IDS[key], "address": address,
        "hasCode": True, "bytecodeBytes": max(0, (len(code) - 2) // 2),
        "bytecode": code, "blockNumber": int(block_tag, 16), "blockTag": block_tag,
        "transactionCount": int(nonce, 16), "balanceWei": str(int(balance, 16)),
        "proxy": {
            "eip1967Implementation": implementation,
            "eip1967Admin": admin,
            "eip1967Beacon": beacon,
            "implementationHasCode": implementation_code is not None and implementation_code != "0x" if implementation else None,
            "sourcifyResolution": (verified_source or {}).get("proxyResolution"),
        },
        "verifiedSource": verified_source, "verification": verification,
        "evidence": {
            "methods": ["eth_blockNumber", "eth_getCode", "eth_getTransactionCount", "eth_getBalance", "eth_getStorageAt"],
            "blockTag": block_tag, "source": "public RPC",
        },
        "limitations": [
            "EIP-1967 slots are checked; beacon resolution, minimal proxies, diamond facets and non-standard proxy patterns may need additional handling.",
            "Non-empty bytecode and source verification do not establish protocol ownership or prove a vulnerability.",
        ],
    }

@app.post("/api/scans/slither")
async def queue_slither_scan(file: UploadFile = File(...), authorization: str | None = Header(default=None)):
    token = os.getenv("AEGIS_SCAN_TOKEN", "")
    if not token:
        raise HTTPException(503, "Static-analysis gateway is not configured")
    if authorization != "Bearer " + token:
        raise HTTPException(401, "Unauthorized")
    if not file.filename or not file.filename.lower().endswith(".zip"):
        raise HTTPException(400, "Upload a ZIP archive of Solidity project sources")
    data = await file.read(20 * 1024 * 1024 + 1)
    if len(data) > 20 * 1024 * 1024:
        raise HTTPException(413, "Archive exceeds 20 MB limit")
    worker_url = os.getenv("AEGIS_WORKER_URL", "http://aegis-slither-worker.railway.internal:8001")
    worker_token = os.getenv("AEGIS_WORKER_TOKEN", "")
    if not worker_token:
        raise HTTPException(503, "Static-analysis worker credentials are not configured")
    try:
        async with httpx.AsyncClient(timeout=200) as client:
            response = await client.post(
                worker_url + "/scan/slither",
                files={"file": (file.filename, data, "application/zip")},
                headers={"Authorization": "Bearer " + worker_token},
            )
        if response.status_code >= 400:
            raise HTTPException(response.status_code, response.text[:2000])
        return response.json()
    except httpx.HTTPError as exc:
        raise HTTPException(502, "Static-analysis worker unavailable") from exc
