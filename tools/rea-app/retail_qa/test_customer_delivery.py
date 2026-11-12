"""Standalone synthetic checks, independent of the frozen Gate R source manifest."""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
import warnings
from unittest import mock
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "retail"
sys.path.insert(0, str(ROOT))
import owner_delivery as owner
import package_delivery as package


def reports():
    now = {"files_indexed": 3, "source_files": 2, "dependency_edges": 1,
           "syntax_errors": 0, "skipped_paths": 1}
    old = dict(now)
    old["files_indexed"] = 2
    return {
        "source-map.json": {"schema_version": "rea-app-source-map/v1", "summary": now,
                            "files": [{"path": "customer/secret-API-123.ts"}]},
        "change-impact.json": {"schema_version": "rea-app-change-impact/v1",
                               "snapshots": {"baseline": old, "current": dict(now)},
                               "summary": {"added_files": 1, "removed_files": 0, "modified_files": 1,
                                           "added_modules": 1, "removed_modules": 0,
                                           "added_internal_dependencies": 1, "removed_internal_dependencies": 0,
                                           "added_contracts": 0, "removed_contracts": 0,
                                           "changed_contracts": 1, "syntax_errors": 0},
                               "changed_files": [{"path": "src/new.ts", "status": "added"},
                                                 {"path": "customer/secret-API-123.ts", "status": "modified"}]},
        "functional-contracts.json": {"schema_version": "rea-app-functional-contracts/v1",
                                      "summary": {"exported_callable_contracts": 1},
                                      "contracts": [{"module": "customer/secret-API-123.ts"}]},
    }


class OfflineDeliveryTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.base = Path(temp.name)
        self.bundle = self.base / "reports"
        self.bundle.mkdir()
        self.delivery = self.base / "delivery"
        self.archive = self.base / "review.zip"
        self.inputs = reports()
        self.write_inputs()

    def write_inputs(self):
        for name, data in self.inputs.items():
            (self.bundle / name).write_bytes(owner._encode(data))

    def handoff(self):
        owner.build(self.bundle, self.delivery)
        owner.verify(self.bundle, self.delivery)

    def test_owner_build_verify_and_privacy(self):
        self.handoff()
        self.assertEqual({p.name for p in self.delivery.iterdir()},
                         {"review.json", "review.html", "manifest.json"})
        output = "".join(p.read_text("utf-8") for p in self.delivery.iterdir())
        self.assertNotIn("secret-API-123", output)
        self.assertNotIn(str(self.base), output)
        self.assertNotIn("<script", output)
        self.assertIn("Content-Security-Policy", output)
        self.assertIn("HOLD_PENDING_OWNER_ACCEPTANCE", output)

    def test_reproducible_delivery_unchanged_reports(self):
        originals = {n: p.read_bytes() for n,p in ((n,self.bundle/n) for n in self.inputs)}
        self.handoff()
        first = {p.name:p.read_bytes() for p in self.delivery.iterdir()}
        other = self.base / "again"
        owner.build(self.bundle, other)
        self.assertEqual(first, {p.name:p.read_bytes() for p in other.iterdir()})
        self.assertEqual(originals, {n:(self.bundle/n).read_bytes() for n in self.inputs})

    def test_existing_destination_is_never_overwritten(self):
        self.delivery.mkdir()
        (self.delivery / "keep").write_text("original")
        with self.assertRaises(owner.DeliveryError):
            owner.build(self.bundle, self.delivery)
        self.assertEqual((self.delivery / "keep").read_text(), "original")

    def test_nested_destination_rejected(self):
        with self.assertRaises(owner.DeliveryError):
            owner.build(self.bundle, self.bundle / "nested")
        with self.assertRaises(owner.DeliveryError):
            owner.build(self.bundle, self.base)

    def test_input_tamper_rejected(self):
        self.handoff()
        self.inputs["source-map.json"]["files"].append({"path": "changed"})
        self.write_inputs()
        with self.assertRaises(owner.DeliveryError):
            owner.verify(self.bundle, self.delivery)

    def test_output_tamper_rejected(self):
        self.handoff()
        (self.delivery / "review.html").write_text("changed")
        with self.assertRaises(owner.DeliveryError):
            owner.verify(self.bundle, self.delivery)

    def test_self_consistent_forgery_rejected_against_source(self):
        self.handoff()
        forged = self.delivery / "review.json"
        forged.write_bytes(b'{"false":true}')
        manifest = json.loads((self.delivery / "manifest.json").read_text())
        manifest["delivery_sha256"]["review.json"] = owner._hash(forged.read_bytes())
        (self.delivery / "manifest.json").write_bytes(owner._encode(manifest))
        with self.assertRaises(owner.DeliveryError):
            owner.verify(self.bundle, self.delivery)

    def test_unknown_schema_rejected(self):
        self.inputs["source-map.json"]["schema_version"] = "unknown"
        self.write_inputs()
        with self.assertRaises(owner.DeliveryError):
            owner.build(self.bundle, self.delivery)

    def test_snapshot_shape_rejected(self):
        self.inputs["change-impact.json"]["snapshots"] = [1, 2]
        self.write_inputs()
        with self.assertRaises(owner.DeliveryError):
            owner.build(self.bundle, self.delivery)

    def test_snapshot_count_mismatch_rejected(self):
        self.inputs["source-map.json"]["summary"]["files_indexed"] = 999
        self.write_inputs()
        with self.assertRaises(owner.DeliveryError):
            owner.build(self.bundle, self.delivery)

    def test_syntax_error_hold(self):
        s=self.inputs["source-map.json"]["summary"]
        i=self.inputs["change-impact.json"]
        s["syntax_errors"] = 1
        i["snapshots"]["current"]["syntax_errors"] = 1
        i["summary"]["syntax_errors"] = 1
        self.write_inputs()
        with self.assertRaises(owner.DeliveryError):
            owner.build(self.bundle, self.delivery)

    def test_boolean_count_rejected(self):
        self.inputs["source-map.json"]["summary"]["files_indexed"] = True
        self.inputs["change-impact.json"]["snapshots"]["current"]["files_indexed"] = True
        self.write_inputs()
        with self.assertRaises(owner.DeliveryError):
            owner.build(self.bundle, self.delivery)

    def test_size_limit_rejected(self):
        (self.bundle/"source-map.json").write_bytes(b" " * (owner.MAX_JSON_BYTES + 1))
        with self.assertRaises(owner.DeliveryError):
            owner.build(self.bundle, self.delivery)

    def test_symlinked_input_file_rejected(self):
        source = self.bundle/"source-map.json"
        target = self.base/"outside.json"
        target.write_bytes(source.read_bytes())
        source.unlink()
        try:
            source.symlink_to(target)
        except (OSError, NotImplementedError):
            self.skipTest("host disallows symlinks")
        with self.assertRaises(owner.DeliveryError):
            owner.build(self.bundle, self.delivery)

    def test_cli_build_verify_and_hold(self):
        cmd=[sys.executable,str(ROOT/"owner_delivery.py")]
        for mode,expected in (("build",0),("verify",0),("build",2)):
            r=subprocess.run(cmd+[mode,"--bundle",str(self.bundle),"--delivery",str(self.delivery)],
                             text=True,capture_output=True)
            self.assertEqual(r.returncode,expected,r.stderr)

    def test_zip_roundtrip_and_reproducible_bytes(self):
        self.handoff()
        package.pack(self.bundle,self.delivery,self.archive)
        package.verify_zip(self.archive,self.bundle)
        package.verify_zip(self.archive)
        other=self.base/"second.zip"
        package.pack(self.bundle,self.delivery,other)
        self.assertEqual(self.archive.read_bytes(),other.read_bytes())
        with zipfile.ZipFile(self.archive) as z:
            self.assertEqual(tuple(z.namelist()),package.ZIP_NAMES)
            self.assertNotIn(b"secret-API-123",b"".join(z.read(n) for n in z.namelist()))

    def test_zip_overwrite_rejected(self):
        self.handoff()
        self.archive.write_bytes(b"keep")
        with self.assertRaises(owner.DeliveryError):
            package.pack(self.bundle,self.delivery,self.archive)
        self.assertEqual(self.archive.read_bytes(),b"keep")

    def test_modified_report_blocks_zip(self):
        self.handoff()
        (self.delivery/"review.json").write_text("bad")
        with self.assertRaises(owner.DeliveryError):
            package.pack(self.bundle,self.delivery,self.archive)

    def test_zip_corruption_rejected(self):
        self.handoff();package.pack(self.bundle,self.delivery,self.archive)
        self.archive.write_bytes(self.archive.read_bytes()[:120])
        with self.assertRaises(owner.DeliveryError):
            package.verify_zip(self.archive)

    def test_pack_rechecks_bytes_after_owner_preflight(self):
        self.handoff()
        original_reader = owner._regular_file
        calls = 0
        def swapped_read(path, limit=owner.MAX_JSON_BYTES):
            nonlocal calls
            result = original_reader(path, limit)
            if path == self.delivery / "review.html":
                calls += 1
                if calls == 2:
                    return result + b"<!-- concurrent modification -->"
            return result
        with mock.patch.object(owner, "_regular_file", side_effect=swapped_read):
            with self.assertRaises(owner.DeliveryError):
                package.pack(self.bundle, self.delivery, self.archive)
        self.assertFalse(self.archive.exists())

    def test_p53_extended_summary_schema_roundtrip(self):
        now = self.inputs["source-map.json"]["summary"]
        now.update(packages=1, internal_edges=1, external_edges=0,
                   exports=1, call_sites=2, file_accesses=0,
                   function_contracts=1, resolved_call_edges=0,
                   value_flow_edges=0, diagnostics=0)
        impact = self.inputs["change-impact.json"]
        impact["snapshots"]["current"] = dict(now)
        impact["snapshots"]["baseline"] = {**now, "files_indexed": 2}
        impact["summary"].update(direct_dependent_records=0,
            transitive_dependent_records=0, impacted_entrypoint_records=0,
            module_package_changes=0, added_packages=0,
            removed_packages=0, changed_packages=0)
        self.inputs["source-map.json"].update(tool_version="0.3.0", parser="babel", limits={"max_files":5000})
        self.inputs["functional-contracts.json"].update(
            source_map_schema="rea-app-source-map/v1", assurance="static_syntax_evidence_only")
        self.write_inputs()
        self.handoff()
        package.pack(self.bundle, self.delivery, self.archive)
        package.verify_zip(self.archive, self.bundle)
        self.assertEqual(json.loads((self.delivery / "review.json").read_text())
            ["counts"]["files_indexed"], 3)

    def test_zip_hidden_trailing_payload_rejected(self):
        self.handoff(); package.pack(self.bundle, self.delivery, self.archive)
        with self.archive.open("ab") as handle:
            handle.write(b"\nFORBIDDEN_SECRET_OUTSIDE_ZIP_CENTRAL_DIRECTORY\n")
        with self.assertRaises(owner.DeliveryError):
            package.verify_zip(self.archive, self.bundle)
        with self.assertRaises(owner.DeliveryError):
            package.verify_zip(self.archive)

    def test_zip_unexpected_path_rejected(self):
        self.handoff();package.pack(self.bundle,self.delivery,self.archive)
        with zipfile.ZipFile(self.archive,"a") as z:
            z.writestr("../../outside","leak")
        with self.assertRaises(owner.DeliveryError):
            package.verify_zip(self.archive)

    def test_zip_duplicate_name_rejected(self):
        self.handoff();package.pack(self.bundle,self.delivery,self.archive)
        with zipfile.ZipFile(self.archive,"a") as z, warnings.catch_warnings():
            warnings.simplefilter("ignore",UserWarning)
            z.writestr("review.json","different")
        with self.assertRaises(owner.DeliveryError):
            package.verify_zip(self.archive)

    def test_zip_modified_bundle_fails_owner_check(self):
        self.handoff();package.pack(self.bundle,self.delivery,self.archive)
        self.inputs["source-map.json"]["files"].append({"path":"changed"})
        self.write_inputs()
        with self.assertRaises(owner.DeliveryError):
            package.verify_zip(self.archive,self.bundle)

    def test_zip_cli_pack_verify(self):
        self.handoff()
        cmd=[sys.executable,str(ROOT/"package_delivery.py")]
        a=subprocess.run(cmd+["pack","--bundle",str(self.bundle),"--delivery",str(self.delivery),
                              "--archive",str(self.archive)],capture_output=True,text=True)
        self.assertEqual(a.returncode,0,a.stderr)
        b=subprocess.run(cmd+["verify-zip","--bundle",str(self.bundle),
                              "--archive",str(self.archive)],capture_output=True,text=True)
        self.assertEqual(b.returncode,0,b.stderr)

    def test_delivery_extra_file_blocks_owner_verification(self):
        self.handoff()
        (self.delivery / "unexpected.txt").write_text("unapproved")
        with self.assertRaises(owner.DeliveryError):
            owner.verify(self.bundle, self.delivery)
        with self.assertRaises(owner.DeliveryError):
            package.pack(self.bundle, self.delivery, self.archive)

    def test_duplicate_report_json_key_rejected(self):
        path = self.bundle / "source-map.json"
        data = path.read_bytes()
        path.write_bytes(data.replace(b'"schema_version":', b'"schema_version":"fake","schema_version":', 1))
        with self.assertRaises(owner.DeliveryError):
            owner.build(self.bundle, self.delivery)

    def test_unsigned_zip_html_mismatch_rejected(self):
        self.handoff(); package.pack(self.bundle, self.delivery, self.archive)
        with zipfile.ZipFile(self.archive) as z:
            data = {name: z.read(name) for name in package.ZIP_NAMES}
        data["review.html"] = data["review.html"].replace(b"<!doctype html>", b"<!doctype html><!-- forged -->")
        receipt = owner._parse_json_strict(data["manifest.json"])
        receipt["delivery_sha256"]["review.html"] = owner._hash(data["review.html"])
        data["manifest.json"] = owner._encode(receipt)
        with zipfile.ZipFile(self.archive, "w") as z:
            for name in package.ZIP_NAMES:
                z.writestr(name, data[name])
        with self.assertRaises(owner.DeliveryError):
            package.verify_zip(self.archive)

    def test_unsigned_zip_release_hold_cannot_be_changed(self):
        self.handoff(); package.pack(self.bundle, self.delivery, self.archive)
        with zipfile.ZipFile(self.archive) as z:
            data = {name: z.read(name) for name in package.ZIP_NAMES}
        review = owner._parse_json_strict(data["review.json"])
        review["customer_release"] = "APPROVED"
        data["review.json"] = owner._encode(review)
        data["review.html"] = owner._html(review)
        receipt = owner._parse_json_strict(data["manifest.json"])
        for name in owner.ARTIFACTS:
            receipt["delivery_sha256"][name] = owner._hash(data[name])
        data["manifest.json"] = owner._encode(receipt)
        with zipfile.ZipFile(self.archive, "w") as z:
            for name in package.ZIP_NAMES:
                z.writestr(name, data[name])
        with self.assertRaises(owner.DeliveryError):
            package.verify_zip(self.archive)

    def test_unsigned_zip_bad_source_digest_format_rejected(self):
        self.handoff(); package.pack(self.bundle, self.delivery, self.archive)
        with zipfile.ZipFile(self.archive) as z:
            data = {name: z.read(name) for name in package.ZIP_NAMES}
        receipt = owner._parse_json_strict(data["manifest.json"])
        receipt["bundle_sha256"]["source-map.json"] = "not-a-sha256"
        data["manifest.json"] = owner._encode(receipt)
        with zipfile.ZipFile(self.archive, "w") as z:
            for name in package.ZIP_NAMES:
                z.writestr(name, data[name])
        with self.assertRaises(owner.DeliveryError):
            package.verify_zip(self.archive)

    def test_unsigned_zip_negative_count_rejected(self):
        self.handoff(); package.pack(self.bundle, self.delivery, self.archive)
        with zipfile.ZipFile(self.archive) as z:
            data = {name: z.read(name) for name in package.ZIP_NAMES}
        review = owner._parse_json_strict(data["review.json"])
        review["counts"]["files_indexed"] = -1
        data["review.json"] = owner._encode(review)
        data["review.html"] = owner._html(review)
        receipt = owner._parse_json_strict(data["manifest.json"])
        for name in owner.ARTIFACTS:
            receipt["delivery_sha256"][name] = owner._hash(data[name])
        data["manifest.json"] = owner._encode(receipt)
        with zipfile.ZipFile(self.archive, "w") as z:
            for name in package.ZIP_NAMES:
                z.writestr(name, data[name])
        with self.assertRaises(owner.DeliveryError):
            package.verify_zip(self.archive)


if __name__ == "__main__":
    unittest.main()
