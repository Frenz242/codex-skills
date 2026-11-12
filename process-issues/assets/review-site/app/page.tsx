"use client";
import {useEffect,useState} from "react";
type Review={pr_key:string;version:number;publication_key:string;manifest:any;observed_github:any;updated_at:string};
const api="/api/review/v1";
async function read(url:string){const r=await fetch(url);if(!r.ok)throw Error(r.status===401?"Sign in to open this private review.":"The review service is unavailable. Your GitHub PR remains authoritative.");return r.json();}
const date=(s:string)=>new Date(s).toLocaleString();
function Media({asset,publication,poster}:{asset:any;publication:string;poster?:string}){
 const [failed,setFailed]=useState(false),src=api+"/media/"+encodeURIComponent(publication)+"/"+asset.id;
 if(failed)return <p className="notice">Media unavailable. <a href={src} target="_blank" rel="noreferrer">Try opening the original</a></p>;
 return <figure>{asset.mime==="image/png"?<a href={src} target="_blank" rel="noreferrer" aria-label={"Open full-size: "+asset.caption}><img src={src} alt={asset.caption} loading="lazy" onError={()=>setFailed(true)}/></a>:
 asset.mime==="video/mp4"?<video controls playsInline preload="metadata" poster={poster} onError={()=>setFailed(true)} aria-label={asset.caption}><source src={src} type="video/mp4"/></video>:
 <a href={src} target="_blank" rel="noreferrer">Open recorded output</a>}<figcaption>{asset.caption} {asset.mime==="video/mp4"&&<a href={src} target="_blank" rel="noreferrer">Open / download clip</a>}</figcaption></figure>;
}
function Entry({review}:{review:Review}){
 const m=review.manifest,o=review.observed_github;
 const freshness=o.head_sha===null?"Freshness unknown":o.head_sha===m.revision.head_sha?"Matches head as of last check":"Stale evidence · head has changed";
 const [history,setHistory]=useState<any[]>([]),[historyError,setHistoryError]=useState(""),[showHistory,setShowHistory]=useState(false),[historyNext,setHistoryNext]=useState<string|null>(null);
 async function loadHistory(after=""){try{const d=await read(api+"/history?pr="+encodeURIComponent(review.pr_key)+(after?"&after="+encodeURIComponent(after):""));setHistory(v=>after?[...v,...d.publications]:d.publications);setHistoryNext(d.next);setShowHistory(true);}catch(e){setHistoryError((e as Error).message);}}
 return <article className="entry">
  <div className="eyebrow">PULL REQUEST #{m.pull_request.number} <span className="status">{o.state}{o.draft?" · draft":""}</span></div>
  <h1>{m.pull_request.title}</h1>
  <div className="actions"><a className="button" href={m.pull_request.url} target="_blank" rel="noreferrer">Review on GitHub ↗</a><span className={freshness.startsWith("Matches")?"fresh":"warning"}>{freshness}</span></div>
  {m.demonstration.limitation&&<p className="notice">{m.demonstration.limitation}</p>}
  <section className="summary"><h2>What changed</h2><p>{m.summary.changed}</p><h3>Why it matters</h3><p>{m.summary.why}</p><h3>What to inspect</h3><p>{m.summary.inspect}</p></section>
  <section><div className="section-title"><h2>See the change</h2><span>{m.demonstration.state}</span></div><p>{m.demonstration.scenario}</p><p className="muted">{m.demonstration.outcome}</p>
   {m.assets.length?m.assets.slice().sort((a:any,b:any)=>(a.mime==="video/mp4"?1:0)-(b.mime==="video/mp4"?1:0)).map((a:any)=><Media key={a.id} asset={a} publication={review.publication_key} poster={m.assets.find((p:any)=>p.mime==="image/png") ? api+"/media/"+encodeURIComponent(review.publication_key)+"/"+m.assets.find((p:any)=>p.mime==="image/png").id : undefined}/>):<p className="notice">{m.demonstration.kind==="nonvisual"?"Nonvisual change: inspect the recorded semantic evidence below.":"Review media is incomplete."}</p>}
  </section>
  <section><h2>Verification</h2>{m.acceptance.map((c:any,i:number)=><details key={i} open={c.state!=="verified"}><summary><span>{c.criterion}</span><strong className={c.state==="verified"?"fresh":"warning"}>{c.state}</strong></summary>
   {["automated","runtime","output","delivery"].map(k=><div key={k}><h4>{k}</h4>{c[k].length?c[k].map((e:any,j:number)=><p key={j}><b>{e.result}</b> · {e.description}{e.reason&&<span className="muted"> — {e.reason}</span>}</p>):<p className="muted">No evidence recorded in this layer.</p>}</div>)}{c.limitation&&<p className="notice">{c.limitation}</p>}
  </details>)}</section>
  <section className="provenance"><h2>Evidence & provenance</h2><p>Evidence for commit <code>{m.revision.head_sha}</code></p><p>Captured {date(m.revision.captured_at)}</p><p>Surface: {m.demonstration.surface} · Capture: {m.demonstration.capture_source}</p><p>{m.demonstration.tool}</p><p>GitHub last checked {date(o.observed_at)} · Checks: {o.checks} · Reviews: {o.reviews}</p><p className="muted">This is a recorded observation, not continuous monitoring. Viewing this page is not an approval.</p><p>{m.pull_request.issues.map((url:string)=><a key={url} href={url} target="_blank" rel="noreferrer">Issue #{url.split("/").pop()} ↗ </a>)}</p>
   <button onClick={()=>showHistory?setShowHistory(false):loadHistory()}> {showHistory?"Hide":"Show"} prior evidence</button>{historyError&&<p role="alert">{historyError}</p>}
   {showHistory&&<ul>{history.map(h=><li key={h.publication_key}>{h.manifest.revision.head_sha.slice(0,12)} · {date(h.manifest.revision.captured_at)} {h.publication_key===review.publication_key?"· displayed revision":""}<p>{h.manifest.summary.changed}</p>{h.manifest.assets.map((a:any)=><a key={a.id} href={api+"/media/"+encodeURIComponent(h.publication_key)+"/"+a.id} target="_blank" rel="noreferrer">{a.caption} ↗ </a>)}</li>)}</ul>}
   {showHistory&&historyNext&&<button onClick={()=>loadHistory(historyNext)}>Load older evidence</button>}
  </section>
 </article>;
}
export default function Home(){
 const [projects,setProjects]=useState<any[]>([]),[reviews,setReviews]=useState<Review[]>([]),[error,setError]=useState(""),[loading,setLoading]=useState(true),[location,setLocation]=useState({project:"",pr:""}),[history,setHistory]=useState(false),[next,setNext]=useState<string|null>(null);
 useEffect(()=>{const sync=()=>{const q=new URLSearchParams(window.location.search);setLocation({project:q.get("project")||"",pr:q.get("pr")||""});};sync();window.addEventListener("popstate",sync);read(api+"/projects").then(d=>setProjects(d.projects)).catch(e=>setError(e.message)).finally(()=>setLoading(false));return()=>window.removeEventListener("popstate",sync);},[]);
 useEffect(()=>{if(!location.project){setReviews([]);return;}let active=true;setLoading(true);setError("");setReviews([]);(async()=>{let cursor="";const all:Review[]=[];do{const d=await read(api+"/reviews?project="+encodeURIComponent(location.project)+(cursor?"&after="+encodeURIComponent(cursor):""));all.push(...d.reviews);cursor=d.next||"";if(!location.pr||all.some(r=>String(r.manifest.pull_request.number)===location.pr))break;}while(cursor);if(active){setReviews(all);setNext(cursor||null);}})().catch(e=>{if(active)setError(e.message);}).finally(()=>{if(active)setLoading(false);});return()=>{active=false;};},[location.project,location.pr]);
 const selected=projects.find(p=>p.project_key===location.project);
 const current=reviews.find(r=>String(r.manifest.pull_request.number)===location.pr);
 const shown=reviews.filter(r=>history||r.observed_github.state==="open"||r.observed_github.state==="unknown").sort((a,b)=>b.updated_at.localeCompare(a.updated_at));
 async function more(){try{const d=await read(api+"/reviews?project="+encodeURIComponent(location.project)+"&after="+encodeURIComponent(next||""));setReviews(v=>[...v,...d.reviews]);setNext(d.next);}catch(e){setError((e as Error).message);}}
 return <div className="shell"><header><a className="brand" href="/"> <span className="brand-mark">R</span> Review hub</a><span className="private">PRIVATE · IMPLEMENTATION EVIDENCE</span></header><nav aria-label="Breadcrumb"><a href="/">Projects</a>{selected&&<> / <a href={"?project="+encodeURIComponent(location.project)}>{selected.repository.name}</a></>}{location.pr&&<> / PR #{location.pr}</>}</nav>
 <main>{error&&<p className="notice" role="alert">{error} <a href="/signin-with-chatgpt?return_to=%2F" target="_top">Sign in</a></p>}{loading&&<p role="status">Loading review evidence…</p>}
 {!location.project&&!loading&&<><p className="eyebrow">FROM CODE TO CONFIDENCE</p><h1>Your projects.<br/><span className="muted">Changes you can inspect.</span></h1><p className="intro">See what changed, watch it work, and check the evidence before opening GitHub.</p><div className="grid">{projects.map(p=><a className="card" key={p.project_key} href={"?project="+encodeURIComponent(p.project_key)}><span className="eyebrow">{p.repository.owner}</span><h2>{p.repository.name} ↗</h2><p>{p.count} recorded {p.count===1?"review":"reviews"}</p><small>Updated {date(p.updated_at)}</small></a>)}</div>{projects.length===0&&!error&&<p className="notice">No reviews yet. An authorized process-issues run will publish evidence here once configured.</p>}</>}
 {location.project&&!location.pr&&!loading&&<><p className="eyebrow">PROJECT REVIEWS</p><h1>{selected?.repository.name||"Project"}</h1><label className="toggle"><input type="checkbox" checked={history} onChange={e=>setHistory(e.target.checked)}/> Include merged and closed history</label><div className="grid">{shown.map(r=><a className="card" key={r.pr_key} href={"?project="+encodeURIComponent(location.project)+"&pr="+r.manifest.pull_request.number}><span className="eyebrow">#{r.manifest.pull_request.number} · {r.observed_github.state}{r.observed_github.draft?" · draft":""}</span><h2>{r.manifest.pull_request.title}</h2><p>{r.manifest.summary.changed}</p><small>{r.observed_github.head_sha===null?"Freshness unknown":r.observed_github.head_sha===r.manifest.revision.head_sha?"Matches last observed head":"Stale evidence"}</small></a>)}</div>{shown.length===0&&!error&&<p className="notice">No matching reviews in this view.</p>}{next&&<button onClick={more}>Load more reviews</button>}</>}
 {location.pr&&!loading&&(current?<Entry key={current.publication_key} review={current}/>:!error&&<p className="notice">This review is not available yet.</p>)}
 </main><footer>GitHub remains the source of truth for code, checks, review and merge state.</footer></div>;
}
