"""Regression tests for the recall project-scoping bug.

Root cause: recall passed the raw cwd (e.g. 'D:\\Aru\\NYU\\x') as a HARD filter
against sessions.project, which stores Claude's encoded dir name ('D--Aru-NYU-x').
The LIKE never matched, so semantic() returned zero rows and recall was always
silent. Fix: encode the cwd and apply project as a soft ranking BOOST, not a filter.
"""
from sidekick import search, daemon
from sidekick.paths import encode_project


def test_encode_project_matches_claude_dir_name():
    assert encode_project("D:\\Aru\\NYU\\agent-flight-recorder") == "D--Aru-NYU-agent-flight-recorder"
    assert encode_project("D:\\Aru\\NYU") == "D--Aru-NYU"
    # trailing separator is ignored
    assert encode_project("D:\\Aru\\NYU\\") == "D--Aru-NYU"
    # non-alphanumerics each map to a single dash (no collapsing), matching the indexer
    assert encode_project("C:\\Users\\u\\Temp\\claude-ab") == "C--Users-u-Temp-claude-ab"
    assert encode_project(None) is None


def test_apply_project_boost_prefers_matching_project():
    results = search._apply_project_boost(
        [
            {"session_id": "other", "project": "D--other", "score": 0.62},
            {"session_id": "mine", "project": "D--Aru-NYU-x", "score": 0.58},
        ],
        boost_project="D--Aru-NYU-x",
    )
    assert results[0]["session_id"] == "mine"
    assert round(results[0]["score"], 4) == round(0.58 * search.PROJECT_BOOST, 4)


def test_apply_project_boost_noop_without_target():
    rows = [{"session_id": "a", "project": "p", "score": 0.5}]
    assert search._apply_project_boost(rows, None)[0]["score"] == 0.5


def test_recall_boosts_current_project_without_hard_filter(monkeypatch):
    """The daemon must call semantic() with NO hard project filter (the bug) and
    the ENCODED cwd as boost_project."""
    captured = {}

    def fake_semantic(prompt, limit=5, project=None, boost_project=None):
        captured["project"] = project
        captured["boost_project"] = boost_project
        return []

    monkeypatch.setattr(daemon.search, "semantic", fake_semantic)
    srv = daemon.Server.__new__(daemon.Server)  # skip start()/model load
    srv._embedder = object()
    resp = srv._recall("how does afr manage worktrees", "D:\\Aru\\NYU\\agent-flight-recorder")

    assert resp == {"ok": True, "hit": None}
    assert captured["project"] is None  # no hard filter -> the original bug is gone
    assert captured["boost_project"] == "D--Aru-NYU-agent-flight-recorder"
