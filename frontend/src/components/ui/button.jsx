import * as React from "react";
import { cva } from "class-variance-authority";
import { Slot } from "radix-ui";

import { cn } from "@/lib/utils";

// shadcn/ui Button (MIT), narrowed to the Balatro button treatment defined in index.css.
const buttonVariants = cva("action-button", {
  variants: {
    variant: {
      primary: "action-button-primary",
      secondary: "action-button-secondary",
      ghost: "action-button-ghost",
      danger: "action-button-danger",
    },
    size: {
      default: "",
      sm: "action-button-sm",
      icon: "action-button-icon",
      "icon-sm": "action-button-icon action-button-sm",
    },
  },
  defaultVariants: {
    variant: "ghost",
    size: "default",
  },
});

const Button = React.forwardRef(function Button(
  { className, variant, size, asChild = false, type = "button", ...props },
  ref
) {
  const Comp = asChild ? Slot.Root : "button";

  return (
    <Comp
      ref={ref}
      data-slot="button"
      type={asChild ? undefined : type}
      className={cn(buttonVariants({ variant, size }), className)}
      {...props}
    />
  );
});

export { Button, buttonVariants };
