// shadcn/ui-style owned component using the Radix Slot primitive.
import * as React from "react"
import { Slot } from "@radix-ui/react-slot"
import { cva, type VariantProps } from "class-variance-authority"
import { cn } from "@/lib/utils"

const buttonVariants = cva(
  "inline-flex items-center justify-center rounded-md px-4 py-2 text-sm font-medium focus-visible:outline-2 focus-visible:outline-offset-2 disabled:pointer-events-none disabled:opacity-50",
  { variants: { variant: { default: "bg-slate-900 text-white hover:bg-slate-700", outline: "border border-slate-300 hover:bg-slate-100" } }, defaultVariants: { variant: "default" } },
)

export function Button({ className, variant, asChild = false, ...props }:
  React.ComponentProps<"button"> & VariantProps<typeof buttonVariants> & { asChild?: boolean }) {
  const Component = asChild ? Slot : "button"
  return <Component className={cn(buttonVariants({ variant, className }))} {...props} />
}
