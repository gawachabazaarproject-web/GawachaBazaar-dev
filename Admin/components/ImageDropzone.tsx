"use client";

import React, { useCallback, useRef, useState } from "react";
import { Icon } from "./icons";

const ALLOWED_TYPES = ["image/jpeg", "image/png", "image/webp", "image/gif"];
const MAX_BYTES = 8 * 1024 * 1024;

/**
 * Drag-and-drop / click-to-browse image upload. Deliberately dumb about
 * where the file goes - the caller's `onUpload` does the actual API call
 * (Cloudinary-backed, see backend/app/services/image_upload.py) and this
 * component only owns the drag/drop/preview/busy/error UI around it, so
 * every screen that needs an image field reuses the exact same upload
 * mechanics instead of re-implementing drag-and-drop per page.
 */
export function ImageDropzone({
  currentUrl,
  onUpload,
  onRemove,
  disabled,
  label = "Image",
}: {
  currentUrl?: string | null;
  onUpload: (file: File) => Promise<void>;
  onRemove?: () => Promise<void>;
  disabled?: boolean;
  label?: string;
}) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragOver, setDragOver] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleFile = useCallback(
    async (file: File) => {
      setError(null);
      if (!ALLOWED_TYPES.includes(file.type)) {
        setError("Unsupported file type. Use JPEG, PNG, WEBP, or GIF.");
        return;
      }
      if (file.size > MAX_BYTES) {
        setError(`Image is too large (${(file.size / 1_048_576).toFixed(1)} MB) - the limit is 8 MB.`);
        return;
      }
      setBusy(true);
      try {
        await onUpload(file);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Upload failed.");
      } finally {
        setBusy(false);
      }
    },
    [onUpload],
  );

  const handleRemove = async () => {
    if (!onRemove) return;
    setError(null);
    setBusy(true);
    try {
      await onRemove();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to remove image.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div>
      <p className="mb-1.5 text-sm font-medium text-neutral-700">{label}</p>
      <div
        onDragOver={(e) => {
          e.preventDefault();
          if (!disabled && !busy) setDragOver(true);
        }}
        onDragLeave={() => setDragOver(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDragOver(false);
          if (disabled || busy) return;
          const file = e.dataTransfer.files?.[0];
          if (file) handleFile(file);
        }}
        onClick={() => !disabled && !busy && inputRef.current?.click()}
        className={`flex cursor-pointer flex-col items-center justify-center gap-2 rounded border-2 border-dashed p-4 text-center transition-colors ${
          dragOver ? "border-primary-500 bg-primary-50" : "border-neutral-300 bg-neutral-50"
        } ${disabled || busy ? "cursor-not-allowed opacity-60" : "hover:border-primary-400"}`}
        style={{ minHeight: currentUrl ? undefined : 140 }}
      >
        {currentUrl ? (
          <div className="relative">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img src={currentUrl} alt="" className="max-h-40 rounded object-contain" />
          </div>
        ) : (
          <>
            <Icon name="upload" size={28} className="text-neutral-400" />
            <p className="text-sm text-neutral-600">
              {busy ? "Uploading..." : "Drag & drop an image, or click to browse"}
            </p>
            <p className="text-xs text-neutral-400">JPEG, PNG, WEBP, or GIF · up to 8 MB</p>
          </>
        )}
        <input
          ref={inputRef}
          type="file"
          accept={ALLOWED_TYPES.join(",")}
          className="hidden"
          disabled={disabled || busy}
          onChange={(e) => {
            const file = e.target.files?.[0];
            if (file) handleFile(file);
            e.target.value = "";
          }}
        />
      </div>

      {currentUrl && (
        <div className="mt-2 flex items-center gap-3">
          <button
            type="button"
            onClick={(e) => {
              e.stopPropagation();
              inputRef.current?.click();
            }}
            disabled={disabled || busy}
            className="text-sm font-medium text-primary-700 hover:underline disabled:opacity-50"
          >
            {busy ? "Uploading..." : "Replace image"}
          </button>
          {onRemove && (
            <button
              type="button"
              onClick={(e) => {
                e.stopPropagation();
                handleRemove();
              }}
              disabled={disabled || busy}
              className="text-sm font-medium text-status-danger hover:underline disabled:opacity-50"
            >
              Remove
            </button>
          )}
        </div>
      )}

      {error && (
        <p className="mt-2 rounded border border-status-danger/30 bg-status-dangerLight px-3 py-2 text-xs text-status-danger">
          {error}
        </p>
      )}
    </div>
  );
}
