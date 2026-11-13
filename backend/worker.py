import asyncio, json, os, re, shutil, stat, subprocess, tempfile, zipfile, io
from pathlib import Path, PurePosixPath
from fastapi import FastAPI, File, Header, HTTPException, UploadFile

app = FastAPI(title="AEGIS Isolated Static Analysis Worker", version="0.1.0")
TOKEN = os.getenv("AEGIS_WORKER_TOKEN", "")
MAX_ARCHIVE, MAX_EXPANDED, MAX_FILES, TIMEOUT = 20*1024*1024, 100*1024*1024, 500, 180
SCAN_LOCK = asyncio.Lock()

SUPPORTED_SOLC_VERSIONS = ("0.4.26", "0.5.17", "0.6.12", "0.7.6", "0.8.19", "0.8.20", "0.8.30")

def version_tuple(value: str):
    parts = value.split(".")
    return tuple(int(x) for x in (parts + ["0", "0"])[:3])

def pragma_accepts(expression: str, candidate: str) -> bool:
    current = version_tuple(candidate)
    for alternative in expression.split("||"):
        tokens = re.findall(r"(\^|~|>=|<=|>|<|=)?\s*(\d+\.\d+(?:\.\d+)?)", alternative)
        if not tokens:
            continue
        accepted = True
        for operator, raw in tokens:
            target = version_tuple(raw)
            if operator == "^":
                upper = (target[0] + 1, 0, 0) if target[0] else ((0, target[1] + 1, 0) if target[1] else (0, 0, target[2] + 1))
                accepted = accepted and current >= target and current < upper
            elif operator == "~":
                accepted = accepted and current >= target and current < (target[0], target[1] + 1, 0)
            elif operator == ">=":
                accepted = accepted and current >= target
            elif operator == "<=":
                accepted = accepted and current <= target
            elif operator == ">":
                accepted = accepted and current > target
            elif operator == "<":
                accepted = accepted and current < target
            else:
                accepted = accepted and current == target
        if accepted:
            return True
    return False

def choose_compiler(project: Path):
    pragmas = []
    for source in project.rglob("*.sol"):
        try:
            text = source.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        pragmas.extend(re.findall(r"pragma\s+solidity\s+([^;]+);", text))
    hint_file = project / "aegis-compiler-version.txt"
    if hint_file.is_file():
        hint = re.search(r"\d+\.\d+\.\d+", hint_file.read_text(errors="ignore"))
        if hint and hint.group(0) in SUPPORTED_SOLC_VERSIONS:
            return hint.group(0), pragmas
    for version in reversed(SUPPORTED_SOLC_VERSIONS):
        if all(pragma_accepts(expression, version) for expression in pragmas):
            return version, pragmas
    if not pragmas:
        return "0.8.30", pragmas
    return None, pragmas


@app.get("/health")
async def health():
    def version(command):
        try:
            result = subprocess.run(command, capture_output=True, text=True, timeout=8, check=False)
            return result.stdout.strip() or result.stderr.strip() or ("exit " + str(result.returncode))
        except Exception as exc:
            return "unavailable: " + str(exc)
    slither_version = await asyncio.to_thread(version, ["slither", "--version"])
    solc_version = await asyncio.to_thread(version, ["solc", "--version"])
    aderyn_version = await asyncio.to_thread(version, ["aderyn", "--version"])
    healthy = (
        not slither_version.startswith("unavailable:")
        and not solc_version.startswith("unavailable:")
        and not aderyn_version.startswith("unavailable:")
    )
    return {
        "status": "ok" if healthy else "degraded",
        "worker": "slither",
        "mode": "static-analysis-only",
        "slitherVersion": slither_version,
        "aderynVersion": aderyn_version,
        "solcVersion": solc_version,
    }

def extract_sources(data: bytes, destination: Path) -> int:
    if len(data) > MAX_ARCHIVE: raise HTTPException(413,"Archive exceeds 20 MB limit")
    try: archive=zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile as exc: raise HTTPException(400,"Upload must be a valid ZIP archive") from exc
    entries=archive.infolist()
    if len(entries)>MAX_FILES: raise HTTPException(413,"Archive contains too many files")
    if sum(x.file_size for x in entries)>MAX_EXPANDED: raise HTTPException(413,"Expanded archive exceeds 100 MB limit")
    written=0
    for item in entries:
        path=PurePosixPath(item.filename); mode=item.external_attr >> 16
        if path.is_absolute() or ".." in path.parts or stat.S_ISLNK(mode): raise HTTPException(400,"Unsafe archive path or symlink")
        if item.is_dir() or path.suffix.lower() not in {".sol",".json",".toml",".txt",".md"}: continue
        target=(destination/Path(*path.parts)).resolve()
        if destination.resolve() not in target.parents: raise HTTPException(400,"Archive path escaped extraction directory")
        target.parent.mkdir(parents=True,exist_ok=True)
        with archive.open(item) as src, target.open("wb") as dst: shutil.copyfileobj(src,dst)
        written+=1
    if not any(destination.rglob("*.sol")): raise HTTPException(400,"Archive must contain at least one Solidity source file")
    return written

def normalize_aderyn_findings(payload: dict) -> list[dict]:
    findings = []
    for severity_key, severity in (("high_issues", "High"), ("low_issues", "Low")):
        section = payload.get(severity_key) or {}
        issues = section.get("issues", []) if isinstance(section, dict) else []
        for issue in issues:
            instances = issue.get("instances") or [{}]
            for instance in instances:
                location = instance.get("contract_path") or "source location unavailable"
                if instance.get("line_no") is not None:
                    location += ":" + str(instance["line_no"])
                findings.append({
                    "id": f"ADERYN-{len(findings) + 1:04d}",
                    "check": issue.get("detector_name") or issue.get("title") or "Aderyn finding",
                    "impact": severity,
                    "confidence": "medium",
                    "description": (issue.get("title") or "Aderyn finding") + ": " + (issue.get("description") or ""),
                    "firstElement": location,
                    "engine": "Aderyn",
                })
    return findings


@app.post("/scan/slither")
async def scan_slither(file: UploadFile=File(...), authorization: str|None=Header(default=None)):
    if not TOKEN: raise HTTPException(503,"Worker token is not configured")
    if authorization != "Bearer "+TOKEN: raise HTTPException(401,"Unauthorized")
    if not file.filename or not file.filename.lower().endswith(".zip"): raise HTTPException(400,"Upload a ZIP archive")
    data=await file.read(MAX_ARCHIVE+1)
    if len(data)>MAX_ARCHIVE: raise HTTPException(413,"Archive exceeds 20 MB limit")
    async with SCAN_LOCK:
        with tempfile.TemporaryDirectory(prefix="aegis-slither-") as tmp:
            project=Path(tmp)/"project"; project.mkdir()
            extracted=extract_sources(data,project)
            compiler_version, pragmas = choose_compiler(project)
            if not compiler_version:
                raise HTTPException(
                    422,
                    "No preinstalled Solidity compiler satisfies every source pragma. "
                    + "Detected pragmas: " + "; ".join(pragmas[:20])
                    + ". Installed compilers: " + ", ".join(SUPPORTED_SOLC_VERSIONS),
                )
            scan_env = {
                "PATH": os.environ.get("PATH", "/usr/local/bin:/usr/bin:/bin"),
                "HOME": os.environ.get("HOME", "/home/worker"),
                "TMPDIR": "/tmp",
                "SOLC_VERSION": compiler_version,
            }
            try:
                proc=await asyncio.to_thread(
                    subprocess.run,
                    ["slither", ".", "--json", "-"],
                    cwd=project, capture_output=True, text=True,
                    timeout=TIMEOUT, check=False, env=scan_env,
                )
            except subprocess.TimeoutExpired as exc:
                raise HTTPException(408, "Static analysis exceeded 180 seconds") from exc
            payload = None
            decoder = json.JSONDecoder()
            for stream in (proc.stdout or "", proc.stderr or ""):
                for match in re.finditer(r"\{", stream):
                    try:
                        candidate, _ = decoder.raw_decode(stream[match.start():])
                        if isinstance(candidate, dict) and ("results" in candidate or "success" in candidate):
                            payload = candidate
                            break
                    except (ValueError, json.JSONDecodeError):
                        continue
                if payload is not None:
                    break
            if payload is None:
                diagnostics = ((proc.stderr or "") + "\n" + (proc.stdout or "")).strip()
                diagnostics = diagnostics[-6000:] if diagnostics else "Slither produced no stdout or stderr."
                raise HTTPException(
                    422,
                    "Slither could not produce a JSON report using solc "
                    + compiler_version + ". Detected pragmas: "
                    + ("; ".join(pragmas[:12]) or "none")
                    + ". Compiler diagnostics: " + diagnostics,
                )
            detectors=payload.get("results",{}).get("detectors",[])
            slither_findings=[{"id":f"SLITHER-{i+1:04d}","check":x.get("check"),"impact":x.get("impact"),"confidence":x.get("confidence"),"description":x.get("description"),"firstElement":(x.get("elements") or [{}])[0].get("source_mapping",{}).get("filename_relative"),"engine":"Slither"} for i,x in enumerate(detectors)]
            aderyn_payload = None
            aderyn_error = None
            aderyn_report_path = project / "aderyn-report.json"
            try:
                aderyn_proc = await asyncio.to_thread(
                    subprocess.run,
                    ["aderyn", "--src", ".", "--output", str(aderyn_report_path), "--skip-update-check", "."],
                    cwd=project, capture_output=True, text=True,
                    timeout=TIMEOUT, check=False, env=scan_env,
                )
                if aderyn_report_path.is_file():
                    aderyn_payload = json.loads(aderyn_report_path.read_text(encoding="utf-8"))
                else:
                    aderyn_error = ((aderyn_proc.stderr or "") + "\n" + (aderyn_proc.stdout or "")).strip()[-4000:]
                    if not aderyn_error:
                        aderyn_error = "Aderyn completed without producing its JSON report."
            except subprocess.TimeoutExpired:
                aderyn_error = "Aderyn exceeded the 180 second analysis timeout."
            except (OSError, ValueError, json.JSONDecodeError) as exc:
                aderyn_error = str(exc)[:2000]
            aderyn_findings = normalize_aderyn_findings(aderyn_payload) if aderyn_payload else []
            findings = slither_findings + aderyn_findings
            aderyn_issue_count = (aderyn_payload or {}).get("issue_count") or {}
            partial = aderyn_error is not None
            return {
                "engine": "Slither + Aderyn",
                "status": "completed_with_partial_engines" if partial else ("completed" if proc.returncode in (0,1) else "completed_with_errors"),
                "exitCode": proc.returncode,
                "compilerVersion": compiler_version,
                "detectedPragmas": pragmas,
                "sourceFiles": len(list(project.rglob("*.sol"))),
                "archiveEntriesExtracted": extracted,
                "findingCount": len(findings),
                "slitherFindingCount": len(slither_findings),
                "aderynFindingCount": len(aderyn_findings),
                "aderynIssueCount": aderyn_issue_count,
                "aderynError": aderyn_error,
                "findings": findings,
                "engines": {"slither": {"status": "completed", "findingCount": len(slither_findings)}, "aderyn": {"status": "partial" if partial else "completed", "findingCount": len(aderyn_findings), "error": aderyn_error}},
                "stderr": proc.stderr[-8000:],
                "classification": "STATIC_ANALYSIS_SIGNAL",
                "disclaimer": "Static-analysis output is a review signal, not a confirmed vulnerability or proof of live exploitability."
            }
    