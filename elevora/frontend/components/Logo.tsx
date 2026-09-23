export function Logo({className=""}:{className?:string}){
 return <span className={`inline-flex items-center gap-2.5 ${className}`}>
  <span className="grid h-8 w-8 place-items-center rounded-[10px] bg-gradient-to-br from-violet-400 via-violet-600 to-indigo-700 shadow-[0_8px_30px_rgba(124,92,255,.3)]">
   <svg width="18" height="18" viewBox="0 0 24 24" fill="none"><path d="M5 17 11.5 6l3 6 4.5-8" stroke="white" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round"/><circle cx="19" cy="4" r="2" fill="white"/></svg>
  </span>
  <span className="text-[18px] font-bold tracking-[-.03em] text-white">ELEVORA</span>
 </span>
}