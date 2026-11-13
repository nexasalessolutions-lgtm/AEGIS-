import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

def test_health_is_read_only():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["mode"] == "read-only"

def test_chain_catalog_has_expected_networks():
    response = client.get("/api/chains")
    assert response.status_code == 200
    assert {item["id"] for item in response.json()} >= {"ethereum", "arbitrum", "base"}

def test_invalid_address_is_rejected():
    response = client.get("/api/contract/inspect", params={"chain": "ethereum", "address": "0x123"})
    assert response.status_code == 400

def test_unsupported_chain_is_rejected():
    response = client.get("/api/contract/inspect", params={"chain": "not-a-chain", "address": "0x" + "1" * 40})
    assert response.status_code == 400

def test_invalid_protocol_slug_is_rejected():
    response = client.get("/api/protocol/../../etc/passwd")
    assert response.status_code in (400, 404)


def test_adapter_contract_discovery_extracts_and_verifies_live_addresses(monkeypatch):
    import asyncio
    import main

    main.CACHE.clear()
    protocol = {"name": "Aave", "chains": ["Ethereum", "Polygon"]}
    source = '''
    const addressesProviderRegistryETH = "0x1111111111111111111111111111111111111111";
    const aaveStakingContract = "0x2222222222222222222222222222222222222222";
    module.exports = {
      ethereum: { tvl: ethereum(false) },
      polygon: v2("polygon", "0x3333333333333333333333333333333333333333")
    };
    '''
    class FakeResponse:
        def __init__(self, payload=None, text=""):
            self._payload, self.text, self.status_code = payload, text, 200
        def raise_for_status(self): return None
        def json(self): return self._payload

    class FakeClient:
        async def __aenter__(self): return self
        async def __aexit__(self, *args): return None
        async def get(self, url):
            if url.endswith("/projects/aave/index.js") or "raw.githubusercontent.com" in url:
                return FakeResponse(text=source)
            if url.endswith("/contents/projects/aave"):
                return FakeResponse([{"type":"file","path":"projects/aave/index.js","download_url":"https://raw.githubusercontent.com/DefiLlama/DefiLlama-Adapters/main/projects/aave/index.js"}])
            raise AssertionError("Unexpected URL " + url)

    async def fake_get_json(*args, **kwargs): return protocol
    async def fake_rpc(chain, method, params):
        if method == "eth_blockNumber":
            return "0x64"
        if method == "eth_getCode":
            address = params[0].lower()
            if address == "0x3333333333333333333333333333333333333333":
                return "0x60006000" if chain == "polygon" else "0x"
            if address in {
                "0x1111111111111111111111111111111111111111",
                "0x2222222222222222222222222222222222222222",
                "0x4444444444444444444444444444444444444444",
            }:
                return "0x60006000"
            return "0x"
        if method == "eth_getStorageAt":
            if params[0].lower() == "0x2222222222222222222222222222222222222222" and params[1] == main.EIP1967["implementation"]:
                return "0x" + "0" * 24 + "4444444444444444444444444444444444444444"
            return "0x" + "0" * 64
        raise AssertionError("Unexpected RPC method " + method)

    monkeypatch.setattr(main, "get_json", fake_get_json)
    monkeypatch.setattr(main.httpx, "AsyncClient", lambda **kwargs: FakeClient())
    monkeypatch.setattr(main, "rpc_call", fake_rpc)
    result = asyncio.run(main.protocol_contract_candidates("aave"))
    assert result["adapterFilesRead"] == 1
    assert result["candidateCount"] >= 3
    assert all(item["hasCode"] for item in result["candidates"])
    assert {item["chain"] for item in result["candidates"]} >= {"ethereum", "polygon"}
    proxy_impl = next(item for item in result["candidates"] if item["role"] == "proxy_implementation")
    assert proxy_impl["address"].lower() == "0x4444444444444444444444444444444444444444"
    assert proxy_impl["proxyAddress"].lower() == "0x2222222222222222222222222222222222222222"


def test_auto_scan_requires_server_side_token(monkeypatch):
    import main
    monkeypatch.setattr(main.os, "environ", {})
    response = client.post("/api/scans/protocol/aave")
    assert response.status_code == 401


def test_scan_job_status_requires_server_side_token():
    response = client.get("/api/scans/jobs/00000000-0000-0000-0000-000000000000")
    assert response.status_code == 401


def test_protocol_scan_runs_multiple_unique_targets_with_a_hard_cap(monkeypatch):
    import asyncio
    import main

    items = [
        {"chain": "ethereum", "address": "0x" + f"{i:040x}", "role": "contract", "confidence": "high"}
        for i in range(15)
    ]
    items.append(dict(items[0]))
    async def fake_discovery(slug):
        return {"candidates": items, "candidateCount": len(items), "chainsChecked": ["ethereum"], "adapterFilesRead": 1, "rpcChecks": 15, "warnings": []}
    seen = []
    async def fake_scan(slug, candidate, discovered):
        seen.append(candidate["address"])
        return {"target": {"chain": candidate["chain"], "address": candidate["address"]}, "analysis": {"findingCount": 2}}
    monkeypatch.setattr(main, "protocol_contract_candidates", fake_discovery)
    monkeypatch.setattr(main, "execute_single_contract_scan", fake_scan)
    progress_updates = []
    result = asyncio.run(main.execute_protocol_scan("demo", progress_callback=progress_updates.append))
    assert progress_updates[-1]["stage"] == "completed"
    assert progress_updates[-1]["completed"] == 15
    assert result["targetsDiscovered"] == 16
    assert result["targetsSelected"] == 15
    assert result["targetsScanned"] == 15
    assert result["findingCount"] == 30
    assert len(set(seen)) == 15


def test_protocol_snapshot_returns_pinned_block_contract_evidence(monkeypatch):
    import asyncio
    import main

    async def fake_discovery(slug):
        return {"candidates": [
            {"chain": "ethereum", "address": "0x" + "1" * 40, "role": "core", "confidence": "high"},
            {"chain": "base", "address": "0x" + "2" * 40, "role": "vault", "confidence": "high"},
        ], "candidateCount": 2}
    async def fake_inspect(chain, address, block_number=None):
        return {"chain": chain, "address": address, "hasCode": True, "blockNumber": block_number or 123, "bytecode": "0x6000", "bytecodeBytes": 2, "verifiedSource": {"abi": []}}
    async def fake_rpc(chain, method, params):
        if method == "eth_blockNumber":
            return "0x7b"
        raise AssertionError(method)
    monkeypatch.setattr(main, "protocol_contract_candidates", fake_discovery)
    monkeypatch.setattr(main, "inspect_contract", fake_inspect)
    monkeypatch.setattr(main, "rpc_call", fake_rpc)
    result = asyncio.run(main.protocol_live_snapshot("demo", 12))
    assert result["targetsInspected"] == 2
    assert result["targetsAvailable"] == 2
    assert {item["chain"] for item in result["targets"]} == {"ethereum", "base"}
    assert all(item["blockNumber"] == 123 for item in result["targets"])


def test_scan_job_persistence_round_trip(tmp_path, monkeypatch):
    import main

    monkeypatch.setattr(main, "DATABASE_PATH", str(tmp_path / "aegis.sqlite3"))
    main.initialize_database()
    job = {
        "jobId": "12345678-1234-1234-1234-123456789abc",
        "protocolSlug": "aave",
        "status": "completed",
        "createdAt": __import__("time").time(),
        "updatedAt": __import__("time").time(),
        "result": {"findingCount": 3, "classification": "STATIC_ANALYSIS_SIGNALS"},
    }
    main.persist_scan_job(job)
    main.SCAN_JOBS.clear()
    main.initialize_database()
    assert main.SCAN_JOBS[job["jobId"]]["result"]["findingCount"] == 3


def test_interrupted_scan_is_requeued_after_restart(tmp_path, monkeypatch):
    import main

    monkeypatch.setattr(main, "DATABASE_PATH", str(tmp_path / "restart.sqlite3"))
    main.initialize_database()
    job = {
        "jobId": "22345678-1234-1234-1234-123456789abc",
        "protocolSlug": "compound",
        "status": "running",
        "createdAt": __import__("time").time(),
        "updatedAt": __import__("time").time(),
    }
    main.persist_scan_job(job)
    main.SCAN_JOBS.clear()
    main.initialize_database()
    restored = main.SCAN_JOBS[job["jobId"]]
    assert restored["status"] == "queued"
    assert "Recovered after API restart" in restored["recoveryNote"]


def test_contract_inspection_falls_back_to_blockscout_abi_and_source(monkeypatch):
    import asyncio
    import main

    async def fake_rpc(chain, method, params):
        if method == "eth_blockNumber":
            return "0x64"
        if method == "eth_getCode":
            return "0x60006000"
        if method == "eth_getTransactionCount":
            return "0x2"
        if method == "eth_getBalance":
            return "0x0"
        if method == "eth_getStorageAt":
            return "0x" + "0" * 64
        raise AssertionError(method)

    async def fake_get_json(url, **kwargs):
        if "sourcify" in url:
            raise main.httpx.ConnectError("Sourcify unavailable")
        if "blockscout" in url:
            return {
                "abi": [{"type": "function", "name": "totalSupply"}],
                "source_code": "pragma solidity ^0.8.0; contract Example {}",
                "file_path": "Example.sol",
                "compiler_version": "v0.8.20+commit.a1b79de6",
            }
        raise AssertionError(url)

    monkeypatch.setattr(main, "rpc_call", fake_rpc)
    monkeypatch.setattr(main, "get_json", fake_get_json)
    result = asyncio.run(main.inspect_contract("ethereum", "0x" + "1" * 40))
    assert result["verification"] == "blockscout_verified"
    assert result["verifiedSource"]["abi"][0]["name"] == "totalSupply"
    assert "Example.sol" in result["verifiedSource"]["sources"]


def test_discovery_keeps_same_address_when_deployed_on_multiple_chains(monkeypatch):
    import asyncio
    import main

    main.CACHE.clear()
    protocol = {"name": "Multi-chain", "chains": ["Ethereum", "Polygon"]}
    address = "0x" + "a" * 40
    source = (
        f'const routerEthereum = "{address}";\n'
        "const fillerOne = 1;\nconst fillerTwo = 2;\nconst fillerThree = 3;\nconst fillerFour = 4;\n"
        f'const routerPolygon = "{address}";\n'
    )

    class FakeResponse:
        status_code = 200
        def __init__(self, payload=None, text=""):
            self.payload, self.text = payload, text
        def raise_for_status(self): return None
        def json(self): return self.payload

    class FakeClient:
        async def __aenter__(self): return self
        async def __aexit__(self, *args): return None
        async def get(self, url):
            if url.endswith("/projects/multichain/index.js"):
                return FakeResponse(text=source)
            raise AssertionError(url)

    async def fake_get_json(*args, **kwargs): return protocol
    async def fake_rpc(chain, method, params):
        if method == "eth_blockNumber": return "0x64"
        if method == "eth_getCode": return "0x6000"
        if method == "eth_getStorageAt": return "0x" + "0" * 64
        raise AssertionError(method)

    monkeypatch.setattr(main, "get_json", fake_get_json)
    monkeypatch.setattr(main.httpx, "AsyncClient", lambda **kwargs: FakeClient())
    monkeypatch.setattr(main, "rpc_call", fake_rpc)
    result = asyncio.run(main.protocol_contract_candidates("multichain"))
    matches = [item for item in result["candidates"] if item["address"].lower() == address.lower()]
    assert {item["chain"] for item in matches} == {"ethereum", "polygon"}
    assert all(item["blockNumber"] == 100 for item in matches)


def test_scan_job_memory_cache_is_bounded_without_dropping_active_jobs():
    import main

    original = dict(main.SCAN_JOBS)
    try:
        main.SCAN_JOBS.clear()
        for index in range(105):
            job_id = f"cache-{index}"
            main.SCAN_JOBS[job_id] = {
                "jobId": job_id,
                "protocolSlug": "demo",
                "status": "completed",
                "createdAt": float(index),
                "updatedAt": float(index),
            }
        main.SCAN_JOBS["active-job"] = {
            "jobId": "active-job",
            "protocolSlug": "demo",
            "status": "running",
            "createdAt": 0.0,
            "updatedAt": 0.0,
        }
        main.prune_scan_job_cache()
        assert len(main.SCAN_JOBS) == 100
        assert "active-job" in main.SCAN_JOBS
        assert "cache-104" in main.SCAN_JOBS
    finally:
        main.SCAN_JOBS.clear()
        main.SCAN_JOBS.update(original)
