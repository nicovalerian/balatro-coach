import { useCallback, useEffect, useRef, useState } from "react";

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
      style={{
        ...styles.zone,
        ...(dragging ? styles.zoneDrag : {}),
        ...(disabled ? styles.zoneDisabled : {}),
        ...(preview ? styles.zoneWithPreview : {}),
      }}
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
        <div style={styles.previewWrap}>
          <img src={preview} alt="screenshot" style={styles.previewImg} />
          <button style={styles.clearBtn} onClick={clear} title="Remove image">✕</button>
        </div>
      ) : (
        <div style={styles.placeholder}>
          <div style={styles.icon}>📸</div>
          <div style={styles.hint}>
            Drop screenshot · click to browse · paste (Ctrl+V)
          </div>
        </div>
      )}
    </div>
  );
}

const styles = {
  zone: {
    border: "1.5px dashed rgba(99,102,241,0.4)",
    borderRadius: 10,
    cursor: "pointer",
    transition: "border-color 0.2s, background 0.2s",
    background: "rgba(99,102,241,0.04)",
    minHeight: 72,
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
  },
  zoneDrag: {
    borderColor: "#818cf8",
    background: "rgba(99,102,241,0.1)",
  },
  zoneDisabled: {
    opacity: 0.5,
    cursor: "not-allowed",
  },
  zoneWithPreview: {
    border: "1.5px solid rgba(99,102,241,0.35)",
    cursor: "default",
    minHeight: 0,
  },
  placeholder: {
    display: "flex",
    flexDirection: "column",
    alignItems: "center",
    gap: 6,
    padding: "16px 12px",
    userSelect: "none",
  },
  icon: { fontSize: 22 },
  hint: { fontSize: 12, color: "#64748b", textAlign: "center" },
  previewWrap: {
    position: "relative",
    width: "100%",
    padding: 6,
  },
  previewImg: {
    width: "100%",
    borderRadius: 7,
    display: "block",
    maxHeight: 220,
    objectFit: "contain",
  },
  clearBtn: {
    position: "absolute",
    top: 10,
    right: 10,
    background: "rgba(0,0,0,0.6)",
    color: "#e2e8f0",
    border: "none",
    borderRadius: 5,
    width: 22,
    height: 22,
    cursor: "pointer",
    fontSize: 11,
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    lineHeight: 1,
  },
};
