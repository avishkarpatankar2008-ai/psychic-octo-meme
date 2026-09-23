import Link from "next/link";
import { Button } from "@/components/Button";
import { INTERVIEW_CATEGORIES } from "@/lib/types";

const features=[
 ["01","Adaptive by design","Every answer changes the next question. Probe, challenge, redirect or advance — automatically."],
 ["02","Grounded in you","Bring a resume and job description. ELEVORA asks about what you actually submitted, not invented experience."],
 ["03","Evidence, not vibes","Your report connects scores to answer evidence and gives you a concrete practice path."],
];

export default function LandingPage(){
 return <div className="overflow-hidden">
  <section className="relative grid-bg">
   <div className="pointer-events-none absolute left-1/2 top-[-180px] h-[520px] w-[760px] -translate-x-1/2 rounded-full bg-violet-600/15 blur-[120px]"/>
   <div className="mx-auto max-w-7xl px-5 pb-24 pt-20 lg:px-8 lg:pt-28">
    <div className="mx-auto max-w-4xl text-center">
     <div className="eyebrow">AI interview practice, rebuilt</div>
     <h1 className="mt-6 text-5xl font-semibold tracking-[-.055em] text-white sm:text-6xl lg:text-8xl">
      Practice like the<br/><span className="bg-gradient-to-r from-white via-violet-200 to-violet-400 bg-clip-text text-transparent">real interview.</span>
     </h1>
     <p className="mx-auto mt-7 max-w-2xl text-base leading-7 text-white/50 sm:text-lg">
      ELEVORA listens to your answers, adapts in real time, and shows you exactly what to improve — for roles, companies, exams and industries.
     </p>
     <div className="mt-9 flex flex-col justify-center gap-3 sm:flex-row">
      <Link href="/signup"><Button className="h-12 px-7 text-[15px]">Start practicing <span>↗</span></Button></Link>
      <Link href="/login"><Button variant="secondary" className="h-12 px-7 text-[15px]">Sign in</Button></Link>
     </div>
     <div className="mt-6 text-xs text-white/30">No fabricated scores. No scripted interviews. Just your practice data.</div>
    </div>

    <div className="mx-auto mt-16 max-w-6xl">
     <div className="glass-strong glow overflow-hidden rounded-3xl">
      <div className="flex items-center justify-between border-b border-white/[.07] px-5 py-4">
       <div className="flex items-center gap-2"><span className="h-2 w-2 rounded-full bg-emerald-400"/><span className="text-xs text-white/50">LIVE INTERVIEW</span></div>
       <div className="text-xs text-white/35">Adaptive session · 14:32</div>
      </div>
      <div className="grid min-h-[360px] lg:grid-cols-[1fr_300px]">
       <div className="p-7 sm:p-10">
        <div className="text-xs font-medium text-violet-300">QUESTION 07 / ADAPTIVE</div>
        <h2 className="mt-5 max-w-2xl text-2xl font-medium leading-9 tracking-tight text-white sm:text-3xl">
         You mentioned reducing query latency. What did you measure before the change, and how did you validate the result?
        </h2>
        <div className="mt-10 flex items-center gap-4">
         <div className="flex h-12 w-12 items-center justify-center rounded-full bg-violet-500/15 text-violet-300">●</div>
         <div className="flex-1"><div className="h-1 overflow-hidden rounded-full bg-white/10"><div className="h-full w-[68%] rounded-full bg-gradient-to-r from-violet-500 to-cyan-400"/></div><div className="mt-2 text-[11px] text-white/35">Listening · microphone ready</div></div>
        </div>
       </div>
       <div className="border-t border-white/[.07] bg-black/10 p-6 lg:border-l lg:border-t-0">
        <div className="text-[11px] uppercase tracking-[.18em] text-white/30">Session signal</div>
        <div className="mt-6 space-y-4">
         {["Technical depth","Answer relevance","Follow-up pressure"].map((x,i)=><div key={x}><div className="flex justify-between text-xs"><span className="text-white/55">{x}</span><span className="text-white/35">{["Strong","Focused","Active"][i]}</span></div><div className="mt-2 h-1 rounded-full bg-white/10"><div className="h-full rounded-full bg-violet-400" style={{width:["82%","91%","64%"][i]}}/></div></div>)}
        </div>
       </div>
      </div>
     </div>
    </div>
   </div>
  </section>

  <section className="border-y border-white/[.07] bg-[#090A12]">
   <div className="mx-auto grid max-w-7xl gap-px bg-white/[.06] px-5 lg:grid-cols-3 lg:px-8">
    {features.map(([n,t,b])=><div key={n} className="bg-[#090A12] px-2 py-12 lg:px-8"><div className="text-xs text-violet-300">{n}</div><h3 className="mt-4 text-xl font-semibold text-white">{t}</h3><p className="mt-3 max-w-sm text-sm leading-6 text-white/45">{b}</p></div>)}
   </div>
  </section>

  <section className="mx-auto max-w-7xl px-5 py-20 lg:px-8">
   <div className="max-w-2xl"><div className="eyebrow">One engine. Any target.</div><h2 className="mt-4 text-3xl font-semibold tracking-tight text-white sm:text-4xl">Prepare for the interview you actually have.</h2><p className="mt-4 text-white/45">Configure one engine for your role, exam, company, experience level and difficulty.</p></div>
   <div className="mt-8 flex flex-wrap gap-2">{INTERVIEW_CATEGORIES.map(c=><span key={c.value} className="rounded-full border border-white/[.08] bg-white/[.025] px-4 py-2 text-sm text-white/55">{c.label}</span>)}</div>
  </section>

  <section className="mx-auto max-w-7xl px-5 pb-28 lg:px-8">
   <div className="relative overflow-hidden rounded-3xl border border-violet-400/15 bg-gradient-to-br from-violet-600/15 to-cyan-500/[.04] p-8 sm:p-12">
    <div className="pointer-events-none absolute right-[-100px] top-[-160px] h-80 w-80 rounded-full bg-violet-500/15 blur-[100px]"/>
    <div className="relative max-w-2xl"><div className="eyebrow">Your next interview starts here</div><h2 className="mt-4 text-3xl font-semibold text-white sm:text-4xl">Stop rehearsing answers. Start training judgment.</h2><p className="mt-4 text-white/45">Build the skill to handle the unexpected question, not just the expected one.</p><Link href="/signup" className="mt-7 inline-block"><Button className="h-11 px-6">Create your account</Button></Link></div>
   </div>
  </section>
 </div>
}