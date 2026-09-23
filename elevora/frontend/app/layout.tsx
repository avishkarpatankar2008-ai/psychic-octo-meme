import type {Metadata} from "next";
import {Inter} from "next/font/google";
import "./globals.css";
import {AuthProvider} from "@/lib/auth-context";
import {Navbar} from "@/components/Navbar";
const inter=Inter({subsets:["latin"],variable:"--font-inter"});
export const metadata:Metadata={title:"ELEVORA — Adaptive AI Interview Practice",description:"Adaptive AI interview practice for roles, companies, exams and industries."};
export default function RootLayout({children}:{children:React.ReactNode}){
 return <html lang="en" className={inter.variable}><body className="min-h-screen font-sans"><AuthProvider><Navbar/><main>{children}</main><footer className="border-t border-white/[.07] bg-[#070812]"><div className="mx-auto flex max-w-7xl flex-col justify-between gap-2 px-5 py-7 text-xs text-white/30 sm:flex-row lg:px-8"><span>© {new Date().getFullYear()} ELEVORA</span><span>Practice the interview, not a script.</span></div></footer></AuthProvider></body></html>
}