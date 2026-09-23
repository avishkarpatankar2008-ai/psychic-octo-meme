import { ButtonHTMLAttributes, forwardRef } from "react";
type Variant = "primary" | "secondary" | "ghost" | "danger";
interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> { variant?: Variant; isLoading?: boolean; }
const variantClasses: Record<Variant,string> = {
 primary:"bg-white text-[#080912] shadow-[0_8px_30px_rgba(124,92,255,.22)] hover:-translate-y-0.5 hover:bg-violet-50 disabled:opacity-50",
 secondary:"border border-white/10 bg-white/[0.05] text-white hover:bg-white/[0.09] disabled:opacity-50",
 ghost:"bg-transparent text-white/60 hover:bg-white/[0.05] hover:text-white disabled:opacity-50",
 danger:"bg-danger text-white hover:bg-danger/90 disabled:opacity-50"
};
export const Button=forwardRef<HTMLButtonElement,ButtonProps>(({variant="primary",isLoading=false,className="",children,disabled,...props},ref)=>(
<button ref={ref} disabled={disabled||isLoading} className={`inline-flex items-center justify-center gap-2 rounded-xl px-4 py-2.5 text-sm font-semibold transition-all duration-200 disabled:cursor-not-allowed ${variantClasses[variant]} ${className}`} {...props}>
{isLoading&&<span className="h-4 w-4 animate-spin rounded-full border-2 border-current border-t-transparent"/>}{children}</button>
)); Button.displayName="Button";
