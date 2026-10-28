"""
tests/test_dev_key.py

La clave de desarrollador viene del .env: sin ella los endpoints
protegidos responden 503; con una incorrecta, 401; con la correcta, pasan.
"""

from app.infrastructure.dev_key_store import dev_key_store

PROTECTED_URL = "/dev/gateway/status"


def test_correct_key_is_accepted(client):
    assert client.get(PROTECTED_URL).status_code == 200


def test_wrong_key_is_rejected(client):
    response = client.get(PROTECTED_URL, headers={"X-Dev-Key": "otra-clave-incorrecta-123456"})
    assert response.status_code == 401


def test_missing_key_is_rejected(client):
    client.headers.pop("X-Dev-Key")
    assert client.get(PROTECTED_URL).status_code == 401


def test_unconfigured_server_answers_503(client, monkeypatch):
    monkeypatch.setattr(dev_key_store, "_key", "")
    assert client.get(PROTECTED_URL).status_code == 503


def test_short_key_counts_as_unconfigured(client, monkeypatch):
    monkeypatch.setattr(dev_key_store, "_key", "corta")
    assert client.get(PROTECTED_URL, headers={"X-Dev-Key": "corta"}).status_code == 503
