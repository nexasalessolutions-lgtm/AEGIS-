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
        if method == "eth_getCode":
            address = params[0].lower()
            if address in {
                "0x1111111111111111111111111111111111111111",
                "0x2222222222222222222222222222222222222222",
                "0x3333333333333333333333333333333333333333",
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
