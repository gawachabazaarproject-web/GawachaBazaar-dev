"use client";

import React, { useCallback, useEffect, useState, useRef } from "react";
import { useAuth } from "@/lib/auth-context";
import {
  AD_IMAGE,
  AdApiError,
  AdminAdListItem,
  createAd,
  deleteAd,
  fetchAds,
  replaceAdImage,
  updateAd,
  validateAdImage,
} from "@/lib/ads";
import { ImageDropzone } from "@/components/ImageDropzone";
import { formatDate } from "@/lib/format";
import { PageHeader } from "@/components/PageHeader";
import { EmptyState } from "@/components/EmptyState";
import { TableSkeleton } from "@/components/TableSkeleton";
import { StatusBadge } from "@/components/StatusBadge";

export default function AdsPage() {
  const { getAccessToken } = useAuth();
  const [ads, setAds] = useState<AdminAdListItem[] | null>(null);
  const [loading, setLoading] = useState(true);
  // After the first load, refreshes are silent so the page does not blank out.
  const loadedOnce = useRef(false);
  const [error, setError] = useState<string | null>(null);
  const [addOpen, setAddOpen] = useState(false);
  const [editing, setEditing] = useState<AdminAdListItem | null>(null);
  const [rowBusy, setRowBusy] = useState<number | null>(null);

  const load = useCallback(async () => {
    const token = getAccessToken();
    if (!token) return;
    if (!loadedOnce.current) setLoading(true); // refreshes after an edit stay in place
    setError(null);
    try {
      setAds(await fetchAds(token));
    } catch (err) {
      setError(err instanceof AdApiError ? err.message : "Unable to load ads.");
    } finally {
      setLoading(false);
      loadedOnce.current = true;
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const withRowBusy = async (id: number, action: () => Promise<void>) => {
    setRowBusy(id);
    try {
      await action();
      await load();
    } catch (err) {
      setError(err instanceof AdApiError ? err.message : "Something went wrong.");
    } finally {
      setRowBusy(null);
    }
  };

  const handleToggleStatus = (ad: AdminAdListItem) => {
    const next = ad.status === "ACTIVE" ? "INACTIVE" : "ACTIVE";
    void withRowBusy(ad.id, async () => {
      const token = getAccessToken();
      if (!token) return;
      await updateAd(token, ad.id, { status: next });
    });
  };

  const handleDelete = (ad: AdminAdListItem) => {
    if (!confirm(`Delete the "${ad.brand_name}" ad? This can't be undone.`)) return;
    void withRowBusy(ad.id, async () => {
      const token = getAccessToken();
      if (!token) return;
      await deleteAd(token, ad.id);
    });
  };

  const handleReplaceImage = (ad: AdminAdListItem, file: File) =>
    withRowBusy(ad.id, async () => {
      const token = getAccessToken();
      if (!token) return;
      await replaceAdImage(token, ad.id, file);
    });

  return (
    <div>
      <PageHeader
        eyebrow="Marketing"
        title="Ads"
        description={`Brand-advertising cards shown in the mobile app's ads carousel. Upload images at exactly ${AD_IMAGE.width} x ${AD_IMAGE.height} px (${AD_IMAGE.ratioLabel}) so nothing is cropped. One ad stays still; two or more slide automatically.`}
        actions={
          <button
            onClick={() => setAddOpen(true)}
            className="rounded bg-primary-800 px-4 py-2 text-sm font-semibold text-white hover:bg-primary-700"
          >
            + Add ad
          </button>
        }
      />

      {error && (
        <p className="mb-4 rounded border border-status-danger/30 bg-status-dangerLight px-3 py-2 text-sm text-status-danger">
          {error}
        </p>
      )}

      <div className="overflow-hidden rounded border border-neutral-200 bg-white">
        {loading ? (
          <TableSkeleton rows={4} columns={5} />
        ) : !ads || ads.length === 0 ? (
          <EmptyState
            icon="megaphone"
            title="No ads yet"
            message="Add a brand's creative to start showing it in the mobile app's ads carousel."
            action={
              <button
                onClick={() => setAddOpen(true)}
                className="rounded bg-primary-800 px-4 py-2 text-sm font-semibold text-white hover:bg-primary-700"
              >
                + Add ad
              </button>
            }
          />
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-neutral-200 bg-neutral-50 text-left text-xs font-semibold uppercase tracking-wide text-neutral-500">
                <th className="px-4 py-3">Creative</th>
                <th className="px-4 py-3">Brand</th>
                <th className="px-4 py-3">Link</th>
                <th className="px-4 py-3">Order</th>
                <th className="px-4 py-3">Status</th>
                <th className="px-4 py-3">Added</th>
                <th className="px-4 py-3"></th>
              </tr>
            </thead>
            <tbody className="divide-y divide-neutral-100">
              {ads.map((ad) => {
                const busy = rowBusy === ad.id;
                return (
                  <tr key={ad.id} className={busy ? "opacity-50" : undefined}>
                    <td className="px-4 py-3">
                      {/* eslint-disable-next-line @next/next/no-img-element */}
                      <img src={ad.image_url} alt={ad.brand_name} className="aspect-[12/5] w-28 rounded object-cover" />
                    </td>
                    <td className="px-4 py-3 font-medium text-primary-900">{ad.brand_name}</td>
                    <td className="max-w-[220px] truncate px-4 py-3 text-neutral-500">
                      {ad.link_url ?? <span className="text-neutral-300">No link</span>}
                    </td>
                    <td className="px-4 py-3 text-neutral-500">{ad.display_order}</td>
                    <td className="px-4 py-3">
                      <StatusBadge status={ad.status} />
                    </td>
                    <td className="px-4 py-3 text-neutral-500">{formatDate(ad.created_at)}</td>
                    <td className="px-4 py-3">
                      <div className="flex justify-end gap-3 text-xs font-semibold">
                        <button
                          disabled={busy}
                          onClick={() => setEditing(ad)}
                          className="text-neutral-500 hover:text-primary-700 hover:underline disabled:opacity-40"
                        >
                          Edit
                        </button>
                        <button
                          disabled={busy}
                          onClick={() => handleToggleStatus(ad)}
                          className="text-neutral-500 hover:text-primary-700 hover:underline disabled:opacity-40"
                        >
                          {ad.status === "ACTIVE" ? "Deactivate" : "Activate"}
                        </button>
                        <button
                          disabled={busy}
                          onClick={() => handleDelete(ad)}
                          className="text-status-danger hover:underline disabled:opacity-40"
                        >
                          Delete
                        </button>
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </div>

      {addOpen && (
        <AddAdDialog
          onClose={() => setAddOpen(false)}
          onCreated={() => {
            setAddOpen(false);
            load();
          }}
        />
      )}

      {editing && (
        <EditAdDialog
          ad={editing}
          onClose={() => setEditing(null)}
          onSaved={() => {
            setEditing(null);
            load();
          }}
          onReplaceImage={(file) => handleReplaceImage(editing, file)}
        />
      )}
    </div>
  );
}

function AddAdDialog({ onClose, onCreated }: { onClose: () => void; onCreated: () => void }) {
  const { getAccessToken } = useAuth();
  const [brandName, setBrandName] = useState("");
  const [linkUrl, setLinkUrl] = useState("");
  const [title, setTitle] = useState("");
  const [subtitle, setSubtitle] = useState("");
  const [displayOrder, setDisplayOrder] = useState("0");
  const [file, setFile] = useState<File | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleFilePick = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const picked = e.target.files?.[0];
    e.target.value = "";
    if (!picked) return;
    const problem = await validateAdImage(picked);
    if (problem) {
      setFile(null);
      setPreviewUrl(null);
      setError(problem);
      return;
    }
    setError(null);
    setFile(picked);
    setPreviewUrl(URL.createObjectURL(picked));
  };

  const handleSubmit = async () => {
    const token = getAccessToken();
    if (!token || !brandName || !file) return;
    setSaving(true);
    setError(null);
    try {
      await createAd(token, {
        brand_name: brandName,
        link_url: linkUrl || undefined,
        title: title.trim() || undefined,
        subtitle: subtitle.trim() || undefined,
        display_order: Number(displayOrder) || 0,
        file,
      });
      onCreated();
    } catch (err) {
      setError(err instanceof AdApiError ? err.message : "Unable to create ad.");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 px-4">
      <div className="w-full max-w-md rounded bg-white p-6 shadow-xl">
        <h2 className="mb-4 font-display text-lg font-semibold text-primary-900">Add ad</h2>

        <Field label="Brand name">
          <input value={brandName} onChange={(e) => setBrandName(e.target.value)} className="w-full rounded border border-neutral-300 px-3 py-2 text-sm" />
        </Field>
        <Field label="Link URL (optional)">
          <input
            value={linkUrl}
            onChange={(e) => setLinkUrl(e.target.value)}
            placeholder="https://..."
            className="w-full rounded border border-neutral-300 px-3 py-2 text-sm"
          />
        </Field>
        <Field label="Card title (optional)">
          <input value={title} onChange={(e) => setTitle(e.target.value)} maxLength={80} placeholder="Shown on the card, e.g. Fresh this week" className="w-full rounded border border-neutral-300 px-3 py-2 text-sm" />
        </Field>
        <Field label="Card subtitle (optional)">
          <input value={subtitle} onChange={(e) => setSubtitle(e.target.value)} maxLength={140} placeholder="One short line under the title" className="w-full rounded border border-neutral-300 px-3 py-2 text-sm" />
        </Field>
        <Field label="Display order">
          <input
            type="number"
            value={displayOrder}
            onChange={(e) => setDisplayOrder(e.target.value)}
            className="w-full rounded border border-neutral-300 px-3 py-2 text-sm"
          />
        </Field>
        <Field label="Creative image">
          <p className="mb-2 rounded bg-primary-50 px-3 py-2 text-xs text-primary-900">
            Required size: <strong>{AD_IMAGE.width} x {AD_IMAGE.height} px</strong> ({AD_IMAGE.ratioLabel}, wide banner). JPG, PNG or WebP, up to 8 MB.
            Keep logos and important text away from the bottom edge - the title and subtitle sit there.
          </p>
          <label className="flex min-h-[110px] cursor-pointer flex-col items-center justify-center gap-2 rounded border-2 border-dashed border-neutral-300 bg-neutral-50 p-4 text-center hover:border-primary-400">
            {previewUrl ? (
              // eslint-disable-next-line @next/next/no-img-element
              <img src={previewUrl} alt="" className="aspect-[12/5] w-full rounded object-cover" />
            ) : (
              <p className="text-sm text-neutral-500">Click to choose a {AD_IMAGE.width} x {AD_IMAGE.height} image</p>
            )}
            <input type="file" accept="image/jpeg,image/png,image/webp,image/gif" className="hidden" onChange={handleFilePick} />
          </label>
        </Field>

        {error && <p className="mb-3 rounded border border-status-danger/30 bg-status-dangerLight px-3 py-2 text-sm text-status-danger">{error}</p>}

        <div className="mt-4 flex justify-end gap-2">
          <button onClick={onClose} className="rounded border border-neutral-300 px-4 py-2 text-sm font-medium text-neutral-700">
            Cancel
          </button>
          <button
            onClick={handleSubmit}
            disabled={saving || !brandName || !file}
            className="rounded bg-primary-800 px-4 py-2 text-sm font-semibold text-white disabled:opacity-40"
          >
            {saving ? "Creating..." : "Create ad"}
          </button>
        </div>
      </div>
    </div>
  );
}

function EditAdDialog({
  ad,
  onClose,
  onSaved,
  onReplaceImage,
}: {
  ad: AdminAdListItem;
  onClose: () => void;
  onSaved: () => void;
  onReplaceImage: (file: File) => Promise<void>;
}) {
  const { getAccessToken } = useAuth();
  const [brandName, setBrandName] = useState(ad.brand_name);
  const [linkUrl, setLinkUrl] = useState(ad.link_url ?? "");
  const [title, setTitle] = useState(ad.title ?? "");
  const [subtitle, setSubtitle] = useState(ad.subtitle ?? "");
  const [displayOrder, setDisplayOrder] = useState(String(ad.display_order));
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSave = async () => {
    const token = getAccessToken();
    if (!token) return;
    setSaving(true);
    setError(null);
    try {
      await updateAd(token, ad.id, {
        brand_name: brandName,
        link_url: linkUrl,
        title,
        subtitle,
        display_order: Number(displayOrder) || 0,
      });
      onSaved();
    } catch (err) {
      setError(err instanceof AdApiError ? err.message : "Unable to save changes.");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 px-4">
      <div className="w-full max-w-md rounded bg-white p-6 shadow-xl">
        <h2 className="mb-4 font-display text-lg font-semibold text-primary-900">Edit ad</h2>

        <Field label="Creative image">
          <ImageDropzone
            currentUrl={ad.image_url}
            onUpload={onReplaceImage}
            validate={validateAdImage}
            hint={`${AD_IMAGE.width} x ${AD_IMAGE.height} px (${AD_IMAGE.ratioLabel}) · JPG, PNG or WebP · up to 8 MB`}
          />
          <p className="mt-1 text-xs text-neutral-500">
            Required size: {AD_IMAGE.width} x {AD_IMAGE.height} px ({AD_IMAGE.ratioLabel}) so nothing is cropped.
          </p>
        </Field>
        <Field label="Card title (optional)">
          <input value={title} onChange={(e) => setTitle(e.target.value)} maxLength={80} className="w-full rounded border border-neutral-300 px-3 py-2 text-sm" />
        </Field>
        <Field label="Card subtitle (optional)">
          <input value={subtitle} onChange={(e) => setSubtitle(e.target.value)} maxLength={140} className="w-full rounded border border-neutral-300 px-3 py-2 text-sm" />
        </Field>
        <Field label="Brand name">
          <input value={brandName} onChange={(e) => setBrandName(e.target.value)} className="w-full rounded border border-neutral-300 px-3 py-2 text-sm" />
        </Field>
        <Field label="Link URL">
          <input
            value={linkUrl}
            onChange={(e) => setLinkUrl(e.target.value)}
            placeholder="https://..."
            className="w-full rounded border border-neutral-300 px-3 py-2 text-sm"
          />
        </Field>
        <Field label="Display order">
          <input
            type="number"
            value={displayOrder}
            onChange={(e) => setDisplayOrder(e.target.value)}
            className="w-full rounded border border-neutral-300 px-3 py-2 text-sm"
          />
        </Field>

        {error && <p className="mb-3 rounded border border-status-danger/30 bg-status-dangerLight px-3 py-2 text-sm text-status-danger">{error}</p>}

        <div className="mt-4 flex justify-end gap-2">
          <button onClick={onClose} className="rounded border border-neutral-300 px-4 py-2 text-sm font-medium text-neutral-700">
            Cancel
          </button>
          <button
            onClick={handleSave}
            disabled={saving || !brandName}
            className="rounded bg-primary-800 px-4 py-2 text-sm font-semibold text-white disabled:opacity-40"
          >
            {saving ? "Saving..." : "Save changes"}
          </button>
        </div>
      </div>
    </div>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="mb-3">
      <label className="mb-1 block text-xs font-semibold uppercase tracking-wide text-neutral-500">{label}</label>
      {children}
    </div>
  );
}
