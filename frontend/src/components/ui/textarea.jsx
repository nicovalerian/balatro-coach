import * as React from "react";

import { cn } from "@/lib/utils";

// shadcn/ui Textarea (MIT), with forwardRef so React 18 can pass refs through.
const Textarea = React.forwardRef(function Textarea({ className, ...props }, ref) {
  return (
    <textarea
      ref={ref}
      data-slot="textarea"
      className={cn(
        "flex w-full resize-none outline-none disabled:cursor-not-allowed disabled:opacity-60",
        className
      )}
      {...props}
    />
  );
});

export { Textarea };
