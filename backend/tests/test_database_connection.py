"""Schema initialization must work with Neon's transaction pooler."""
from unittest.mock import MagicMock
from types import SimpleNamespace

from app.db.local_store import PostgresStore


def test_schema_timeout_is_set_in_transaction_not_startup(monkeypatch):
    connection = MagicMock()
    cursor = connection.return_value.__enter__.return_value.cursor.return_value.__enter__.return_value
    monkeypatch.setattr('app.db.local_store.db_manager.sync_connection', connection)
    monkeypatch.setattr('app.db.local_store.get_settings', lambda: SimpleNamespace(database_url='synthetic-test-boundary'))
    store = PostgresStore()

    store.init_db()

    assert store._initialized
    connection.assert_called_once_with()
    assert cursor.execute.call_args_list[0].args == ("SET LOCAL statement_timeout = '15s'",)
