import datetime as dt
import unittest

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
    return {"id": ghsa, "package": package, "path": "apps/mobile", "reason": "r", "expires": expires}


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


class MobileExceptionsTest(unittest.TestCase):
    def test_only_the_two_valid_exceptions_is_green(self):
        self.assertEqual(gate.evaluate(audit(*MOBILE_KNOWN), "apps/mobile", MOBILE_EXCEPTIONS, TODAY), [])

    def test_new_high_fails(self):
        report = audit(*MOBILE_KNOWN, advisory("GHSA-new", "lodash", "high", "apps/mobile"))
        errors = gate.evaluate(report, "apps/mobile", MOBILE_EXCEPTIONS, TODAY)
        self.assertEqual(len(errors), 1)
        self.assertIn("GHSA-new", errors[0])

    def test_expired_exception_fails(self):
        expired = [exception("GHSA-86w9-cpqp-85rv", "node-forge", dt.date(2026, 10, 5)), MOBILE_EXCEPTIONS[1]]
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


if __name__ == "__main__":
    unittest.main()
