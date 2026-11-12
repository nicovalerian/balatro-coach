import * as React from "react";
import { Popover as PopoverPrimitive } from "radix-ui";

import { cn } from "@/lib/utils";

// shadcn/ui Popover (MIT), styled with the project tokens. Used instead of a
// tooltip for help text so it opens on tap and keyboard as well as hover.
const Popover = PopoverPrimitive.Root;
const PopoverTrigger = PopoverPrimitive.Trigger;

const PopoverContent = React.forwardRef(function PopoverContent(
  { className, align = "end", sideOffset = 6, children, ...props },
  ref
) {
  return (
    <PopoverPrimitive.Portal>
      <PopoverPrimitive.Content
        ref={ref}
        align={align}
        sideOffset={sideOffset}
        collisionPadding={12}
        className={cn(
          "z-50 w-[260px] rounded-control border-2 border-line-strong bg-[#1d2025] p-3 text-[12px] leading-relaxed text-ink-muted shadow-[var(--shadow-raised)] outline-none",
          "data-[state=open]:animate-in data-[state=open]:fade-in-0 data-[state=open]:zoom-in-95",
          "data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=closed]:zoom-out-95",
          "data-[side=bottom]:slide-in-from-top-1 data-[side=left]:slide-in-from-right-1 data-[side=right]:slide-in-from-left-1 data-[side=top]:slide-in-from-bottom-1",
          className
        )}
        {...props}
      >
        {children}
        <PopoverPrimitive.Arrow className="fill-[#1d2025]" width={10} height={5} />
      </PopoverPrimitive.Content>
    </PopoverPrimitive.Portal>
  );
});

export { Popover, PopoverTrigger, PopoverContent };
