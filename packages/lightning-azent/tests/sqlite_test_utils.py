"""SQLite test connections that always close Windows file handles.

The sqlite3 connection context manager commits/rolls back but does not close
its connection. TemporaryDirectory cleanup on Windows can therefore fail with
WinError 32. This helper preserves transaction semantics and closes reliably.
"""
from __future__ import annotations

from contextlib import contextmanager
import sqlite3


@contextmanager
def sqlite_connection(*args, **kwargs):
    connection = sqlite3.connect(*args, **kwargs)
    try:
        yield connection
        connection.commit()
    except BaseException:
        connection.rollback()
        raise
    finally:
        connection.close()
