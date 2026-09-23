"use client";
import Link from "next/link";
import {useEffect,useMemo,useState} from "react";
import {Button} from "@/components/Button";
import {Card} from "@/components/Card";
import {ProtectedRoute} from "@/components/ProtectedRoute";
import {interviewsApi} from "@/lib/api";
import {useAuth} from "@/lib/auth-context";
import {INTERVIEW_CATEGORIES,type Interview} from "@/lib/types";

function label(v:string){return INTERVIEW_CATEGORIES.find(c=>c.value===v)?.label??v}
function status(v:Interview["status"]){return v==="completed"?"Completed":v==="in_progress"?"In progress":v==="draft"?"Not started":"Abandoned"}

function Dashboard(){
 const {user}=useAuth(); const [items,setItems]=useState<Interview[]>([]); const [loading,setLoading]=useState(true); const [error,setError]=useState<string|null>(null);
 useEffect(()=>{interviewsApi.list().then(setItems).catch(()=>setError("We couldn't load your interviews. Refresh to try again.")).finally(()=>setLoading(false))},[]);
 const completed=useMemo(()=>items.filter(i=>i.status==="completed"),[items]);
 const active=useMemo(()=>items.filter(i=>i.status==="in_progress"||i.status==="draft"),[items]);
 return <div className="min-h-[calc(100vh-64px)]">
  <div className="mx-auto max-w-7xl px-5 py-8 lg:px-8 lg:py-10">
   <div className="flex flex-col justify-between gap-5 sm:flex-row sm:items-end">
    <div><div className="eyebrow">Workspace</div><h1 className="mt-2 text-3xl font-semibold tracking-tight text-white">Good to see you, {user?.name?.split(" ")[0] || "there"}.</h1><p className="mt-2 text-sm text-white/40">Your practice history, without the noise.</p></div>
    <Link href="/interviews/new"><Button className="h-11 px-5">+ New interview</Button></Link>
   </div>

   <div className="mt-8 grid gap-3 sm:grid-cols-3">
    {[["Interviews",items.length,"Total sessions"],["Completed",completed.length,"Finished sessions"],["In progress",active.length,"Sessions to continue"]].map(([a,b,c])=><Card key={String(a)} className="p-5"><div className="text-xs text-white/35">{a}</div><div className="mt-2 text-3xl font-semibold tracking-tight text-white">{loading?"—":b}</div><div className="mt-1 text-xs text-white/30">{c}</div></Card>)}
   </div>

   <div className="mt-8 grid gap-5 lg:grid-cols-[1fr_340px]">
    <Card className="min-h-[360px]">
     <div className="flex items-center justify-between"><div><div className="text-sm font-semibold text-white">Your interviews</div><div className="mt-1 text-xs text-white/35">Every session you create appears here.</div></div><Link href="/interviews/new" className="text-xs font-medium text-violet-300 hover:text-violet-200">Start practice →</Link></div>
     {error&&<div className="mt-8 rounded-xl border border-red-400/15 bg-red-400/5 p-4 text-sm text-red-300">{error}</div>}
     {loading&&<div className="mt-8 space-y-3">{[1,2,3].map(i=><div key={i} className="h-20 animate-pulse rounded-xl bg-white/[.04]"/>)}</div>}
     {!loading&&!error&&items.length===0&&<div className="flex min-h-[270px] flex-col items-center justify-center text-center"><div className="grid h-14 w-14 place-items-center rounded-2xl border border-white/10 bg-white/[.04] text-xl text-violet-300">↗</div><h3 className="mt-5 font-semibold text-white">Your practice history is empty</h3><p className="mt-2 max-w-sm text-sm leading-6 text-white/35">Create your first interview and ELEVORA will start building your real performance history.</p><Link href="/interviews/new" className="mt-5"><Button>Start first interview</Button></Link></div>}
     {!loading&&!error&&items.length>0&&<div className="mt-6 space-y-2">{items.map(i=><div key={i.id} className="flex flex-col gap-4 rounded-xl border border-white/[.06] bg-white/[.02] p-4 transition hover:border-white/[.12] sm:flex-row sm:items-center sm:justify-between"><div><div className="font-medium text-white">{label(i.category)}{i.role?` · ${i.role}`:""}</div><div className="mt-1 text-xs text-white/35">{i.difficulty} · {i.durationMinutes} min · {status(i.status)}</div></div><div className="flex gap-2"><Link href={`/interviews/${i.id}`}><Button variant="secondary" className="px-3 py-2">{i.status==="completed"||i.status==="abandoned"?"View":"Continue"}</Button></Link>{i.status==="completed"&&<Link href={`/results/${i.id}`}><Button variant="ghost" className="px-3 py-2">Report</Button></Link>}</div></div>)}</div>}
    </Card>
    <Card className="h-fit">
     <div className="text-sm font-semibold text-white">Practice loop</div><div className="mt-1 text-xs text-white/35">The product gets better with actual sessions.</div>
     <div className="mt-6 space-y-5">{[["01","Configure","Choose target, difficulty and duration."],["02","Interview","Answer naturally with voice or text."],["03","Review","Use evidence-backed feedback to practice again."]].map(([n,t,b])=><div key={n} className="flex gap-3"><span className="text-xs font-semibold text-violet-300">{n}</span><div><div className="text-sm font-medium text-white">{t}</div><div className="mt-1 text-xs leading-5 text-white/35">{b}</div></div></div>)}</div>
    </Card>
   </div>
  </div>
 </div>
}
export default function DashboardPage(){return <ProtectedRoute><Dashboard/></ProtectedRoute>}
