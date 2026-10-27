from pathlib import Path
import json
import sqlite3
import tempfile
import unittest
from lightning_azent.runlog import RunLogError, inspect_completed_business_receipts

class ReceiptTests(unittest.TestCase):
    def setUp(self):
        t = tempfile.TemporaryDirectory()
        self.addCleanup(t.cleanup)
        self.root = Path(t.name)
        self.state=self.root/'state.sqlite'
        self.business=self.root/'business.sqlite'
        with sqlite3.connect(self.state) as con:
            con.execute('CREATE TABLE steps(run_id TEXT, step_id TEXT, status TEXT, output_json TEXT)')
        with sqlite3.connect(self.business) as con:
            con.execute('CREATE TABLE records(run_id TEXT, step_id TEXT,payload_json TEXT)')
            con.execute('CREATE TABLE csv_records(run_id TEXT,import_step_id TEXT,row_number INTEGER,payload_json TEXT)')
        self.run_id='SyntheticRun'
    def step(self,op):
        return {'steps':[{'id':'Save', 'op':op}]}
    def receipt(self, status, obj):
        with sqlite3.connect(self.state) as con:
            con.execute('INSERT INTO steps VALUES (?,?,?,?)',(self.run_id,'Save',status,json.dumps(obj)))
    def test_put_present(self):
        self.receipt('completed',{'stored_by':'Save'})
        with sqlite3.connect(self.business) as con: con.execute('INSERT INTO records VALUES (?,?,?)',(self.run_id,'Save','{}'))
        inspect_completed_business_receipts(self.state,self.business,self.run_id,self.step('sqlite_put'))
    def test_put_missing(self):
        self.receipt('completed',{'stored_by':'Save'})
        with self.assertRaisesRegex(RunLogError, 'missing'):
            inspect_completed_business_receipts(self.state,self.business,self.run_id,self.step('sqlite_put'))
    def test_incomplete_put_absence_allowed(self):
        self.receipt('failed',None)
        inspect_completed_business_receipts(self.state,self.business,self.run_id,self.step('sqlite_put'))
    def test_import_two_then_one_rejected(self):
        self.receipt('completed',{'imported_rows':2})
        with sqlite3.connect(self.business) as con:
            con.executemany('INSERT INTO csv_records VALUES (?,?,?,?)',[(self.run_id,'Save',1,'{}'),(self.run_id,'Save',2,'{}')])
        inspect_completed_business_receipts(self.state,self.business,self.run_id,self.step('sqlite_import_csv'))
        with sqlite3.connect(self.business) as con: con.execute('DELETE FROM csv_records WHERE row_number=2')
        with self.assertRaisesRegex(RunLogError, 'inconsistent'):
            inspect_completed_business_receipts(self.state,self.business,self.run_id,self.step('sqlite_import_csv'))
    def test_zero_import_valid(self):
        self.receipt('completed',{'imported_rows':0})
        inspect_completed_business_receipts(self.state,self.business,self.run_id,self.step('sqlite_import_csv'))
    def test_bad_import_receipt_fails_closed(self):
        self.receipt('completed',{'imported_rows':'2'})
        with self.assertRaisesRegex(RunLogError, 'invalid'):
            inspect_completed_business_receipts(self.state,self.business,self.run_id,self.step('sqlite_import_csv'))

if __name__=='__main__':unittest.main()
