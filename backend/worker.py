import asyncio, json, os, shutil, stat, subprocess, tempfile, zipfile, io
from pathlib import Path, PurePosixPath
from fastapi import FastAPI, File, Header, HTTPException, UploadFile

app = FastAPI(title="AEGIS Isolated Static Analysis Worker", version="0.1.0")
TOKEN = os.getenv("AEGIS_WORKER_TOKEN", "")
MAX_ARCHIVE, MAX_EXPANDED, MAX_FILES, TIMEOUT = 20*1024*1024, 100*1024*1024, 500, 180

@app.get("/health")
async def health():
    return {"status":"ok","worker":"slither","mode":"static-analysis-only"}

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

@app.post("/scan/slither")
async def scan_slither(file: UploadFile=File(...), authorization: str|None=Header(default=None)):
    if not TOKEN: raise HTTPException(503,"Worker token is not configured")
    if authorization != "Bearer "+TOKEN: raise HTTPException(401,"Unauthorized")
    if not file.filename or not file.filename.lower().endswith(".zip"): raise HTTPException(400,"Upload a ZIP archive")
    data=await file.read(MAX_ARCHIVE+1)
    if len(data)>MAX_ARCHIVE: raise HTTPException(413,"Archive exceeds 20 MB limit")
    with tempfile.TemporaryDirectory(prefix="aegis-slither-") as tmp:
        project=Path(tmp)/"project"; project.mkdir()
        extracted=extract_sources(data,project)
        try:
            proc=await asyncio.to_thread(subprocess.run,["slither",".","--json","-"],cwd=project,capture_output=True,text=True,timeout=TIMEOUT,check=False,env={"PATH":os.environ.get("PATH","/usr/local/bin:/usr/bin:/bin"),"HOME":"/tmp"})
        except subprocess.TimeoutExpired as exc: raise HTTPException(408,"Static analysis exceeded 180 seconds") from exc
        payload=None
        for candidate in (proc.stdout,proc.stderr):
            try: payload=json.loads(candidate); break
            except Exception: pass
        if payload is None: raise HTTPException(422,"Slither returned no parseable JSON; check compiler compatibility")
        detectors=payload.get("results",{}).get("detectors",[])
        findings=[{"id":f"SLITHER-{i+1:04d}","check":x.get("check"),"impact":x.get("impact"),"confidence":x.get("confidence"),"description":x.get("description"),"firstElement":(x.get("elements") or [{}])[0].get("source_mapping",{}).get("filename_relative")} for i,x in enumerate(detectors)]
        return {"engine":"Slither","status":"completed" if proc.returncode in (0,1) else "completed_with_errors","exitCode":proc.returncode,"sourceFiles":len(list(project.rglob("*.sol"))),"archiveEntriesExtracted":extracted,"findingCount":len(findings),"findings":findings,"stderr":proc.stderr[-8000:],"classification":"STATIC_ANALYSIS_SIGNAL","disclaimer":"Static-analysis output is a review signal, not a confirmed vulnerability or proof of live exploitability."}
