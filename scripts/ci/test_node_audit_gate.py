import datetime as dt
import json
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

import node_audit_gate as gate

TODAY = dt.date(2026, 10, 6)


def advisory(ghsa: str, package: str, severity: str, *workspaces: str) -> dict:
    return {
        "github_advisory_id": ghsa,
        "module_name": package,
        "severity": severity,
        "findings": [{"paths": [f"{w} > dep@1.0.0 > {package}@1.0.0" for w in workspaces]}],
    }


def audit(*advisories: dict) -> dict:
    return {"advisories": {str(i): a for i, a in enumerate(advisories)}, "metadata": {}}


def exception(ghsa: str, package: str, expires: dt.date) -> dict:
    return {
        "id": ghsa,
        "package": package,
        "path": "apps/mobile",
        "reason": "r",
        "expires": expires,
    }


VALID = dt.date(2027, 1, 4)
MOBILE_EXCEPTIONS = [
    exception("GHSA-86w9-cpqp-85rv", "node-forge", VALID),
    exception("GHSA-vfj7-8cjw-p6xm", "braces", VALID),
]
MOBILE_KNOWN = [
    advisory("GHSA-86w9-cpqp-85rv", "node-forge", "high", "apps/mobile"),
    advisory("GHSA-vfj7-8cjw-p6xm", "braces", "high", "apps/mobile"),
]


class WorkspaceScopeTest(unittest.TestCase):
    def test_high_in_other_workspace_is_ignored(self):
        report = audit(advisory("GHSA-aaaa", "x", "critical", "apps/pdf"))
        self.assertEqual(gate.evaluate(report, "apps/web", [], TODAY), [])

    def test_high_in_workspace_fails(self):
        report = audit(advisory("GHSA-aaaa", "x", "high", "apps/web", "apps/pdf"))
        self.assertEqual(len(gate.evaluate(report, "apps/web", [], TODAY)), 1)

    def test_moderate_is_not_gated(self):
        report = audit(advisory("GHSA-aaaa", "x", "moderate", "apps/web"))
        self.assertEqual(gate.evaluate(report, "apps/web", [], TODAY), [])


class UnscopedPathTest(unittest.TestCase):
    def test_root_path_fails_in_every_workspace(self):
        report = audit(
            {
                "github_advisory_id": "GHSA-root",
                "module_name": "x",
                "severity": "critical",
                "findings": [{"paths": [". > x@1.0.0"]}],
            }
        )
        for workspace in gate.GATED_WORKSPACES:
            errors = gate.evaluate(report, workspace, [], TODAY)
            self.assertEqual(len(errors), 1)
            self.assertIn("GHSA-root", errors[0])

    def test_packages_schema_path_fails(self):
        report = audit(advisory("GHSA-schema", "x", "high", "packages/schema"))
        self.assertEqual(len(gate.evaluate(report, "apps/web", [], TODAY)), 1)

    def test_moderate_outside_gated_workspaces_is_ignored(self):
        report = audit(advisory("GHSA-root", "x", "moderate", "."))
        self.assertEqual(gate.evaluate(report, "apps/web", [], TODAY), [])

    def test_gated_prefix_must_match_whole_segment(self):
        report = audit(advisory("GHSA-lookalike", "x", "high", "apps/web-extra"))
        self.assertEqual(len(gate.evaluate(report, "apps/web", [], TODAY)), 1)


class MissingPathsTest(unittest.TestCase):
    def test_gated_advisory_without_paths_fails_closed(self):
        report = audit({**advisory("GHSA-aaaa", "x", "high"), "findings": [{"paths": []}]})
        with self.assertRaises(SystemExit):
            gate.evaluate(report, "apps/web", [], TODAY)

    def test_moderate_without_paths_is_ignored(self):
        report = audit({**advisory("GHSA-aaaa", "x", "moderate"), "findings": [{"paths": []}]})
        self.assertEqual(gate.evaluate(report, "apps/web", [], TODAY), [])


class MobileExceptionsTest(unittest.TestCase):
    def test_only_the_two_valid_exceptions_is_green(self):
        self.assertEqual(
            gate.evaluate(audit(*MOBILE_KNOWN), "apps/mobile", MOBILE_EXCEPTIONS, TODAY), []
        )

    def test_new_high_fails(self):
        report = audit(*MOBILE_KNOWN, advisory("GHSA-new", "lodash", "high", "apps/mobile"))
        errors = gate.evaluate(report, "apps/mobile", MOBILE_EXCEPTIONS, TODAY)
        self.assertEqual(len(errors), 1)
        self.assertIn("GHSA-new", errors[0])

    def test_expired_exception_fails(self):
        expired = [
            exception("GHSA-86w9-cpqp-85rv", "node-forge", dt.date(2026, 10, 5)),
            MOBILE_EXCEPTIONS[1],
        ]
        errors = gate.evaluate(audit(*MOBILE_KNOWN), "apps/mobile", expired, TODAY)
        self.assertEqual(len(errors), 1)
        self.assertIn("abgelaufen", errors[0])

    def test_expiry_day_is_still_valid(self):
        last_day = [exception(e["id"], e["package"], TODAY) for e in MOBILE_EXCEPTIONS]
        self.assertEqual(gate.evaluate(audit(*MOBILE_KNOWN), "apps/mobile", last_day, TODAY), [])

    def test_expired_exception_without_finding_still_fails(self):
        expired = [exception("GHSA-86w9-cpqp-85rv", "node-forge", dt.date(2026, 1, 1))]
        self.assertEqual(len(gate.evaluate(audit(), "apps/mobile", expired, TODAY)), 1)


class FailClosedTest(unittest.TestCase):
    def test_invalid_audit_output_exits(self):
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as tmp:
            bad = Path(tmp) / "audit.json"
            bad.write_text('{"error": {"code": "ENOTFOUND"}}', encoding="utf-8")
            with self.assertRaises(SystemExit):
                gate.load_audit(bad)


def write_yaml(directory: Path, body: str) -> Path:
    path = directory / "exceptions.yml"
    path.write_text(textwrap.dedent(body), encoding="utf-8")
    return path


VALID_ENTRY = """\
    exceptions:
      - id: GHSA-86w9-cpqp-85rv
        package: node-forge
        path: apps/mobile
        reason: r
        expires: {expires}
    """


class LoadExceptionsTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.dir = Path(self._tmp.name)

    def test_none_path_means_no_exceptions(self):
        self.assertEqual(gate.load_exceptions(None, "apps/web"), [])

    def test_path_mismatch_exits(self):
        path = write_yaml(self.dir, VALID_ENTRY.format(expires="2027-01-04"))
        with self.assertRaises(SystemExit):
            gate.load_exceptions(path, "apps/web")

    def test_missing_required_field_exits(self):
        import yaml

        full = {
            "id": "GHSA-86w9-cpqp-85rv",
            "package": "node-forge",
            "path": "apps/mobile",
            "reason": "r",
            "expires": dt.date(2027, 1, 4),
        }
        for field in gate.REQUIRED_FIELDS:
            entry = {k: v for k, v in full.items() if k != field}
            path = write_yaml(self.dir, yaml.safe_dump({"exceptions": [entry]}))
            with self.subTest(field=field), self.assertRaises(SystemExit):
                gate.load_exceptions(path, "apps/mobile")

    def test_non_mapping_document_exits(self):
        path = write_yaml(self.dir, "- just\n- a list\n")
        with self.assertRaises(SystemExit):
            gate.load_exceptions(path, "apps/mobile")

    def test_expires_as_date_datetime_and_string(self):
        for raw in ("2027-01-04", "2027-01-04T00:00:00Z", '"2027-01-04"'):
            path = write_yaml(self.dir, VALID_ENTRY.format(expires=raw))
            entries = gate.load_exceptions(path, "apps/mobile")
            with self.subTest(raw=raw):
                self.assertEqual(gate._expiry(entries[0]), dt.date(2027, 1, 4))

    def test_datetime_expiry_compares_against_date(self):
        path = write_yaml(self.dir, VALID_ENTRY.format(expires="2026-10-05T12:00:00Z"))
        entries = gate.load_exceptions(path, "apps/mobile")
        errors = gate.evaluate(audit(), "apps/mobile", entries, TODAY)
        self.assertEqual(len(errors), 1)


class CliEndToEndTest(unittest.TestCase):
    SCRIPT = Path(gate.__file__)

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.dir = Path(self._tmp.name)

    def run_cli(self, report: dict, *extra: str) -> subprocess.CompletedProcess:
        audit_path = self.dir / "audit.json"
        audit_path.write_text(json.dumps(report), encoding="utf-8")
        return subprocess.run(
            [sys.executable, str(self.SCRIPT), "--audit-json", str(audit_path), *extra],
            capture_output=True,
            text=True,
            check=False,
        )

    def test_green_with_only_the_two_valid_exceptions(self):
        exceptions = write_yaml(
            self.dir,
            """\
            exceptions:
              - id: GHSA-86w9-cpqp-85rv
                package: node-forge
                path: apps/mobile
                reason: r
                expires: 2027-01-04
              - id: GHSA-vfj7-8cjw-p6xm
                package: braces
                path: apps/mobile
                reason: r
                expires: 2027-01-04
            """,
        )
        result = self.run_cli(
            audit(*MOBILE_KNOWN),
            "--workspace", "apps/mobile",
            "--exceptions", str(exceptions),
            "--today", "2026-10-06",
        )  # fmt: skip
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_new_finding_exits_1(self):
        result = self.run_cli(
            audit(advisory("GHSA-new", "x", "high", "apps/web")),
            "--workspace", "apps/web",
        )  # fmt: skip
        self.assertEqual(result.returncode, 1)
        self.assertIn("GHSA-new", result.stdout)

    def test_expired_exception_exits_1(self):
        exceptions = write_yaml(self.dir, VALID_ENTRY.format(expires="2026-10-05"))
        result = self.run_cli(
            audit(),
            "--workspace", "apps/mobile",
            "--exceptions", str(exceptions),
            "--today", "2026-10-06",
        )  # fmt: skip
        self.assertEqual(result.returncode, 1)
        self.assertIn("abgelaufen", result.stdout)

    def test_garbage_audit_output_exits_nonzero(self):
        result = self.run_cli({"error": "ENOTFOUND"}, "--workspace", "apps/web")
        self.assertNotEqual(result.returncode, 0)


if __name__ == "__main__":
    unittest.main()
