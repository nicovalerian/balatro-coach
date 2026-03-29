import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { ImagePlus, Upload, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

const MAX_FILES = 3;

export default function ImageUploader({
  files = [],
  onFilesChange,
  disabled,
}) {
  const [dragging, setDragging] = useState(false);
  const inputRef = useRef(null);

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

  const appendFiles = useCallback(
    (incomingFiles) => {
      const nextFiles = Array.from(incomingFiles ?? []).filter(
        (file) => file?.type?.startsWith("image/")
      );
      if (nextFiles.length === 0) return;

      const remainingSlots = Math.max(0, MAX_FILES - files.length);
      if (remainingSlots === 0) return;

      onFilesChange([...files, ...nextFiles.slice(0, remainingSlots)]);
    },
    [files, onFilesChange]
  );

  useEffect(() => {
    const onPaste = (event) => {
      const pastedFiles = Array.from(event.clipboardData?.items ?? [])
        .filter((entry) => entry.kind === "file" && entry.type.startsWith("image/"))
        .map((entry) => entry.getAsFile())
        .filter(Boolean);

      if (pastedFiles.length > 0) {
        appendFiles(pastedFiles);
      }
    };

    window.addEventListener("paste", onPaste);
    return () => window.removeEventListener("paste", onPaste);
  }, [appendFiles]);

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
        files.length > 0 && "upload-dropzone-preview",
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
        onChange={(event) => appendFiles(event.target.files)}
        disabled={disabled}
      />

      <div className="flex min-h-[64px] flex-wrap items-center justify-between gap-3 px-4 py-2.5">
        <div className="flex items-center gap-3">
          <div className="flex h-11 w-11 items-center justify-center rounded-[12px] border-2 border-[#3498db]/45 bg-[#3498db]/10">
            <Upload className="h-5 w-5 text-[#78bfff]" />
          </div>
          <div>
            <p className="pixel-font text-[13px] text-[#f0f0f0]">Screenshots</p>
            <p className="terminal-copy text-[12px] text-[#b6c0ba]">
              Add up to 3 images from blind, hand, shop, or joker layout.
            </p>
          </div>
        </div>

        <Button
          type="button"
          className="action-button action-button-secondary min-h-[44px] px-4"
          onClick={openPicker}
          disabled={disabled || files.length >= MAX_FILES}
        >
          <ImagePlus className="mr-2 h-4 w-4" />
          {files.length > 0 ? "Add Screenshot" : "Choose Images"}
        </Button>
      </div>

      {files.length === 0 ? (
        <div className="px-4 pb-2">
          <p className="terminal-copy text-[12px] text-[#aab5ae]">
            Drop screenshots here or paste from the clipboard.
          </p>
        </div>
      ) : (
        <div className="px-3 pb-2">
          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
            {previews.map((preview, index) => (
              <div key={`${preview.file.name}-${index}`} className="terminal-inset p-2">
                <div className="relative">
                  <img
                    src={preview.url}
                    alt={`screenshot preview ${index + 1}`}
                    className="h-[116px] w-full rounded-[12px] object-cover"
                  />
                  <Button
                    type="button"
                    className="action-button action-button-danger absolute right-2 top-2 min-h-[34px] px-3"
                    onClick={() => removeFileAt(index)}
                  >
                    <X className="h-3.5 w-3.5" />
                  </Button>
                </div>
                <div className="mt-2 flex items-center justify-between gap-2">
                  <p className="terminal-copy truncate text-[12px] text-[#dce4df]">
                    {preview.file.name}
                  </p>
                  <span className="pixel-font text-[11px] text-[#f2c237]">
                    {index + 1}/{MAX_FILES}
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
