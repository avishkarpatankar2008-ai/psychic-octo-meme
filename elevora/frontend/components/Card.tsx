import { HTMLAttributes } from "react";
export function Card({className="",children,...props}:HTMLAttributes<HTMLDivElement>){
 return <div className={`rounded-2xl border border-white/[0.08] bg-white/[0.035] p-6 shadow-soft backdrop-blur-xl ${className}`} {...props}>{children}</div>
}
