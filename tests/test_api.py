"""API 接口测试"""
import pytest
from fastapi.testclient import TestClient
from stock_platform.api.main import app

client = TestClient(app)


def test_root():
    resp = client.get("/")
    assert resp.status_code == 200
    data = resp.json()
    assert "status" in data
    assert data["status"] == "running"


def test_health():
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_search_empty():
    resp = client.get("/stocks/search", params={"q": "ZZZZZ9999"})
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


def test_quality():
    resp = client.get("/quality")
    assert resp.status_code == 200
    data = resp.json()
    assert "stock_count" in data


def test_rankings_changes():
    resp = client.get("/rankings/changes", params={"limit": 5})
    assert resp.status_code == 200


def test_rankings_volume():
    resp = client.get("/rankings/volume", params={"limit": 5})
    assert resp.status_code == 200
