import { useCallback, useEffect, useRef, useState } from "react";
import { Upload, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

/**
 * ImageUploader
 * Supports: click to browse, drag-and-drop, paste (Ctrl+V).
 * Shows a preview thumbnail. Calls onFile(File) when an image is selected.
 */
export default function ImageUploader({ onFile, disabled }) {
  const [preview, setPreview] = useState(null);
  const [dragging, setDragging] = useState(false);
  const inputRef = useRef(null);

  const handleFile = useCallback(
    (file) => {
      if (!file || !file.type.startsWith("image/")) return;
      setPreview(URL.createObjectURL(file));
      onFile(file);
    },
    [onFile]
  );

  // Paste support
  useEffect(() => {
    const onPaste = (e) => {
      const item = Array.from(e.clipboardData?.items ?? []).find(
        (i) => i.kind === "file" && i.type.startsWith("image/")
      );
      if (item) handleFile(item.getAsFile());
    };
    window.addEventListener("paste", onPaste);
    return () => window.removeEventListener("paste", onPaste);
  }, [handleFile]);

  const onDrop = (e) => {
    e.preventDefault();
    setDragging(false);
    const file = e.dataTransfer.files?.[0];
    handleFile(file);
  };

  const clear = (e) => {
    e.stopPropagation();
    setPreview(null);
    onFile(null);
    if (inputRef.current) inputRef.current.value = "";
  };

  return (
    <div
      className={cn(
        "rounded-lg border border-dashed border-accent/40 bg-accent/5 transition-colors",
        dragging && "border-accent bg-accent/10",
        disabled && "cursor-not-allowed opacity-50",
        preview && "border-border bg-card"
      )}
      onClick={() => !disabled && !preview && inputRef.current?.click()}
      onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
      onDragLeave={() => setDragging(false)}
      onDrop={disabled ? undefined : onDrop}
    >
      <input
        ref={inputRef}
        type="file"
        accept="image/*"
        style={{ display: "none" }}
        onChange={(e) => handleFile(e.target.files?.[0])}
        disabled={disabled}
      />

      {preview ? (
        <div className="relative w-full p-2">
          <img src={preview} alt="screenshot" style={styles.previewImg} />
          <Button
            type="button"
            size="icon-sm"
            variant="secondary"
            className="absolute right-3 top-3"
            onClick={clear}
            title="Remove image"
          >
            <X className="h-3.5 w-3.5" />
          </Button>
        </div>
      ) : (
        <div className="flex select-none items-center gap-2 px-3 py-2">
          <Upload className="h-4 w-4 text-accent" />
          <div className="text-xs text-muted-foreground">
            Drop screenshot, click to browse, or paste (Ctrl+V)
          </div>
        </div>
      )}
    </div>
  );
}

const styles = {
  previewImg: {
    width: "100%",
    borderRadius: 10,
    display: "block",
    maxHeight: 220,
    objectFit: "contain",
  },
};
