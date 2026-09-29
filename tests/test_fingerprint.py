import json

from llm_cost_teardown.fingerprint import fingerprint_log_line, fingerprint_request, prompt_blocks

SALT = b"test-salt"


def chat(question: str, **extra) -> dict:
    return {
        "model": "gpt-5.4",
        "messages": [
            {"role": "system", "content": "You are a support agent for Acme."},
            {"role": "user", "content": "My order is late."},
            {"role": "user", "content": question},
        ],
        **extra,
    }


def test_shared_prefix_gives_shared_hashes():
    a = fingerprint_request(chat("Where is it?"), SALT)
    b = fingerprint_request(chat("Can I cancel?"), SALT)
    assert a["prefix_hashes"][:2] == b["prefix_hashes"][:2]
    assert a["prefix_hashes"][2] != b["prefix_hashes"][2]
    assert a["prefix_chars"][:2] == b["prefix_chars"][:2]


def test_salt_changes_every_hash():
    a = fingerprint_request(chat("x"), SALT)
    b = fingerprint_request(chat("x"), b"other")
    assert not set(a["prefix_hashes"]) & set(b["prefix_hashes"])


def test_request_hash_ignores_transport_fields():
    base = fingerprint_request(chat("x"), SALT)["request_hash"]
    assert fingerprint_request(chat("x", stream=True, user="u1"), SALT)["request_hash"] == base
    assert fingerprint_request(chat("x", temperature=0.2), SALT)["request_hash"] != base


def test_anthropic_block_order_tools_system_messages():
    request = {
        "tools": [{"name": "lookup"}],
        "system": [{"type": "text", "text": "rules"}, {"type": "text", "text": "context", "cache_control": {}}],
        "messages": [{"role": "user", "content": [{"type": "text", "text": "hi"}, {"type": "text", "text": "q"}]}],
    }
    blocks = prompt_blocks(request)
    assert list(blocks[0]) == ["tools"]
    assert [list(b) for b in blocks[1:3]] == [["system"], ["system"]]
    assert len(blocks) == 5


def test_log_line_drops_prompt_and_response_text():
    record = {
        "timestamp": "2026-09-01T00:00:00Z",
        "model": "gpt-5.4",
        "usage": {"prompt_tokens": 10, "completion_tokens": 2},
        "request": chat("SECRET CUSTOMER QUESTION"),
        "response": {"choices": [{"message": {"content": "SECRET ANSWER"}}]},
    }
    out = json.dumps(fingerprint_log_line(record, SALT))
    assert "SECRET" not in out
    assert "Acme" not in out
    assert '"prefix_hashes"' in out and '"usage"' in out
