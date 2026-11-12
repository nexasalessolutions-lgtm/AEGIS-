import os, re
from typing import Any
import httpx
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title='AEGIS Read-only Intelligence API', version='0.1.0')
app.add_middleware(CORSMiddleware, allow_origins=os.getenv('CORS_ORIGINS', '*').split(','), allow_credentials=False, allow_methods=['GET'], allow_headers=['*'])
LLAMA = 'https://api.llama.fi'
SOURCIFY = 'https://sourcify.dev/server'
CHAIN_IDS = {'ethereum':1,'optimism':10,'bsc':56,'gnosis':100,'polygon':137,'arbitrum':42161,'avalanche':43114,'base':8453}
RPCS = {'ethereum':['https://ethereum-rpc.publicnode.com','https://1rpc.io/eth'],'arbitrum':['https://arbitrum-one-rpc.publicnode.com','https://1rpc.io/arb'],'optimism':['https://optimism-rpc.publicnode.com','https://1rpc.io/op'],'base':['https://base-rpc.publicnode.com','https://1rpc.io/base'],'polygon':['https://polygon-bor-rpc.publicnode.com','https://1rpc.io/matic'],'bsc':['https://bsc-rpc.publicnode.com','https://1rpc.io/bnb'],'avalanche':['https://avalanche-c-chain-rpc.publicnode.com'],'gnosis':['https://gnosis-rpc.publicnode.com']}

def valid_address(value: str) -> str:
    if not re.fullmatch(r'0x[a-fA-F0-9]{40}', value): raise HTTPException(400, 'Invalid EVM address')
    return value

async def get_json(client: httpx.AsyncClient, url: str, **kwargs: Any):
    response = await client.get(url, **kwargs); response.raise_for_status(); return response.json()

@app.get('/health')
async def health(): return {'status':'ok','service':'aegis-api','mode':'read-only','version':'0.1.0'}

@app.get('/api/chains')
async def chains(): return [{'id':k,'label':k.title(),'chainId':CHAIN_IDS[k]} for k in RPCS]

@app.get('/api/protocols')
async def protocols(chain: str|None=None, category: str|None=None, limit: int=Query(100,ge=1,le=500)):
    try:
        async with httpx.AsyncClient(timeout=25) as client: rows = await get_json(client, f'{LLAMA}/protocols')
        items=[]
        for p in rows:
            supported=p.get('chains') or []
            if chain and chain.lower() not in [str(c).lower() for c in supported]: continue
            if category and category.lower() not in str(p.get('category','')).lower(): continue
            items.append({'name':p.get('name'),'slug':p.get('slug'),'category':p.get('category'),'chains':supported,'tvl':p.get('tvl'),'url':p.get('url'),'symbol':p.get('symbol'),'chainTvls':p.get('chainTvls',{})})
        items.sort(key=lambda x:float(x.get('tvl') or 0),reverse=True)
        return {'items':items[:limit],'count':min(len(items),limit),'source':'DefiLlama'}
    except httpx.HTTPError as exc: raise HTTPException(502, f'Protocol registry upstream error: {exc}') from exc

@app.get('/api/protocol/{slug}')
async def protocol(slug: str):
    if not re.fullmatch(r'[a-zA-Z0-9._-]{1,120}',slug): raise HTTPException(400,'Invalid protocol slug')
    try:
        async with httpx.AsyncClient(timeout=25) as client: data=await get_json(client,f'{LLAMA}/protocol/{slug}')
        return {'protocol':data,'source':'DefiLlama'}
    except httpx.HTTPStatusError as exc: raise HTTPException(exc.response.status_code,'Protocol not found upstream') from exc
    except httpx.HTTPError as exc: raise HTTPException(502,f'Protocol detail upstream error: {exc}') from exc

@app.get('/api/contract/inspect')
async def inspect_contract(chain: str,address: str):
    address=valid_address(address); key=chain.lower()
    if key not in RPCS: raise HTTPException(400,f'Unsupported chain. Supported: {", ".join(RPCS)}')
    code=None; last_error=None
    async with httpx.AsyncClient(timeout=18) as client:
        for rpc in RPCS[key]:
            try:
                response=await client.post(rpc,json={'jsonrpc':'2.0','id':1,'method':'eth_getCode','params':[address,'latest']})
                response.raise_for_status(); payload=response.json()
                if payload.get('error'): raise RuntimeError(payload['error'].get('message','RPC error'))
                code=payload.get('result'); break
            except Exception as exc: last_error=str(exc)
        if code is None: raise HTTPException(502,f'All public RPC endpoints failed: {last_error}')
        if code=='0x': raise HTTPException(404,'No contract bytecode at this address on the selected chain')
        source=None; verification='not_found'
        try:
            source=await get_json(client,f'{SOURCIFY}/v2/contract/{CHAIN_IDS[key]}/{address}',params={'fields':'all'}); verification='sourcify_match'
        except httpx.HTTPError: pass
    return {'chain':key,'chainId':CHAIN_IDS[key],'address':address,'hasCode':True,'bytecodeBytes':max(0,(len(code)-2)//2),'bytecode':code,'verifiedSource':source,'verification':verification,'evidence':{'codeMethod':'eth_getCode','blockTag':'latest','rpc':'public RPC'},'limitations':['Proxy implementation resolution is not yet performed.','Non-empty bytecode does not establish protocol ownership or vulnerability.']}