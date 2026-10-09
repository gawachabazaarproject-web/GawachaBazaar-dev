"use client";

import React, { useCallback, useEffect, useState } from "react";
import { useAuth } from "@/lib/auth-context";
import {
  createHomeSlide,
  deleteHomeSlide,
  fetchHomeSlides,
  HomeSlide,
  HomeSlideApiError,
  HomeSlideFields,
  replaceHomeSlideImage,
  updateHomeSlide,
} from "@/lib/home-slides";
import { ImageDropzone } from "@/components/ImageDropzone";
import { PageHeader } from "@/components/PageHeader";
import { EmptyState } from "@/components/EmptyState";
import { TableSkeleton } from "@/components/TableSkeleton";
import { StatusBadge } from "@/components/StatusBadge";

const inputCls =
  "w-full rounded border border-neutral-300 px-3 py-2 text-sm focus:border-primary-500 focus:outline-none focus:ring-1 focus:ring-primary-500";

export default function ContentPage() {
  const { getAccessToken } = useAuth();
  const [slides, setSlides] = useState<HomeSlide[] | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [addOpen, setAddOpen] = useState(false);
  const [editing, setEditing] = useState<HomeSlide | null>(null);
  const [busy, setBusy] = useState<number | null>(null);

  const load = useCallback(async () => {
    const token = getAccessToken();
    if (!token) return;
    setLoading(true);
    setError(null);
    try {
      setSlides(await fetchHomeSlides(token));
    } catch (err) {
      setError(err instanceof HomeSlideApiError ? err.message : "Unable to load slides.");
    } finally {
      setLoading(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const run = async (id: number, action: (token: string) => Promise<unknown>) => {
    const token = getAccessToken();
    if (!token) return;
    setBusy(id);
    setError(null);
    try {
      await action(token);
      await load();
    } catch (err) {
      setError(err instanceof HomeSlideApiError ? err.message : "Something went wrong.");
    } finally {
      setBusy(null);
    }
  };

  // Reordering renumbers every slide 0..n-1 in its new position, so order
  // values never collide or drift.
  const move = (index: number, dir: -1 | 1) => {
    if (!slides) return;
    const target = index + dir;
    if (target < 0 || target >= slides.length) return;
    const next = [...slides];
    [next[index], next[target]] = [next[target], next[index]];
    void run(slides[index].id, (token) =>
      Promise.all(
        next.map((s, i) => (s.display_order === i ? null : updateHomeSlide(token, s.id, { display_order: i }))),
      ),
    );
  };

  const toggle = (s: HomeSlide) =>
    run(s.id, (token) => updateHomeSlide(token, s.id, { status: s.status === "ACTIVE" ? "INACTIVE" : "ACTIVE" }));

  const remove = (s: HomeSlide) => {
    if (!confirm(`Delete the "${s.title}" slide? This can't be undone.`)) return;
    void run(s.id, (token) => deleteHomeSlide(token, s.id));
  };

  return (
    <div>
      <PageHeader
        eyebrow="Marketing"
        title="Home slides"
        description="The big carousel at the top of the mobile app's Home screen. Edit text and photos, reorder, hide or add slides - changes appear in the app on its next refresh."
        actions={
          <button
            onClick={() => setAddOpen(true)}
            className="rounded bg-primary-800 px-4 py-2 text-sm font-semibold text-white hover:bg-primary-700"
          >
            + Add slide
          </button>
        }
      />

      {error && (
        <p className="mb-4 rounded border border-status-danger/30 bg-status-dangerLight px-3 py-2 text-sm text-status-danger">
          {error}
        </p>
      )}

      <div className="overflow-hidden rounded border border-neutral-200 bg-white">
        {loading && !slides ? (
          <TableSkeleton rows={4} columns={5} />
        ) : !slides || slides.length === 0 ? (
          <EmptyState
            icon="file-text"
            title="No slides"
            message="The Home carousel is hidden in the app until you add at least one slide."
          />
        ) : (
          <ul className="divide-y divide-neutral-100">
            {slides.map((s, i) => (
              <li key={s.id} className={`flex items-center gap-4 p-4 ${busy === s.id ? "opacity-50" : ""}`}>
                <div className="flex flex-col">
                  <button
                    disabled={busy !== null || i === 0}
                    onClick={() => move(i, -1)}
                    aria-label="Move up"
                    className="px-1 text-neutral-400 hover:text-primary-700 disabled:opacity-20"
                  >
                    ▲
                  </button>
                  <button
                    disabled={busy !== null || i === slides.length - 1}
                    onClick={() => move(i, 1)}
                    aria-label="Move down"
                    className="px-1 text-neutral-400 hover:text-primary-700 disabled:opacity-20"
                  >
                    ▼
                  </button>
                </div>
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img src={s.image_url} alt="" className="h-24 w-20 shrink-0 rounded object-cover" />
                <div className="min-w-0 flex-1">
                  <p className="text-xs font-semibold uppercase tracking-wide text-accent-700">{s.label}</p>
                  <p className="font-display text-base font-semibold text-primary-900">
                    {s.title} {s.script_suffix && <em className="font-normal">{s.script_suffix}</em>}
                  </p>
                  <p className="line-clamp-2 text-sm text-neutral-500">{s.body}</p>
                  {s.cta_label && <p className="mt-1 text-xs text-neutral-400">Button: {s.cta_label}</p>}
                </div>
                <StatusBadge status={s.status} />
                <div className="flex gap-3 text-xs font-semibold">
                  <button disabled={busy !== null} onClick={() => setEditing(s)} className="text-neutral-500 hover:text-primary-700 hover:underline">
                    Edit
                  </button>
                  <button disabled={busy !== null} onClick={() => toggle(s)} className="text-neutral-500 hover:text-primary-700 hover:underline">
                    {s.status === "ACTIVE" ? "Hide" : "Show"}
                  </button>
                  <button disabled={busy !== null} onClick={() => remove(s)} className="text-status-danger hover:underline">
                    Delete
                  </button>
                </div>
              </li>
            ))}
          </ul>
        )}
      </div>

      {addOpen && (
        <AddSlideDialog
          nextOrder={slides?.length ?? 0}
          onClose={() => setAddOpen(false)}
          onCreated={() => {
            setAddOpen(false);
            load();
          }}
        />
      )}
      {editing && (
        <EditSlideDialog
          slide={editing}
          onClose={() => setEditing(null)}
          onSaved={() => {
            setEditing(null);
            load();
          }}
        />
      )}
    </div>
  );
}

function SlideForm({
  value,
  onChange,
}: {
  value: HomeSlideFields;
  onChange: (next: HomeSlideFields) => void;
}) {
  const set = (k: keyof HomeSlideFields) => (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) =>
    onChange({ ...value, [k]: e.target.value });
  return (
    <>
      <Field label="Small label (e.g. SEASONAL MARKET)">
        <input value={value.label} onChange={set("label")} className={inputCls} />
      </Field>
      <div className="grid grid-cols-2 gap-3">
        <Field label="Headline">
          <input value={value.title} onChange={set("title")} className={inputCls} />
        </Field>
        <Field label="Headline accent (italic, 2nd line)">
          <input value={value.script_suffix} onChange={set("script_suffix")} className={inputCls} />
        </Field>
      </div>
      <Field label="Description">
        <textarea value={value.body} onChange={set("body")} rows={3} className={inputCls} />
      </Field>
      <div className="grid grid-cols-2 gap-3">
        <Field label="Button text">
          <input value={value.cta_label} onChange={set("cta_label")} className={inputCls} />
        </Field>
        <Field label="Button link (optional)">
          <input value={value.link_url} onChange={set("link_url")} placeholder="https://... or leave empty" className={inputCls} />
        </Field>
      </div>
    </>
  );
}

function AddSlideDialog({ nextOrder, onClose, onCreated }: { nextOrder: number; onClose: () => void; onCreated: () => void }) {
  const { getAccessToken } = useAuth();
  const [fields, setFields] = useState<HomeSlideFields>({ label: "", title: "", script_suffix: "", body: "", cta_label: "", link_url: "" });
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submit = async () => {
    const token = getAccessToken();
    if (!token || !file) return;
    setSaving(true);
    setError(null);
    try {
      await createHomeSlide(token, { ...fields, display_order: nextOrder, file });
      onCreated();
    } catch (err) {
      setError(err instanceof HomeSlideApiError ? err.message : "Unable to add slide.");
    } finally {
      setSaving(false);
    }
  };

  return (
    <Modal title="Add slide" onClose={onClose}>
      <Field label="Photo (portrait works best, e.g. 1200x1500)">
        <label className="flex min-h-[110px] cursor-pointer flex-col items-center justify-center gap-2 rounded border-2 border-dashed border-neutral-300 bg-neutral-50 p-4 text-center hover:border-primary-400">
          {preview ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img src={preview} alt="" className="max-h-40 rounded object-contain" />
          ) : (
            <p className="text-sm text-neutral-500">Click to choose an image</p>
          )}
          <input
            type="file"
            accept="image/jpeg,image/png,image/webp,image/gif"
            className="hidden"
            onChange={(e) => {
              const f = e.target.files?.[0];
              if (f) {
                setFile(f);
                setPreview(URL.createObjectURL(f));
              }
            }}
          />
        </label>
      </Field>
      <SlideForm value={fields} onChange={setFields} />
      {error && <ErrorBox message={error} />}
      <Actions
        onClose={onClose}
        onSubmit={submit}
        disabled={saving || !file || !fields.label.trim() || !fields.title.trim()}
        label={saving ? "Adding..." : "Add slide"}
      />
    </Modal>
  );
}

function EditSlideDialog({ slide, onClose, onSaved }: { slide: HomeSlide; onClose: () => void; onSaved: () => void }) {
  const { getAccessToken } = useAuth();
  const [fields, setFields] = useState<HomeSlideFields>({
    label: slide.label,
    title: slide.title,
    script_suffix: slide.script_suffix ?? "",
    body: slide.body,
    cta_label: slide.cta_label,
    link_url: slide.link_url ?? "",
  });
  const [imageUrl, setImageUrl] = useState(slide.image_url);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submit = async () => {
    const token = getAccessToken();
    if (!token) return;
    setSaving(true);
    setError(null);
    try {
      await updateHomeSlide(token, slide.id, fields);
      onSaved();
    } catch (err) {
      setError(err instanceof HomeSlideApiError ? err.message : "Unable to save changes.");
    } finally {
      setSaving(false);
    }
  };

  return (
    <Modal title="Edit slide" onClose={onClose}>
      <Field label="Photo">
        <ImageDropzone
          currentUrl={imageUrl}
          onUpload={async (file) => {
            const token = getAccessToken();
            if (!token) return;
            const updated = await replaceHomeSlideImage(token, slide.id, file);
            setImageUrl(updated.image_url);
          }}
        />
      </Field>
      <SlideForm value={fields} onChange={setFields} />
      {error && <ErrorBox message={error} />}
      <Actions
        onClose={onClose}
        onSubmit={submit}
        disabled={saving || !fields.label.trim() || !fields.title.trim()}
        label={saving ? "Saving..." : "Save changes"}
      />
    </Modal>
  );
}

function Modal({ title, onClose, children }: { title: string; onClose: () => void; children: React.ReactNode }) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center overflow-y-auto bg-black/40 px-4 py-6" onClick={onClose}>
      <div className="w-full max-w-lg rounded bg-white p-6 shadow-xl" onClick={(e) => e.stopPropagation()}>
        <h2 className="mb-4 font-display text-lg font-semibold text-primary-900">{title}</h2>
        {children}
      </div>
    </div>
  );
}

function Actions({ onClose, onSubmit, disabled, label }: { onClose: () => void; onSubmit: () => void; disabled: boolean; label: string }) {
  return (
    <div className="mt-4 flex justify-end gap-2">
      <button onClick={onClose} className="rounded border border-neutral-300 px-4 py-2 text-sm font-medium text-neutral-700">
        Cancel
      </button>
      <button onClick={onSubmit} disabled={disabled} className="rounded bg-primary-800 px-4 py-2 text-sm font-semibold text-white disabled:opacity-40">
        {label}
      </button>
    </div>
  );
}

function ErrorBox({ message }: { message: string }) {
  return <p className="mb-3 rounded border border-status-danger/30 bg-status-dangerLight px-3 py-2 text-sm text-status-danger">{message}</p>;
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="mb-3">
      <label className="mb-1 block text-xs font-semibold uppercase tracking-wide text-neutral-500">{label}</label>
      {children}
    </div>
  );
}
