"""API 接口测试（适配统一响应结构）"""
import pytest
from fastapi.testclient import TestClient
from stock_platform.api.main import app

client = TestClient(app)


def _data(resp):
    """提取统一响应中的 data 字段"""
    return resp.json()["data"]


def test_root():
    resp = client.get("/")
    assert resp.status_code == 200
    body = resp.json()
    assert body["code"] == 0
    assert body["data"]["status"] == "running"


def test_health():
    resp = client.get("/health")
    assert resp.status_code == 200
    assert _data(resp)["status"] == "ok"


def test_search_empty():
    resp = client.get("/stocks/search", params={"q": "ZZZZZ9999"})
    assert resp.status_code == 200
    assert _data(resp) == []


def test_quality():
    resp = client.get("/quality")
    assert resp.status_code == 200
    body = resp.json()
    assert body["code"] == 0
    assert "stock_count" in body["data"]


def test_rankings_changes():
    resp = client.get("/rankings/changes", params={"limit": 5})
    assert resp.status_code == 200
    assert resp.json()["code"] == 0


def test_rankings_volume():
    resp = client.get("/rankings/volume", params={"limit": 5})
    assert resp.status_code == 200
    assert resp.json()["code"] == 0
