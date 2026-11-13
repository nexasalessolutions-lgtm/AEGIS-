import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import io, zipfile
from pathlib import Path
import pytest
from fastapi import HTTPException
from worker import extract_sources

def make_zip(entries):
    buf=io.BytesIO()
    with zipfile.ZipFile(buf,"w") as z:
        for name,data in entries.items(): z.writestr(name,data)
    return buf.getvalue()

def test_extracts_solidity_sources(tmp_path):
    count=extract_sources(make_zip({"src/Token.sol":"pragma solidity ^0.8.0; contract Token {}","README.md":"docs"}),tmp_path)
    assert count==2
    assert (tmp_path/"src/Token.sol").exists()

def test_rejects_zip_slip(tmp_path):
    with pytest.raises(HTTPException):
        extract_sources(make_zip({"../escape.sol":"contract X {}"}),tmp_path)

def test_requires_solidity_file(tmp_path):
    with pytest.raises(HTTPException):
        extract_sources(make_zip({"README.md":"not solidity"}),tmp_path)


def test_compiler_selection_respects_solidity_pragma_ranges(tmp_path):
    from worker import choose_compiler

    (tmp_path / "A.sol").write_text("pragma solidity ^0.8.20; contract A {}")
    assert choose_compiler(tmp_path)[0] == "0.8.30"


def test_compiler_selection_supports_legacy_exact_pragmas(tmp_path):
    from worker import choose_compiler

    (tmp_path / "Legacy.sol").write_text("pragma solidity 0.5.17; contract Legacy {}")
    assert choose_compiler(tmp_path)[0] == "0.5.17"


def test_compiler_selection_reports_unavailable_exact_version(tmp_path):
    from worker import choose_compiler

    (tmp_path / "Future.sol").write_text("pragma solidity 0.8.21; contract Future {}")
    version, pragmas = choose_compiler(tmp_path)
    assert version is None
    assert pragmas == ["0.8.21"]


def test_compiler_hint_from_verified_metadata_is_used(tmp_path):
    from worker import choose_compiler

    (tmp_path / "A.sol").write_text("pragma solidity 0.8.19; contract A {}")
    (tmp_path / "aegis-compiler-version.txt").write_text("0.8.19")
    assert choose_compiler(tmp_path)[0] == "0.8.19"


def test_normalize_aderyn_findings_preserves_severity_and_source_location():
    from worker import normalize_aderyn_findings

    payload = {
        "high_issues": {"issues": [{
            "title": "Unchecked delegatecall",
            "description": "A delegatecall target is not validated.",
            "detector_name": "delegate-call-unchecked-address",
            "instances": [{"contract_path": "src/Vault.sol", "line_no": 42}],
        }]},
        "low_issues": {"issues": [{
            "title": "Unindexed event",
            "description": "An event parameter is not indexed.",
            "detector_name": "unindexed-events",
            "instances": [{"contract_path": "src/Vault.sol", "line_no": 88}],
        }]},
    }
    findings = normalize_aderyn_findings(payload)
    assert len(findings) == 2
    assert findings[0]["impact"] == "High"
    assert findings[0]["firstElement"] == "src/Vault.sol:42"
    assert findings[1]["impact"] == "Low"
    assert findings[1]["engine"] == "Aderyn"
