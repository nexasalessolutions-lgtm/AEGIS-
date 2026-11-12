from __future__ import annotations

import asyncio
import io
import zipfile
import os
import re
import time
from typing import Any
from pathlib import PurePosixPath

import httpx
from fastapi import FastAPI, File, Header, HTTPException, Query, Request, UploadFile
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
BLOCKSCOUT = {
    "ethereum": "https://eth.blockscout.com",
    "arbitrum": "https://arbitrum.blockscout.com",
    "optimism": "https://optimism.blockscout.com",
    "base": "https://base.blockscout.com",
    "polygon": "https://polygon.blockscout.com",
    "gnosis": "https://gnosis.blockscout.com",
    "celo": "https://celo.blockscout.com",
    "linea": "https://linea.blockscout.com",
    "scroll": "https://scroll.blockscout.com",
    "zksync": "https://zksync.blockscout.com",
}
CHAIN_IDS = {
    "ethereum": 1, "optimism": 10, "bsc": 56, "gnosis": 100, "polygon": 137,
    "fantom": 250, "zksync": 324, "celo": 42220, "arbitrum": 42161,
    "avalanche": 43114, "base": 8453, "linea": 59144, "scroll": 534352,
    "blast": 81457, "mode": 34443, "mantle": 5000, "opbnb": 204,
    "sonic": 146, "unichain": 130, "berachain": 80094, "zora": 7777777,
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
    "celo": ["https://forno.celo.org"],
    "fantom": ["https://rpc.ftm.tools"],
    "zksync": ["https://mainnet.era.zksync.io"],
    "linea": ["https://rpc.linea.build"],
    "scroll": ["https://rpc.scroll.io"],
    "blast": ["https://rpc.blast.io"],
    "mode": ["https://mainnet.mode.network"],
    "mantle": ["https://rpc.mantle.xyz"],
    "opbnb": ["https://opbnb-mainnet-rpc.bnbchain.org"],
    "sonic": ["https://rpc.soniclabs.com"],
    "unichain": ["https://mainnet.unichain.org"],
    "berachain": ["https://rpc.berachain.com"],
    "zora": ["https://rpc.zora.energy"],
}
EIP1967 = {
    "implementation": "0x360894a13ba1a3210667c828492db98dca3e2076cc3735a920a3ca505d382bbc",
    "admin": "0xb53127684a568b3173ae13b9f8a6016e243e63b6e8ee1178d6a717850b5d6103",
    "beacon": "0xa3f0ad74e5423aebfd80d3ef4346578335a9a72aeaee59ff6cb3582b35133d50",
}
CACHE: dict[str, tuple[float, Any]] = {}
SCAN_REQUESTS: dict[str, list[float]] = {}


def enforce_scan_rate_limit(request: Request):
    forwarded = request.headers.get('x-forwarded-for', '')
    ip = forwarded.split(',')[0].strip() if forwarded else (request.client.host if request.client else 'unknown')
    now = time.monotonic()
    recent = [stamp for stamp in SCAN_REQUESTS.get(ip, []) if now - stamp < 600]
    if len(recent) >= 3:
        raise HTTPException(429, 'Scan limit reached for this IP. Try again in 10 minutes.')
    recent.append(now)
    SCAN_REQUESTS[ip] = recent

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
    """Discover contract candidates from the protocol's DeFiLlama adapter source, then verify live code on supported chains."""
    if not re.fullmatch(r"[a-zA-Z0-9._-]{1,120}", slug):
        raise HTTPException(400, "Invalid protocol slug")
    cache_key = "contracts:" + slug.lower()
    cached = CACHE.get(cache_key)
    if cached and cached[0] > time.monotonic():
        return cached[1]
    try:
        protocol = await get_json(LLAMA + "/protocol/" + slug, cache_key="protocol:" + slug, ttl=300)
    except httpx.HTTPError as exc:
        raise HTTPException(502, "Protocol detail upstream request failed") from exc

    chain_aliases = {
        "ethereum":"ethereum", "eth":"ethereum", "arbitrum":"arbitrum",
        "arbitrum one":"arbitrum", "optimism":"optimism", "op":"optimism",
        "base":"base", "polygon":"polygon", "matic":"polygon", "bsc":"bsc",
        "bnb chain":"bsc", "avalanche":"avalanche", "avax":"avalanche",
        "gnosis":"gnosis", "xdai":"gnosis", "celo":"celo", "fantom":"fantom",
        "sonic":"sonic", "linea":"linea", "scroll":"scroll", "zksync era":"zksync",
        "zksync":"zksync", "mantle":"mantle", "blast":"blast", "mode":"mode",
        "opbnb":"opbnb", "unichain":"unichain", "berachain":"berachain", "zora":"zora",
    }
    supported = []
    for name in protocol.get("chains") or []:
        key = chain_aliases.get(str(name).strip().lower())
        if key and key in RPCS and key not in supported:
            supported.append(key)

    adapter_sources: list[tuple[str, str]] = []
    adapter_warnings: list[str] = []
    github_headers = {
        "User-Agent": "AEGIS-DeFi-Intelligence",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    async with httpx.AsyncClient(timeout=18, headers=github_headers, follow_redirects=True) as client:
        listing = None
        direct_found = False
        raw_root = f"https://raw.githubusercontent.com/DefiLlama/DefiLlama-Adapters/main/projects/{slug}/"
        try:
            direct = await client.get(raw_root + "index.js")
            if direct.status_code == 200:
                direct_found = True
                adapter_sources.append((f"projects/{slug}/index.js", direct.text[:600_000]))
                imports = re.findall(r"""(?:require\s*\(|from\s*)['"]\./([^'"]+)['"]""", direct.text)
                for relative in list(dict.fromkeys(imports))[:25]:
                    if relative.startswith(".") or ".." in PurePosixPath(relative).parts:
                        continue
                    candidates = [relative] if PurePosixPath(relative).suffix else [relative + ".js", relative + "/index.js"]
                    for candidate_path in candidates:
                        response = await client.get(raw_root + candidate_path)
                        if response.status_code == 200:
                            adapter_sources.append((f"projects/{slug}/{candidate_path}", response.text[:600_000]))
                            break
        except httpx.HTTPError as exc:
            adapter_warnings.append("Direct adapter source lookup failed: " + str(exc))
        if not direct_found:
            paths_to_try = [
                f"https://api.github.com/repos/DefiLlama/DefiLlama-Adapters/contents/projects/{slug}",
                f"https://api.github.com/repos/DefiLlama/DefiLlama-Adapters/contents/projects/{slug}.js",
            ]
            for url in paths_to_try:
                try:
                    response = await client.get(url)
                    if response.status_code == 404:
                        continue
                    response.raise_for_status()
                    listing = response.json()
                    break
                except httpx.HTTPError as exc:
                    adapter_warnings.append("DeFiLlama adapter repository lookup failed: " + str(exc))
                    break

        # If the slug casing differs, resolve it against the public projects directory once.
        if listing is None and not adapter_warnings and not direct_found:
            try:
                response = await client.get("https://api.github.com/repos/DefiLlama/DefiLlama-Adapters/contents/projects")
                response.raise_for_status()
                entries = response.json()
                match = next((x for x in entries if str(x.get("name", "")).lower() in {slug.lower(), (slug + ".js").lower()}), None)
                if match:
                    response = await client.get(match["url"])
                    response.raise_for_status()
                    listing = response.json()
            except httpx.HTTPError as exc:
                adapter_warnings.append("Could not resolve adapter directory: " + str(exc))

        file_entries: list[dict[str, Any]] = []
        async def collect(entries: Any, depth: int = 0):
            if depth > 2 or not isinstance(entries, list):
                return
            for entry in entries:
                if len(file_entries) >= 35:
                    return
                kind = entry.get("type")
                path = str(entry.get("path", ""))
                if kind == "file" and path.lower().endswith((".js", ".ts", ".json")):
                    file_entries.append(entry)
                elif kind == "dir" and depth < 2:
                    try:
                        sub = await client.get(entry["url"])
                        sub.raise_for_status()
                        await collect(sub.json(), depth + 1)
                    except httpx.HTTPError:
                        continue

        if listing is not None:
            if isinstance(listing, list):
                await collect(listing)
            elif isinstance(listing, dict) and listing.get("type") == "file":
                file_entries.append(listing)
        for entry in file_entries:
            raw_url = entry.get("download_url")
            if not raw_url:
                continue
            try:
                response = await client.get(raw_url)
                response.raise_for_status()
                adapter_sources.append((str(entry.get("path", "")), response.text[:600_000]))
            except httpx.HTTPError:
                continue

    address_pattern = re.compile(r"0x[a-fA-F0-9]{40}")
    role_pattern = re.compile(r"\b(factory|router|pool|vault|comptroller|controller|registry|proxy|manager|lendingPool|market|staking|gauge|bridge|oracle|treasury|owner|multisig|addressProvider|implementation|beacon|diamond|escrow|masterChef|chef|distributor|governor|timelock|strategy|wrapper)\b", re.I)
    token_pattern = re.compile(r"\b(token|asset|reward|underlying|symbol|blacklist|stablecoin|coreAssets|weth|usdc|usdt|dai)\b", re.I)
    chain_pattern = re.compile(r"\b(ethereum|arbitrum|optimism|polygon|base|bsc|avalanche|avax|gnosis|xdai|celo|fantom|sonic|linea|scroll|zksync|mantle|blast|mode|opbnb|unichain|berachain|zora)\b", re.I)
    collected: dict[str, dict[str, Any]] = {}

    def add_candidate(address: str, source_path: str, source_line: int, context: str, source_url: str):
        if address.lower() == "0x" + "0" * 40:
            return
        chain = None
        aliases = chain_pattern.findall(context)
        for alias in reversed(aliases):
            mapped = chain_aliases.get(alias.lower())
            if mapped in supported:
                chain = mapped
                break
        if chain is None:
            # Explicit suffixes are common in adapter constant names (e.g. registryETH).
            if re.search(r"\b[A-Za-z0-9_]+ETH\b", context) and "ethereum" in supported:
                chain = "ethereum"
            elif len(supported) == 1:
                chain = supported[0]
        role_match = role_pattern.search(context)
        token_match = token_pattern.search(context)
        role = role_match.group(1).lower() if role_match else ("token_or_asset" if token_match else "adapter_reference")
        confidence = "medium" if role_match else ("low" if token_match else "low")
        key = address.lower()
        current = collected.get(key)
        record = {
            "address": address,
            "chain": chain,
            "role": role,
            "confidence": confidence,
            "source": "DefiLlama adapter source",
            "sourcePath": source_path,
            "sourceLine": source_line,
            "sourceUrl": source_url,
            "attribution": "unverified_adapter_candidate",
        }
        if current is None or (confidence == "medium" and current["confidence"] != "medium"):
            collected[key] = record
        elif current and not current.get("chain") and chain:
            current["chain"] = chain

    for path, source in adapter_sources:
        lines = source.splitlines()
        raw_url = "https://github.com/DefiLlama/DefiLlama-Adapters/blob/main/" + path
        for index, line in enumerate(lines):
            matches = list(address_pattern.finditer(line))
            if not matches:
                continue
            context = "\n".join(lines[max(0, index - 2):min(len(lines), index + 3)])
            for match in matches:
                add_candidate(match.group(0), path, index + 1, context, raw_url)

    # Supplement adapter code with any explicit addresses in the protocol metadata itself.
    visited = 0
    def walk_metadata(value: Any, path: str = "protocol", depth: int = 0):
        nonlocal visited
        if depth > 8 or visited > 5000 or value is None:
            return
        visited += 1
        if isinstance(value, str):
            for match in address_pattern.finditer(value):
                context = path + " " + value
                add_candidate(match.group(0), "DeFiLlama protocol metadata", 0, context, "https://api.llama.fi/protocol/" + slug)
        elif isinstance(value, list):
            for index, item in enumerate(value[:300]):
                walk_metadata(item, f"{path}[{index}]", depth + 1)
        elif isinstance(value, dict):
            for key, item in list(value.items())[:300]:
                walk_metadata(item, f"{path}.{key}", depth + 1)
    walk_metadata(protocol)

    # Prioritize likely protocol infrastructure over token/asset references.
    ranked = sorted(
        collected.values(),
        key=lambda x: (0 if x["confidence"] == "medium" else 1, x["sourcePath"], x["sourceLine"]),
    )[:50]

    # Verify candidates against chain bytecode. Unknown-chain candidates are checked against
    # the protocol's advertised EVM chains, with bounded concurrency and a hard request cap.
    semaphore = asyncio.Semaphore(8)
    checks = 0
    async def verify_candidate(candidate: dict[str, Any]):
        nonlocal checks
        target_chains = [candidate["chain"]] if candidate.get("chain") else supported[:4]
        if not target_chains:
            return []
        found = []
        for chain_key in target_chains:
            async with semaphore:
                checks += 1
                if checks > 200:
                    return found
                try:
                    code = await rpc_call(chain_key, "eth_getCode", [candidate["address"], "latest"])
                    if code and code != "0x":
                        found.append({
                            **candidate,
                            "chain": chain_key,
                            "hasCode": True,
                            "bytecodeBytes": max(0, (len(code) - 2) // 2),
                            "attribution": "adapter_source_candidate_code_verified",
                        })
                except Exception:
                    continue
        return found

    verified_groups = await asyncio.gather(*(verify_candidate(item) for item in ranked))
    verified = [item for group in verified_groups for item in group]
    verified.sort(key=lambda x: (0 if x["confidence"] == "medium" else 1, x["chain"], x["address"].lower()))
    result = {
        "protocolSlug": slug,
        "protocolName": protocol.get("name"),
        "candidates": verified[:200],
        "candidateCount": len(verified),
        "sourceCandidates": len(collected),
        "adapterFilesRead": len(adapter_sources),
        "adapterFiles": [path for path, _ in adapter_sources],
        "chainsChecked": supported,
        "rpcChecks": checks,
        "discoveryStatus": "verified_candidates_found" if verified else ("adapter_source_found_no_live_code" if adapter_sources else "adapter_source_not_found"),
        "sources": [
            {"name": "DeFiLlama adapter repository", "url": "https://github.com/DefiLlama/DefiLlama-Adapters/tree/main/projects/" + slug},
            {"name": "DeFiLlama protocol metadata", "url": "https://api.llama.fi/protocol/" + slug},
        ],
        "warnings": adapter_warnings,
        "warning": "Addresses are adapter-source candidates. On-chain bytecode confirms code exists at the address and chain; it does not prove protocol ownership, active use, or vulnerability.",
    }
    CACHE[cache_key] = (time.monotonic() + 600, result)
    return result

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

@app.get("/api/worker/health")
async def worker_health():
    worker_url = os.getenv("AEGIS_WORKER_URL", "http://aegis-slither-worker-v3.railway.internal:8001")
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(worker_url + "/health")
            response.raise_for_status()
            worker = response.json()
        return {"status": worker.get("status", "unknown"), "worker": worker}
    except (httpx.HTTPError, ValueError) as exc:
        raise HTTPException(503, "Private Slither worker is unavailable") from exc

@app.post("/api/scans/protocol/{slug}")
async def auto_scan_protocol(slug: str, request: Request, authorization: str | None = Header(default=None)):
    scan_token = os.getenv("AEGIS_SCAN_TOKEN", "")
    if not scan_token or authorization != "Bearer " + scan_token:
        raise HTTPException(401, "Unauthorized")
    """Automatically discover one contract, retrieve its verified source and run isolated Slither."""
    enforce_scan_rate_limit(request)
    if not re.fullmatch(r"[a-zA-Z0-9._-]{1,120}", slug):
        raise HTTPException(400, "Invalid protocol slug")
    candidates_result = await protocol_contract_candidates(slug)
    candidates = candidates_result.get("candidates") or []
    if not candidates:
        raise HTTPException(404, "No on-chain-verified adapter contract candidates were discovered for this protocol.")
    candidate = next((x for x in candidates if x.get("confidence") == "medium"), candidates[0])
    chain = candidate.get("chain")
    address = candidate.get("address")
    if not chain or chain not in CHAIN_IDS:
        raise HTTPException(422, "The best candidate has no supported chain attribution.")
    verified: dict[str, Any] = {}
    source_provenance = "Sourcify verified contract source"
    try:
        # Sourcify is queried once for the selected candidate; this is not a bulk contract crawl.
        verified = await get_json(
            f"{SOURCIFY}/v2/contract/{CHAIN_IDS[chain]}/{address}",
            params={"fields": "sources"},
            cache_key=f"sourcify-sources:{chain}:{address.lower()}",
            ttl=3600,
        )
    except httpx.HTTPError:
        verified = {}

    source_files: dict[str, str] = {}
    sources = verified.get("sources")
    if isinstance(sources, dict):
        for path, value in sources.items():
            if isinstance(value, str):
                source_files[str(path)] = value
            elif isinstance(value, dict) and isinstance(value.get("content"), str):
                source_files[str(path)] = value["content"]
    elif isinstance(sources, list):
        for item in sources:
            if isinstance(item, dict):
                path = item.get("path") or item.get("name") or f"source-{len(source_files)}.sol"
                value = item.get("content") or item.get("source")
                if isinstance(value, str):
                    source_files[str(path)] = value

    std_json = verified.get("stdJsonInput")
    if not source_files and isinstance(std_json, dict):
        for path, value in (std_json.get("sources") or {}).items():
            if isinstance(value, dict) and isinstance(value.get("content"), str):
                source_files[str(path)] = value["content"]

    # Sourcify may not have this deployment; fall back to a single Blockscout contract lookup.
    if not source_files and chain in BLOCKSCOUT:
        try:
            explorer = await get_json(
                f"{BLOCKSCOUT[chain]}/api/v2/smart-contracts/{address}",
                cache_key=f"blockscout-source:{chain}:{address.lower()}",
                ttl=3600,
            )
            raw_source = explorer.get("source_code") or explorer.get("sourceCode") or ""
            if isinstance(raw_source, str) and raw_source.strip():
                try:
                    parsed_source = json.loads(raw_source)
                except Exception:
                    parsed_source = None
                if isinstance(parsed_source, dict) and isinstance(parsed_source.get("sources"), dict):
                    for path, value in parsed_source["sources"].items():
                        if isinstance(value, dict) and isinstance(value.get("content"), str):
                            source_files[str(path)] = value["content"]
                else:
                    source_files[explorer.get("file_path") or "Contract.sol"] = raw_source
            extras = explorer.get("additional_sources") or explorer.get("additionalSources") or []
            if isinstance(extras, list):
                for item in extras:
                    if isinstance(item, dict):
                        path = item.get("file_path") or item.get("filePath") or f"additional-{len(source_files)}.sol"
                        value = item.get("source_code") or item.get("sourceCode") or item.get("source")
                        if isinstance(value, str):
                            source_files[str(path)] = value
            if source_files:
                source_provenance = "Blockscout verified contract source"
                verified = {"match": "blockscout_verified", **verified}
        except httpx.HTTPError:
            pass

    safe_sources: list[tuple[str, str]] = []
    for path, source in source_files.items():
        normalized = PurePosixPath(path.replace("\\", "/"))
        if normalized.is_absolute() or ".." in normalized.parts:
            continue
        if normalized.suffix.lower() == ".sol" and len(source.encode("utf-8")) <= 2_000_000:
            safe_sources.append((str(normalized), source))
        if len(safe_sources) >= 200:
            break
    if not safe_sources:
        raise HTTPException(422, "No verified Solidity source was available from Sourcify or the supported Blockscout explorer for the selected contract.")

    archive_buffer = io.BytesIO()
    with zipfile.ZipFile(archive_buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path, source in safe_sources:
            archive.writestr(path, source)
    archive_bytes = archive_buffer.getvalue()
    if len(archive_bytes) > 4 * 1024 * 1024:
        raise HTTPException(413, "Automatically collected source bundle exceeds 4 MB.")

    worker_url = os.getenv("AEGIS_WORKER_URL", "")
    worker_token = os.getenv("AEGIS_WORKER_TOKEN", "")
    if not worker_url or not worker_token:
        raise HTTPException(503, "Static-analysis worker is not configured.")
    try:
        async with httpx.AsyncClient(timeout=200) as client:
            response = await client.post(
                worker_url.rstrip("/") + "/scan/slither",
                files={"file": (f"{slug}-{chain}-{address}.zip", archive_bytes, "application/zip")},
                headers={"Authorization": "Bearer " + worker_token},
            )
        if response.status_code >= 400:
            raise HTTPException(response.status_code, response.text[:2000])
        result = response.json()
    except httpx.HTTPError as exc:
        raise HTTPException(502, "Static-analysis worker unavailable.") from exc

    return {
        "protocolSlug": slug,
        "target": {
            "chain": chain, "chainId": CHAIN_IDS[chain], "address": address,
            "role": candidate.get("role"), "adapterSource": candidate.get("sourceUrl"),
            "sourceVerification": verified.get("match") or verified.get("runtimeMatch") or "Sourcify source available",
        },
        "sourceFiles": len(safe_sources),
        "sourceProvenance": source_provenance,
        "analysis": result,
        "classification": "STATIC_ANALYSIS_SIGNAL",
        "disclaimer": "Static-analysis results require manual security review and are not proof of exploitability or current live exploitability.",
    }

@app.post("/api/scans/slither")
async def queue_slither_scan(request: Request, file: UploadFile = File(...), authorization: str | None = Header(default=None)):
    enforce_scan_rate_limit(request)
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
