import { useEffect, useMemo, useRef, useState } from "react";
import { AnimatePresence, m, useReducedMotion } from "motion/react";
import { ImagePlus, Upload, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { SPRING, dealIn } from "@/lib/motion";
import { cn } from "@/lib/utils";

const MAX_FILES = 3;

// Appends image files to the current selection, capped at MAX_FILES.
// Returns null when nothing would change.
export function addImageFiles(files, incomingFiles) {
  const nextFiles = Array.from(incomingFiles ?? []).filter((file) => file?.type?.startsWith("image/"));
  if (nextFiles.length === 0) return null;

  const remainingSlots = Math.max(0, MAX_FILES - files.length);
  if (remainingSlots === 0) return null;

  return [...files, ...nextFiles.slice(0, remainingSlots)];
}

// Window-level paste handler, so screenshots can be pasted whether or not the
// uploader panel is open.
export function useClipboardImages(onImages) {
  useEffect(() => {
    const onPaste = (event) => {
      const pastedFiles = Array.from(event.clipboardData?.items ?? [])
        .filter((entry) => entry.kind === "file" && entry.type.startsWith("image/"))
        .map((entry) => entry.getAsFile())
        .filter(Boolean);

      if (pastedFiles.length > 0) onImages(pastedFiles);
    };

    window.addEventListener("paste", onPaste);
    return () => window.removeEventListener("paste", onPaste);
  }, [onImages]);
}

export default function ImageUploader({ files = [], onFilesChange, disabled }) {
  const [dragging, setDragging] = useState(false);
  const inputRef = useRef(null);
  const reduceMotion = useReducedMotion();

  const previews = useMemo(
    () =>
      files.map((file) => ({
        file,
        url: URL.createObjectURL(file),
      })),
    [files]
  );

  useEffect(
    () => () => {
      previews.forEach((preview) => URL.revokeObjectURL(preview.url));
    },
    [previews]
  );

  const appendFiles = (incomingFiles) => {
    const next = addImageFiles(files, incomingFiles);
    if (next) onFilesChange(next);
  };

  const removeFileAt = (indexToRemove) => {
    onFilesChange(files.filter((_, index) => index !== indexToRemove));
    if (inputRef.current) inputRef.current.value = "";
  };

  const openPicker = () => {
    if (!disabled) {
      inputRef.current?.click();
    }
  };

  return (
    <div
      className={cn(
        "upload-dropzone",
        dragging && "upload-dropzone-active",
        files.length > 0 && !dragging && "upload-dropzone-preview",
        disabled && "cursor-not-allowed opacity-60"
      )}
      onDragOver={(event) => {
        event.preventDefault();
        if (!disabled) setDragging(true);
      }}
      onDragLeave={() => setDragging(false)}
      onDrop={
        disabled
          ? undefined
          : (event) => {
              event.preventDefault();
              setDragging(false);
              appendFiles(event.dataTransfer.files);
            }
      }
    >
      <input
        ref={inputRef}
        type="file"
        accept="image/*"
        multiple
        className="hidden"
        aria-label="Choose screenshots"
        onChange={(event) => appendFiles(event.target.files)}
        disabled={disabled}
      />

      <div className="flex flex-wrap items-center justify-between gap-3 p-3">
        <div className="flex min-w-[220px] flex-1 items-center gap-3">
          <div
            className="flex h-10 w-10 shrink-0 items-center justify-center rounded-control border-2 border-sky/40 bg-sky/10"
            aria-hidden="true"
          >
            <Upload className="h-[18px] w-[18px] text-sky" />
          </div>
          <div className="min-w-0">
            <p className="pixel-font text-[14px] text-ink">
              Screenshots <span className="text-ink-subtle">{files.length}/{MAX_FILES}</span>
            </p>
            <p className="terminal-copy mt-1 text-[12px] leading-5 text-ink-muted">
              Add up to 3 images from blind, hand, shop, or joker layout.
              {files.length === 0 ? (
                <span className="hidden sm:inline"> Drop them here or paste from the clipboard.</span>
              ) : null}
            </p>
          </div>
        </div>

        <Button
          variant="secondary"
          size="sm"
          onClick={openPicker}
          disabled={disabled || files.length >= MAX_FILES}
        >
          <ImagePlus />
          {files.length > 0 ? "Add Screenshot" : "Choose Images"}
        </Button>
      </div>

      {files.length > 0 ? (
        <ul className="grid grid-cols-3 gap-2 px-3 pb-3">
          <AnimatePresence initial={false}>
            {previews.map((preview, index) => (
              <m.li
                key={`${preview.file.name}-${preview.file.lastModified}-${preview.file.size}`}
                initial={reduceMotion ? false : dealIn.initial}
                animate={dealIn.animate}
                exit={reduceMotion ? undefined : dealIn.exit}
                transition={SPRING}
                className="relative min-w-0"
              >
                <img
                  src={preview.url}
                  alt={`Screenshot ${index + 1}: ${preview.file.name}`}
                  className="aspect-video w-full rounded-control border-2 border-line object-cover"
                />
                <Button
                  variant="danger"
                  size="icon-sm"
                  className="absolute right-1 top-1 h-7 min-h-7 w-7 rounded-[8px] [&_svg]:h-3.5 [&_svg]:w-3.5"
                  onClick={() => removeFileAt(index)}
                  aria-label={`Remove ${preview.file.name}`}
                >
                  <X />
                </Button>
                <p className="terminal-copy mt-1.5 truncate text-[12px] text-ink-muted" title={preview.file.name}>
                  {preview.file.name}
                </p>
              </m.li>
            ))}
          </AnimatePresence>
        </ul>
      ) : null}
    </div>
  );
}
