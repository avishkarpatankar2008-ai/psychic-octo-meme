"use client";
import Link from "next/link";
import { useRouter, usePathname } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import { Logo } from "./Logo";
import { Button } from "./Button";

export function Navbar() {
  const { user, logout } = useAuth();
  const router = useRouter();
  const pathname = usePathname();
  async function handleLogout() { await logout(); router.push("/"); }
  const links = user ? [
    ["/dashboard","Overview"], ["/interviews/new","Practice"], ["/interview-profiles","Profiles"], ["/settings","Settings"]
  ] : [];
  return (
    <header className="sticky top-0 z-50 border-b border-white/[0.07] bg-[#070812]/80 backdrop-blur-xl">
      <div className="mx-auto flex h-16 max-w-7xl items-center justify-between px-5 lg:px-8">
        <Link href={user ? "/dashboard" : "/"} className="shrink-0"><Logo /></Link>
        {user ? (
          <div className="flex items-center gap-1">
            <nav className="hidden items-center gap-1 md:flex">
              {links.map(([href,label]) => <Link key={href} href={href} className={`rounded-lg px-3 py-2 text-sm transition ${pathname===href ? "bg-white/[0.07] text-white" : "text-white/50 hover:bg-white/[0.05] hover:text-white"}`}>{label}</Link>)}
            </nav>
            <div className="ml-2 hidden h-6 w-px bg-white/10 md:block" />
            <div className="ml-2 flex items-center gap-2">
              <div className="hidden text-right sm:block"><div className="text-xs font-medium text-white">{user.name}</div><div className="text-[10px] text-white/35">{user.email}</div></div>
              <button onClick={handleLogout} className="h-9 w-9 rounded-full border border-white/10 bg-white/[0.06] text-xs font-semibold text-white hover:bg-white/10" aria-label="Log out">{user.name?.slice(0,1).toUpperCase()}</button>
            </div>
          </div>
        ) : (
          <nav className="flex items-center gap-2"><Link href="/login" className="rounded-lg px-4 py-2 text-sm text-white/60 hover:text-white">Log in</Link><Link href="/signup"><Button className="px-4 py-2">Start free</Button></Link></nav>
        )}
      </div>
    </header>
  );
}
