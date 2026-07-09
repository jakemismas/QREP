"""KNOWN_ISSUES sweep as a permanent guard (S7, issue #47).

Every xfail marker in the suite must carry a KNOWN_ISSUES reference in its
reason - the repo's only honest escape for an unreachable criterion. The
sprint 2 protocol also allowed vitest/Playwright equivalents (test.fails);
those are audited by the same rule below.
"""

from pathlib import Path

TESTS_DIR = Path(__file__).parent
WEB_SRC = TESTS_DIR.parent / "web"


def test_every_python_xfail_references_known_issues():
    offenders = []
    for path in TESTS_DIR.glob("*.py"):
        if path.name == "test_known_issues_audit.py":
            continue
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if "xfail(" in line and "KNOWN_ISSUES" not in line:
                offenders.append(f"{path.name}:{number}: {line.strip()}")
    assert offenders == [], f"xfail without a KNOWN_ISSUES reference: {offenders}"


def test_every_web_test_fails_references_known_issues():
    offenders = []
    for pattern in ("src/**/*.test.ts", "e2e/*.ts"):
        for path in WEB_SRC.glob(pattern):
            for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                if "test.fails" in line and "KNOWN_ISSUES" not in line:
                    offenders.append(f"{path.name}:{number}: {line.strip()}")
    assert offenders == [], f"test.fails without a KNOWN_ISSUES reference: {offenders}"
