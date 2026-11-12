// Adapted from Motion Primitives "Disclosure" (motion-primitives.com, MIT).
// Changes: JS instead of TS; the content id lives in the provider so a trigger
// anywhere (inside or outside the Disclosure) can point at it with aria-controls;
// native <button> triggers keep their own semantics; reduced motion skips the
// height tween and shows content immediately.
import * as React from "react";
import { createContext, useContext, useEffect, useId, useState } from "react";
import { AnimatePresence, MotionConfig, m, useReducedMotion } from "motion/react";

import { cn } from "@/lib/utils";
import { SPRING, collapse } from "@/lib/motion";

const DisclosureContext = createContext(undefined);

function useDisclosure() {
  const context = useContext(DisclosureContext);
  if (!context) throw new Error("useDisclosure must be used within a Disclosure");
  return context;
}

export function Disclosure({
  open: openProp = false,
  onOpenChange,
  children,
  className,
  transition = SPRING,
  variants,
  id,
}) {
  const [open, setOpen] = useState(openProp);
  const generatedId = useId();
  const contentId = id ?? `disclosure-${generatedId.replace(/:/g, "")}`;

  useEffect(() => {
    setOpen(openProp);
  }, [openProp]);

  const toggle = () => {
    const next = !open;
    setOpen(next);
    onOpenChange?.(next);
  };

  return (
    <MotionConfig transition={transition}>
      <div className={className}>
        <DisclosureContext.Provider value={{ open, toggle, variants, contentId }}>
          {children}
        </DisclosureContext.Provider>
      </div>
    </MotionConfig>
  );
}

export function DisclosureTrigger({ children, className }) {
  const { toggle, open, contentId } = useDisclosure();

  return React.Children.map(children, (child) => {
    if (!React.isValidElement(child)) return child;
    const isNativeButton = child.type === "button";
    return React.cloneElement(child, {
      ...child.props,
      onClick: (event) => {
        child.props.onClick?.(event);
        toggle();
      },
      "aria-expanded": open,
      "aria-controls": contentId,
      ...(isNativeButton
        ? { type: "button" }
        : {
            role: "button",
            tabIndex: 0,
            onKeyDown: (event) => {
              if (event.key === "Enter" || event.key === " ") {
                event.preventDefault();
                toggle();
              }
            },
          }),
      className: cn(className, child.props.className),
    });
  });
}

export function DisclosureContent({ children, className }) {
  const { open, variants, contentId } = useDisclosure();
  const reduceMotion = useReducedMotion();

  const combined = {
    expanded: { ...collapse.expanded, ...variants?.expanded },
    collapsed: { ...collapse.collapsed, ...variants?.collapsed },
  };

  return (
    <div id={contentId} className={cn("overflow-hidden", className)}>
      <AnimatePresence initial={false}>
        {open ? (
          <m.div
            key="content"
            initial={reduceMotion ? false : "collapsed"}
            animate="expanded"
            exit={reduceMotion ? undefined : "collapsed"}
            variants={combined}
          >
            {children}
          </m.div>
        ) : null}
      </AnimatePresence>
    </div>
  );
}
