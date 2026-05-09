from pathlib import Path
from sidekick.parser import parse_session_file

FIXTURES = Path(__file__).parent / "fixtures"

def test_parse_completed_returns_three_turns():
    turns = list(parse_session_file(FIXTURES / "completed.jsonl"))
    assert len(turns) == 3
    assert turns[0].role == "user"
    assert turns[0].text == "Add a function to compute fibonacci"
    assert turns[0].session_id == "sess-completed"
    assert turns[0].cwd == "/proj/foo"
    assert turns[1].role == "assistant"
    assert turns[1].input_tokens == 100
    assert turns[1].output_tokens == 50

def test_parse_skips_malformed_lines(tmp_path):
    f = tmp_path / "bad.jsonl"
    f.write_text(
        '{"type":"user","message":{"role":"user","content":"ok"},"sessionId":"s1","timestamp":"2026-05-04T10:00:00Z"}\n'
        'not-json-at-all\n'
        '{"type":"user","message":{"role":"user","content":"ok2"},"sessionId":"s1","timestamp":"2026-05-04T10:00:01Z"}\n'
    )
    turns = list(parse_session_file(f))
    assert len(turns) == 2

def test_parse_returns_byte_offsets():
    turns = list(parse_session_file(FIXTURES / "completed.jsonl"))
    assert turns[0].byte_offset == 0
    assert turns[1].byte_offset > 0
    assert turns[2].byte_offset > turns[1].byte_offset

def test_parse_empty_file(tmp_path):
    f = tmp_path / "empty.jsonl"
    f.write_text("")
    assert list(parse_session_file(f)) == []
