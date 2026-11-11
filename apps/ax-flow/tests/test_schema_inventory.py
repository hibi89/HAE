"""Synthetic offline SQLite inventory: data, path, mutation and release guards."""
from __future__ import annotations

import json
from contextlib import closing
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from axflow.schema_inventory import SchemaInventoryError, inspect_offline_schema


class OfflineSchemaTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='hae-schema-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / 'synthetic.sqlite'
        with closing(sqlite3.connect(self.source)) as db, db:
            db.executescript('''
                PRAGMA foreign_keys=ON;
                CREATE TABLE customers (id INTEGER PRIMARY KEY, name TEXT NOT NULL);
                CREATE TABLE orders (id INTEGER PRIMARY KEY, customer_id INTEGER,
                    FOREIGN KEY(customer_id) REFERENCES customers(id));
                INSERT INTO customers VALUES (1, 'PRIVATE_SYNTHETIC_ROW');
                INSERT INTO orders VALUES (1, 1);
            ''')
        self.original = self.source.read_bytes()

    def test_bounded_private_default_receipt_has_no_table_or_row_names(self):
        result = inspect_offline_schema(self.source, synthetic=True)
        self.assertEqual(result['table_count'], 2)
        self.assertEqual(result['foreign_key_count'], 1)
        self.assertFalse(result['identifiers_visible'])
        self.assertEqual(result['tables'], [])
        self.assertNotIn('customers', json.dumps(result))
        self.assertNotIn('PRIVATE_SYNTHETIC_ROW', json.dumps(result))
        self.assertEqual(self.original, self.source.read_bytes())

    def test_owner_review_schema_only_no_user_rows(self):
        result = inspect_offline_schema(self.source, synthetic=True, reveal_names=True)
        self.assertEqual([x['table'] for x in result['tables']], ['customers', 'orders'])
        self.assertEqual(result['tables'][1]['foreign_keys'][0]['target_table'], 'customers')
        self.assertNotIn('PRIVATE_SYNTHETIC_ROW', json.dumps(result))
        self.assertFalse(result['dbvora_remote_verified'])
        self.assertEqual(result['release_gate'], 'HOLD')

    def test_requires_synthetic_consent_and_absolute_explicit_file(self):
        for kwargs in ({}, {'synthetic': 1}, {'synthetic': False},
                       {'synthetic': True, 'reveal_names': 1}):
            with self.subTest(kwargs=kwargs), self.assertRaises(SchemaInventoryError):
                inspect_offline_schema(self.source, **kwargs)
        with self.assertRaises(SchemaInventoryError):
            inspect_offline_schema('relative.sqlite', synthetic=True)

    def test_invalid_sqlite_file_refused(self):
        path = self.root / 'invalid.sqlite'
        path.write_bytes(b'not sqlite')
        with self.assertRaises(SchemaInventoryError):
            inspect_offline_schema(path, synthetic=True)

    def test_uncommitted_wal_and_sidecars_are_refused(self):
        sidecar = Path(str(self.source) + '-wal')
        sidecar.write_bytes(b'ACTIVE')
        with self.assertRaises(SchemaInventoryError):
            inspect_offline_schema(self.source, synthetic=True)
        sidecar.unlink()
        self.assertEqual(inspect_offline_schema(self.source, synthetic=True)['table_count'], 2)

    def test_symlink_or_hardlink_refused_when_supported(self):
        alias = self.root / 'alias.db'
        try:
            alias.symlink_to(self.source)
        except (OSError, NotImplementedError):
            self.skipTest('symlink unavailable on this host')
        with self.assertRaises(SchemaInventoryError):
            inspect_offline_schema(alias, synthetic=True)

    def test_hardlinked_source_rejected(self):
        alias = self.root / 'other.db'
        try:
            os.link(self.source, alias)
        except (OSError, NotImplementedError):
            self.skipTest('hardlink unavailable')
        with self.assertRaises(SchemaInventoryError):
            inspect_offline_schema(self.source, synthetic=True)

    def test_injected_schema_views_triggers_virtual_tables_refused(self):
        with closing(sqlite3.connect(self.source)) as db, db:
            db.execute('CREATE VIEW unsafe_view AS SELECT * FROM customers')
        with self.assertRaises(SchemaInventoryError):
            inspect_offline_schema(self.source, synthetic=True)

    def test_empty_sqlite_schema_refused(self):
        with closing(sqlite3.connect(self.root / 'empty.sqlite')) as db, db:
            pass
        with self.assertRaises(SchemaInventoryError):
            inspect_offline_schema(self.root / 'empty.sqlite', synthetic=True)

    def test_unknown_source_and_directory_refused(self):
        for path in [self.root / 'absent', self.root]:
            with self.subTest(path=path), self.assertRaises(SchemaInventoryError):
                inspect_offline_schema(path, synthetic=True)

    def test_utf8_and_quoted_identifier_only_in_review(self):
        path = self.root / 'quoted.sqlite'
        with closing(sqlite3.connect(path)) as db, db:
            db.execute('CREATE TABLE "테이블""이름" ("컬럼""이름" INTEGER)')
        default = inspect_offline_schema(path, synthetic=True)
        self.assertEqual(default['table_count'], 1)
        self.assertNotIn('테이블', json.dumps(default, ensure_ascii=False))
        reviewed = inspect_offline_schema(path, synthetic=True, reveal_names=True)
        self.assertEqual(reviewed['tables'][0]['table'], '테이블"이름')
        self.assertEqual(reviewed['tables'][0]['columns'][0]['name'], '컬럼"이름')

    def test_cli_rejects_missing_synthetic_gate_and_no_path_leak(self):
        proc = subprocess.run([sys.executable, '-m', 'axflow.schema_inventory_cli',
                               '--source', str(self.source)], capture_output=True, text=True)
        self.assertEqual(proc.returncode, 2)
        self.assertNotIn(str(self.root), proc.stderr)
        self.assertEqual(proc.stdout, '')

    def test_cli_prints_bounded_metadata_only(self):
        proc = subprocess.run([sys.executable, '-m', 'axflow.schema_inventory_cli',
                               '--source', str(self.source), '--synthetic'],
                              capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        receipt = json.loads(proc.stdout)
        self.assertEqual(receipt['table_count'], 2)
        self.assertFalse(receipt['identifiers_visible'])
        self.assertNotIn('PRIVATE_SYNTHETIC_ROW', proc.stdout)

    def test_source_replacement_detected(self):
        from axflow import schema_inventory as module
        with patch.object(module, '_sha_file', side_effect=[('0' * 64), ('1' * 64)]):
            with self.assertRaises(SchemaInventoryError):
                inspect_offline_schema(self.source, synthetic=True)


if __name__ == '__main__':
    unittest.main()
