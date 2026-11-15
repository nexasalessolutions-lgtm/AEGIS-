import { NextRequest, NextResponse } from "next/server";
export const dynamic = "force-dynamic";
const allowed = /^(health|ready|api\/(protocols|chains|capabilities|worker\/health|protocol\/[a-zA-Z0-9._-]+(?:\/(?:contracts|state))?|contract\/inspect|scans\/protocol\/[a-zA-Z0-9._-]+|scans\/jobs(?:\/[a-f0-9-]+)?))$/;
async function forward(req:NextRequest, ctx:{params:Promise<{path:string[]}>}) {
 const {path}=await ctx.params; const joined=path.join("/");
 if(!allowed.test(joined)) return NextResponse.json({detail:"Route not allowed"},{status:404});
 const base=(process.env.AEGIS_API_URL||"").replace(/\/$/,"");
 if(!base) return NextResponse.json({detail:"AEGIS_API_URL is not configured"},{status:503});
 const upstream=base+"/"+joined+req.nextUrl.search;
 const headers=new Headers();
 const contentType=req.headers.get("content-type"); if(contentType) headers.set("content-type",contentType);
 const token=process.env.AEGIS_SCAN_TOKEN; if(token) headers.set("authorization","Bearer "+token);
 const init:RequestInit={method:req.method,headers,cache:"no-store",signal:AbortSignal.timeout(240000)};
 if(req.method!=="GET"&&req.method!=="HEAD") init.body=await req.arrayBuffer();
 try { const response=await fetch(upstream,init); const body=await response.arrayBuffer(); return new NextResponse(body,{status:response.status,headers:{"content-type":response.headers.get("content-type")||"application/json","cache-control":"no-store"}}); }
 catch(e:any){return NextResponse.json({detail:"AEGIS API unavailable",message:e?.message||"upstream failure"},{status:502});}
}
export async function GET(req:NextRequest,ctx:{params:Promise<{path:string[]}>}){return forward(req,ctx);}
export async function POST(req:NextRequest,ctx:{params:Promise<{path:string[]}>}){return forward(req,ctx);}
