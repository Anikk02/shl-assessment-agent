# tests/test_api.py
import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_health_check():
    """Test health check endpoint"""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_chat_clarify():
    """Test chat with vague query"""
    response = client.post("/chat", json={
        "messages": [
            {"role": "user", "content": "I need an assessment"}
        ]
    })
    assert response.status_code == 200
    data = response.json()
    assert "reply" in data
    assert data["recommendations"] == []
    assert data["end_of_conversation"] is False


def test_chat_recommend():
    """Test chat with sufficient details"""
    response = client.post("/chat", json={
        "messages": [
            {"role": "user", "content": "I need an assessment"},
            {"role": "assistant", "content": "What role are you hiring for?"},
            {"role": "user", "content": "Hiring a senior Java developer with stakeholder management skills"}
        ]
    })
    assert response.status_code == 200
    data = response.json()
    assert "reply" in data
    assert len(data["recommendations"]) > 0
    assert data["end_of_conversation"] in [True, False]


def test_chat_compare():
    """Test comparison request"""
    response = client.post("/chat", json={
        "messages": [
            {"role": "user", "content": "What is the difference between OPQ and GSA?"}
        ]
    })
    assert response.status_code == 200
    data = response.json()
    assert "reply" in data
    assert "OPQ" in data["reply"] or "GSA" in data["reply"]


def test_chat_out_of_scope():
    """Test out-of-scope request"""
    response = client.post("/chat", json={
        "messages": [
            {"role": "user", "content": "How should I structure an interview loop?"}
        ]
    })
    assert response.status_code == 200
    data = response.json()
    assert "reply" in data
    assert data["recommendations"] == []
    assert "cannot" in data["reply"].lower() or "not" in data["reply"].lower()


def test_chat_schema_validation():
    """Test schema validation"""
    # Invalid message role
    response = client.post("/chat", json={
        "messages": [
            {"role": "invalid", "content": "Test"}
        ]
    })
    assert response.status_code == 422