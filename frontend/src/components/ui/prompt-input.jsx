// Adapted from prompt-kit "PromptInput" (prompt-kit.com, MIT).
// Changes: JS instead of TS; styled with the composer tokens in index.css;
// clicking the shell only focuses the textarea when the click did not land on
// another control (so keyboard/mouse users of the toolbar keep their focus);
// the textarea stays editable while a reply streams, only submit is gated.
import React, { createContext, useContext, useLayoutEffect, useRef } from "react";

import { Textarea } from "@/components/ui/textarea";
import { cn } from "@/lib/utils";

const PromptInputContext = createContext({
  isLoading: false,
  value: "",
  setValue: () => {},
  maxHeight: 240,
  onSubmit: undefined,
  disabled: false,
  textareaRef: { current: null },
});

export function usePromptInput() {
  return useContext(PromptInputContext);
}

const INTERACTIVE = "button, a, input, textarea, select, label, [role='button']";

function PromptInput({
  className,
  isLoading = false,
  maxHeight = 240,
  value,
  onValueChange,
  onSubmit,
  children,
  disabled = false,
  textareaRef: externalRef,
  onClick,
  ...props
}) {
  const internalRef = useRef(null);
  const textareaRef = externalRef ?? internalRef;

  const handleClick = (event) => {
    if (!disabled && !event.target.closest(INTERACTIVE)) textareaRef.current?.focus();
    onClick?.(event);
  };

  return (
    <PromptInputContext.Provider
      value={{
        isLoading,
        value,
        setValue: onValueChange,
        maxHeight,
        onSubmit,
        disabled,
        textareaRef,
      }}
    >
      <div
        onClick={handleClick}
        className={cn("composer-shell cursor-text p-2", disabled && "cursor-not-allowed opacity-60", className)}
        {...props}
      >
        {children}
      </div>
    </PromptInputContext.Provider>
  );
}

function PromptInputTextarea({ className, onKeyDown, disableAutosize = false, ...props }) {
  const { value, setValue, maxHeight, onSubmit, disabled, textareaRef } = usePromptInput();

  const adjustHeight = (el) => {
    if (!el || disableAutosize) return;
    el.style.height = "auto";
    el.style.height =
      typeof maxHeight === "number"
        ? `${Math.min(el.scrollHeight, maxHeight)}px`
        : `min(${el.scrollHeight}px, ${maxHeight})`;
  };

  useLayoutEffect(() => {
    adjustHeight(textareaRef.current);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [value, maxHeight, disableAutosize]);

  const handleKeyDown = (event) => {
    if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing) {
      event.preventDefault();
      onSubmit?.();
    }
    onKeyDown?.(event);
  };

  return (
    <Textarea
      ref={textareaRef}
      value={value}
      onChange={(event) => {
        adjustHeight(event.target);
        setValue?.(event.target.value);
      }}
      onKeyDown={handleKeyDown}
      className={cn("composer-textarea terminal-copy", className)}
      rows={1}
      disabled={disabled}
      {...props}
    />
  );
}

function PromptInputActions({ children, className, ...props }) {
  return (
    <div className={cn("flex items-center gap-2", className)} {...props}>
      {children}
    </div>
  );
}

export { PromptInput, PromptInputTextarea, PromptInputActions };
