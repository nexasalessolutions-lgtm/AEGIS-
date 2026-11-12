import io, zipfile
from pathlib import Path
import pytest
from fastapi import HTTPException
from backend.worker import extract_sources

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
