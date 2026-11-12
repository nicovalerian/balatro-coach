import * as React from "react";
import { Dialog as SheetPrimitive } from "radix-ui";

import { cn } from "@/lib/utils";

// shadcn/ui Sheet (MIT), left/right only, classes rewritten for Tailwind 3 + tailwindcss-animate.
const Sheet = SheetPrimitive.Root;
const SheetTrigger = SheetPrimitive.Trigger;
const SheetClose = SheetPrimitive.Close;
const SheetTitle = SheetPrimitive.Title;
const SheetDescription = SheetPrimitive.Description;

const SheetOverlay = React.forwardRef(function SheetOverlay({ className, ...props }, ref) {
  return (
    <SheetPrimitive.Overlay
      ref={ref}
      className={cn(
        "fixed inset-0 z-50 bg-black/70",
        "data-[state=open]:animate-in data-[state=open]:fade-in-0 data-[state=open]:duration-300",
        "data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=closed]:duration-200",
        className
      )}
      {...props}
    />
  );
});

const SheetContent = React.forwardRef(function SheetContent(
  { className, children, side = "left", ...props },
  ref
) {
  return (
    <SheetPrimitive.Portal>
      <SheetOverlay />
      <SheetPrimitive.Content
        ref={ref}
        data-side={side}
        className={cn(
          "fixed inset-y-0 z-50 flex h-full flex-col text-ink shadow-[var(--shadow-shell)] outline-none ease-out",
          "data-[state=open]:animate-in data-[state=open]:duration-300 data-[state=closed]:animate-out data-[state=closed]:duration-200",
          side === "left" &&
            "left-0 data-[state=open]:slide-in-from-left data-[state=closed]:slide-out-to-left",
          side === "right" &&
            "right-0 data-[state=open]:slide-in-from-right data-[state=closed]:slide-out-to-right",
          className
        )}
        {...props}
      >
        {children}
      </SheetPrimitive.Content>
    </SheetPrimitive.Portal>
  );
});

export { Sheet, SheetTrigger, SheetClose, SheetContent, SheetTitle, SheetDescription };
