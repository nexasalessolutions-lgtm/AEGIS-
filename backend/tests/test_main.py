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
