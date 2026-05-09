import sqlite3
from pathlib import Path


def make_afr_db(path: Path) -> None:
    conn = sqlite3.connect(path)
    conn.executescript(
        """
        CREATE TABLE runs (
            id TEXT PRIMARY KEY,
            source TEXT,
            project_path TEXT,
            started_at TEXT,
            ended_at TEXT,
            user_goal TEXT,
            final_summary TEXT,
            outcome TEXT DEFAULT 'untagged',
            cost_usd REAL DEFAULT 0.0,
            tokens_in INTEGER DEFAULT 0,
            tokens_out INTEGER DEFAULT 0,
            cache_read INTEGER DEFAULT 0,
            cache_write INTEGER DEFAULT 0
        );

        INSERT INTO runs VALUES (
            'abc12345-0000-0000-0000-000000000000',
            'claude',
            '/projects/foo',
            '2026-05-01T10:00:00',
            '2026-05-01T10:30:00',
            'fix the modal deployment error',
            'Fixed by adding huggingface-secret',
            'shipped',
            0.05,
            1842,
            4201,
            920,
            0
        );

        INSERT INTO runs VALUES (
            'def67890-0000-0000-0000-000000000000',
            'claude',
            '/projects/foo',
            '2026-05-02T11:00:00',
            '2026-05-02T11:10:00',
            'debug authentication middleware',
            '',
            'blocked',
            0.01,
            250,
            800,
            100,
            0
        );
        """
    )
    conn.commit()
    conn.close()
