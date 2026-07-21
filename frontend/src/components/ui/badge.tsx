import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

const badgeVariants = cva(
  "inline-flex items-center gap-1.5 rounded border px-2 py-0.5 font-mono text-[10.5px] font-medium " +
    "uppercase tracking-wide",
  {
    variants: {
      variant: {
        default: "border-transparent bg-primary text-primary-foreground",
        accent: "border-accent bg-accent/10 text-accent",
        outline: "border-border bg-transparent text-muted-foreground",
        critical: "border-transparent bg-severity-critical/10 text-severity-critical",
        major: "border-transparent bg-severity-major/10 text-severity-major",
        minor: "border-transparent bg-severity-minor/10 text-severity-minor",
        queued: "border-border bg-transparent text-status-queued",
        processing: "border-transparent bg-status-processing/10 text-status-processing",
        done: "border-transparent bg-status-done/10 text-status-done",
        failed: "border-transparent bg-status-failed/10 text-status-failed",
      },
    },
    defaultVariants: {
      variant: "default",
    },
  },
);

export interface BadgeProps
  extends React.HTMLAttributes<HTMLSpanElement>,
    VariantProps<typeof badgeVariants> {}

export function Badge({ className, variant, ...props }: BadgeProps) {
  return <span className={cn(badgeVariants({ variant }), className)} {...props} />;
}
