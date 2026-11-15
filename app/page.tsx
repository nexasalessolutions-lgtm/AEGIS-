"use client";

import { useEffect, useMemo, useState } from "react";

type Protocol = { name:string; slug:string; category?:string; chains:string[]; tvl?:number; symbol?:string; url?:string };
type Candidate = { chain:string; address:string; role:string; confidence:string; bytecodeBytes:number; blockNumber?:number; attribution?:string; proxyAddress?:string };
type Job = { jobId:string; status:string; progress?:{stage?:string;completed?:number;total?:number}; result?:any; error?:string };

const money = (n?:number) => n == null ? "—" : n >= 1e9 ? "$"+(n/1e9).toFixed(2)+"B" : n >= 1e6 ? "$"+(n/1e6).toFixed(2)+"M" : n >= 1e3 ? "$"+(n/1e3).toFixed(1)+"K" : "$"+n.toFixed(0);
const short = (s:string) => s ? s.slice(0,8)+"…"+s.slice(-6) : "";
async function api(path:string, init?:RequestInit) {
  const r = await fetch("/api/aegis/"+path, {...init, headers:{"content-type":"application/json",...(init?.headers||{})}});
  const data = await r.json().catch(()=>({detail:"Invalid server response"}));
  if(!r.ok) throw new Error(data.detail || data.message || data.error || "Request failed ("+r.status+")");
  return data;
}

export default function Home() {
  const [protocols,setProtocols]=useState<Protocol[]>([]);
  const [query,setQuery]=useState("");
  const [chain,setChain]=useState("all");
  const [loading,setLoading]=useState(true);
  const [error,setError]=useState("");
  const [selected,setSelected]=useState<Protocol|null>(null);
  const [candidates,setCandidates]=useState<Candidate[]>([]);
  const [discovery,setDiscovery]=useState<any>(null);
  const [discovering,setDiscovering]=useState(false);
  const [contract,setContract]=useState<any>(null);
  const [selectedTarget,setSelectedTarget]=useState<Candidate|null>(null);
  const [scan,setScan]=useState<Job|null>(null);
  const [scanBusy,setScanBusy]=useState(false);
  const [tab,setTab]=useState("overview");
  const [health,setHealth]=useState<any>(null);
  const [snapshot,setSnapshot]=useState<any>(null);
  const [snapshotBusy,setSnapshotBusy]=useState(false);

  useEffect(()=>{ api("protocols?limit=2000").then(d=>setProtocols(d.items||[])).catch(e=>setError(e.message)).finally(()=>setLoading(false)); api("capabilities").then(setHealth).catch(()=>{}); },[]);
  const filtered=useMemo(()=>protocols.filter(p=>(p.name+" "+p.slug+" "+(p.category||"")).toLowerCase().includes(query.toLowerCase())&&(chain==="all"||p.chains?.some(c=>c.toLowerCase()===chain))),[protocols,query,chain]);
  const chains=useMemo(()=>Array.from(new Set(protocols.flatMap(p=>p.chains||[]))).sort(),[protocols]);

  async function openProtocol(p:Protocol){
    setSelected(p);setTab("overview");setCandidates([]);setDiscovery(null);setContract(null);setSelectedTarget(null);setScan(null);setSnapshot(null);
    setDiscovering(true);
    try {
      const [detail, discovered] = await Promise.all([api("protocol/"+encodeURIComponent(p.slug)),api("protocol/"+encodeURIComponent(p.slug)+"/contracts")]);
      setDiscovery(detail.protocol||detail);setCandidates(discovered.candidates||[]);setDiscovery({...detail.protocol,...discovered});
      setTab("contracts");
    } catch(e:any){setError(e.message);}
    finally{setDiscovering(false);}
  }
  async function loadSnapshot(){
    if(!selected)return;
    setSnapshotBusy(true);setError("");
    try{setSnapshot(await api("protocol/"+encodeURIComponent(selected.slug)+"/snapshot?limit=12"));}
    catch(e:any){setError(e.message);}
    finally{setSnapshotBusy(false);}
  }
  async function inspect(c:Candidate){
    setSelectedTarget(c);setContract(null);
    try{setContract(await api("contract/inspect?chain="+encodeURIComponent(c.chain)+"&address="+encodeURIComponent(c.address)));}
    catch(e:any){setError(e.message);}
  }
  async function startScan(){
    if(!selected)return;
    setScanBusy(true);setError("");
    try{
      const started=await api("scans/protocol/"+encodeURIComponent(selected.slug),{method:"POST",body:"{}"});
      setScan({jobId:started.jobId,status:started.status});
      setTab("scan");
    }catch(e:any){setError(e.message);}
    finally{setScanBusy(false);}
  }
  useEffect(()=>{
    if(!scan?.jobId||["completed","failed"].includes(scan.status))return;
    let cancelled=false;
    const poll=async()=>{try{const next=await api("scans/jobs/"+scan.jobId);if(!cancelled)setScan(next);}catch(e:any){if(!cancelled)setError(e.message);}};
    poll();const id=setInterval(poll,2500);return()=>{cancelled=true;clearInterval(id);};
  },[scan?.jobId,scan?.status]);

  return <main className="shell">
    <aside className="sidebar">
      <div className="brand"><div className="brandmark">A</div><div><b>AEGIS</b><small>PROTOCOL INTELLIGENCE</small></div></div>
      <div className="workspace"><div className="eyebrow">WORKSPACE</div><div className="workspacebox"><span className="pulse"/>Security Research <span className="chev">⌄</span></div></div>
      <div className="eyebrow navlabel">INTELLIGENCE</div>
      <div className="navitem active">◈ <span>Protocol directory</span></div>
      <div className="navitem">⌘ <span>Contract explorer</span></div>
      <div className="navitem">◉ <span>Security scans</span></div>
      <div className="navitem">▤ <span>Audit history</span></div>
      <div className="sidebottom"><div className="statusline"><span className="pulse"/> LIVE DATA</div><small>Read-only public-chain intelligence</small><small className="muted">AEGIS v0.3 · Research build</small></div>
    </aside>
    <section className="main">
      <header className="topbar"><div><div className="eyebrow">SECURITY OPERATIONS / PROTOCOLS</div><h1>Protocol intelligence</h1><p>Discover on-chain infrastructure, inspect verified source and run isolated static analysis.</p></div><div className="topright"><span className="livepill"><i/> DeFiLlama connected</span><span className="avatar">SR</span></div></header>
      {error&&<div className="errorbar" onClick={()=>setError("")}>{error} <b>×</b></div>}
      <div className="stats">
        <div className="stat"><span>TRACKED PROTOCOLS</span><b>{loading?"—":protocols.length.toLocaleString()}</b><small>DeFiLlama registry</small></div>
        <div className="stat"><span>CHAINS INDEXED</span><b>{chains.length||"—"}</b><small>Supported EVM networks</small></div>
        <div className="stat"><span>ON-CHAIN DISCOVERY</span><b className="green">LIVE</b><small>Adapter candidates + RPC bytecode checks</small></div>
        <div className="stat"><span>ANALYSIS MODE</span><b>STATIC</b><small>Findings require manual confirmation</small></div>
      </div>
      <div className="content">
        <section className="directory panel">
          <div className="panelhead"><div><div className="eyebrow">MARKET INTELLIGENCE</div><h2>Protocol directory</h2></div><span className="count">{filtered.length.toLocaleString()} RESULTS</span></div>
          <div className="filters"><input value={query} onChange={e=>setQuery(e.target.value)} placeholder="Search protocols, symbols, categories…"/><select value={chain} onChange={e=>setChain(e.target.value)}><option value="all">All chains</option>{chains.map(c=><option key={c} value={c.toLowerCase()}>{c}</option>)}</select></div>
          <div className="tablewrap"><table><thead><tr><th>PROTOCOL</th><th>CATEGORY</th><th>CHAINS</th><th className="right">TVL</th></tr></thead><tbody>
            {loading&&<tr><td colSpan={4} className="empty">Loading live protocol registry…</td></tr>}
            {!loading&&filtered.slice(0,250).map((p,i)=><tr key={p.slug} onClick={()=>openProtocol(p)} className={selected?.slug===p.slug?"chosen":""}><td><span className="rank">{String(i+1).padStart(2,"0")}</span><span className="protocolname">{p.name}</span><small className="slug">{p.slug}</small></td><td><span className="category">{p.category||"—"}</span></td><td><span className="chainlist">{(p.chains||[]).slice(0,3).join(" · ")}{(p.chains||[]).length>3?" +"+(p.chains.length-3):""}</span></td><td className="right tvl">{money(p.tvl)}</td></tr>)}
            {!loading&&!filtered.length&&<tr><td colSpan={4} className="empty">No protocols match this filter.</td></tr>}
          </tbody></table></div>
          <div className="tablefoot">Showing up to 250 results · Data refreshes from DeFiLlama</div>
        </section>
        <section className="detail panel">
          {!selected?<div className="placeholder"><div className="placeholdericon">⌁</div><h2>Select a protocol</h2><p>Choose any protocol from the directory to inspect its adapter references, on-chain contract candidates, proxy slots, source metadata and scan history.</p><div className="featurelist"><span>✓ Live protocol metadata</span><span>✓ On-chain bytecode verification</span><span>✓ Sourcify / Blockscout source lookup</span><span>✓ Isolated Slither static analysis</span></div></div>:<>
            <div className="detailhead"><div><div className="eyebrow">PROTOCOL / {selected.slug.toUpperCase()}</div><h2>{selected.name}</h2><p>{selected.category||"DeFi protocol"} · {selected.chains?.join(", ")}</p></div><a href={selected.url||"#"} target="_blank" rel="noreferrer">External ↗</a></div>
            <div className="detailstats"><div><small>TVL</small><b>{money(selected.tvl)}</b></div><div><small>DISCOVERED TARGETS</small><b>{discovering?"…":candidates.length}</b></div><div><small>CHAINS</small><b>{selected.chains?.length||0}</b></div></div>
            <div className="tabs">{["overview","contracts","state","scan","fork"].map(t=><button className={tab===t?"selected":""} onClick={()=>{setTab(t);if(t==="state"&&!snapshot&&!snapshotBusy)void loadSnapshot();}} key={t}>{t==="fork"?"Fork test":t==="state"?"On-chain state":t[0].toUpperCase()+t.slice(1)}</button>)}</div>
            {discovering&&<div className="loadingbox">Discovering adapter addresses and verifying live bytecode across supported chains…</div>}
            {tab==="overview"&&<div className="sectionbody"><h3>Protocol overview</h3><p className="muted">Protocol metadata and chain TVL are sourced from DeFiLlama. Address candidates are discovered from the public adapter repository and checked against public RPC endpoints.</p><div className="notice">Evidence policy: adapter references are candidates, not ownership proof. Bytecode presence confirms a contract exists at the selected address and chain, not that it is secure.</div><button className="primary" onClick={()=>setTab("contracts")}>Explore discovered contracts →</button></div>}
            {tab==="contracts"&&<div className="sectionbody"><div className="subhead"><h3>On-chain contract candidates</h3><span>{candidates.length} verified addresses</span></div>{!discovering&&!candidates.length&&<div className="emptybox">No live contract candidates were verified for this protocol. Adapter source may be unavailable or contain no deployable addresses.</div>}<div className="targetlist">{candidates.map((c,i)=><button key={c.chain+":"+c.address+":"+i} className={"target "+(selectedTarget?.address===c.address?"targetselected":"")} onClick={()=>inspect(c)}><span className="targetdot">◈</span><span className="targetmain"><b>{c.role||"contract"}</b><small>{c.chain} · {short(c.address)}</small></span><span className="targetmeta">{c.bytecodeBytes?.toLocaleString()} bytes</span><span className="arrow">→</span></button>)}</div>
              {contract&&<div className="inspect"><div className="subhead"><h3>Contract inspection</h3><span className="verified">ON-CHAIN CODE FOUND</span></div><div className="inspectgrid"><div><small>ADDRESS</small><b>{contract.address||selectedTarget?.address}</b></div><div><small>BLOCK</small><b>{contract.blockNumber||contract.block_number||"Pinned read"}</b></div><div><small>BYTECODE</small><b>{contract.bytecodeBytes||contract.bytecode_bytes||"—"} bytes</b></div><div><small>VERIFICATION</small><b>{contract.verification||contract.sourceVerification||"Lookup complete"}</b></div></div><details><summary>Raw inspection evidence</summary><pre>{JSON.stringify(contract,null,2)}</pre></details></div>}
            </div>}
            {tab==="state"&&<div className="sectionbody"><div className="subhead"><h3>Pinned on-chain snapshot</h3><span className="pill">READ ONLY</span></div><p className="muted">Each contract on a chain is inspected against the same block height for that chain. Different chains are not simultaneous. No transactions are sent.</p>{snapshotBusy&&<div className="loadingbox">Reading chain heads, bytecode, balances, proxy slots and verified source metadata…</div>}{snapshot&&<><div className="detailstats"><div><small>DISCOVERED</small><b>{snapshot.discoveredCandidates}</b></div><div><small>INSPECTED</small><b>{snapshot.targetsInspected}</b></div><div><small>LIVE CODE</small><b>{snapshot.targetsAvailable}</b></div></div><div className="inspectgrid">{Object.entries(snapshot.chainBlockNumbers||{}).map(([ch,b])=><div key={ch}><small>{ch.toUpperCase()} PINNED BLOCK</small><b>{b==null?"Unavailable":Number(b).toLocaleString()}</b></div>)}</div><div className="targetlist">{(snapshot.targets||[]).map((t:any,i:number)=><div className="target" key={t.chain+":"+t.address+":"+i}><span className="targetdot">◈</span><span className="targetmain"><b>{t.role||"Contract"} · {t.chain||"unknown chain"}</b><small>{t.address||"Address unavailable"}</small><small>{t.status==="unavailable"||t.status==="error"?t.error:(t.verification||"Source not verified")+" · "+(t.bytecodeBytes??0)+" bytecode bytes"}</small></span><span className="targetmeta">{t.hasCode?"CODE FOUND":"UNAVAILABLE"}</span></div>)}</div><div className="notice">{snapshot.warning}</div><details><summary>Full RPC and source evidence</summary><pre>{JSON.stringify(snapshot,null,2)}</pre></details></>}{!snapshotBusy&&!snapshot&&<div className="emptybox">Snapshot not loaded yet. Select this tab to query the latest read-only chain state.</div>}</div>}
            {tab==="scan"&&<div className="sectionbody"><div className="subhead"><h3>Static security analysis</h3><span className="pill">ISOLATED WORKER</span></div><p className="muted">Discovers and verifies protocol contract candidates, retrieves verified Solidity source, hashes source files, then runs Slither in an isolated worker. Optional engines are reported separately when unavailable.</p><button className="primary" disabled={scanBusy||!candidates.length} onClick={startScan}>{scanBusy?"Starting…":"Run protocol scan"}</button>{scan&&<div className="job"><div className="jobtop"><b>Scan job {scan.jobId.slice(0,8)}</b><span className={"jobstatus "+scan.status}>{scan.status.toUpperCase()}</span></div>{scan.progress&&<><p>{scan.progress.stage||"Processing"} · {scan.progress.completed||0}/{scan.progress.total||0}</p><div className="progress"><i style={{width:((scan.progress.total?100*(scan.progress.completed||0)/scan.progress.total:0))+"%"}}/></div></>}{scan.error&&<p className="error">{scan.error}</p>}{scan.result&&<><div className="detailstats"><div><small>SCANNED</small><b>{scan.result.targetsScanned}</b></div><div><small>UNAVAILABLE</small><b>{scan.result.targetsUnavailable}</b></div><div><small>FINDINGS</small><b>{scan.result.findingCount}</b></div></div><pre>{JSON.stringify(scan.result,null,2)}</pre></>}</div>}</div>}
            {tab==="fork"&&<div className="sectionbody"><h3>Fork validation</h3><div className="notice">A pinned-block fork is not an exploit confirmation by itself. A finding must have a reproducible proof-of-concept test with explicit preconditions, state changes, attacker balance delta and gas cost before it can be marked confirmed.</div><div className="emptybox">Protocol-specific exploit reproduction is not enabled in this deployment. No transactions are broadcast to live networks.</div></div>}
          </>}
        </section>
      </div>
      <footer>AEGIS · READ-ONLY ON-CHAIN INTELLIGENCE <span>Public RPC · DeFiLlama · Sourcify · Blockscout</span></footer>
    </section>
  </main>;
}
