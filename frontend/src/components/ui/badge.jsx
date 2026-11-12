import * as React from "react";
import { cva } from "class-variance-authority";

import { cn } from "@/lib/utils";

// shadcn/ui Badge (MIT), narrowed to the three chip tones the run summary uses.
const badgeVariants = cva(
  "inline-flex h-7 shrink-0 items-center whitespace-nowrap rounded-full border-2 px-2.5 text-[12px] leading-none",
  {
    variants: {
      tone: {
        default: "border-line bg-black/20 text-ink",
        gold: "border-gold/50 bg-gold/10 text-gold-soft",
        red: "border-suit-heart/50 bg-suit-heart/10 text-[#ffc9c9]",
      },
    },
    defaultVariants: { tone: "default" },
  }
);

function Badge({ className, tone, ...props }) {
  return <span className={cn(badgeVariants({ tone }), className)} {...props} />;
}

export { Badge, badgeVariants };
