'use client';

import { Copy, FileText, Film, Image as ImageIcon, Music, Trash2, Upload } from 'lucide-react';
import { useCallback, useEffect, useRef, useState } from 'react';

import { Badge, Button, Card, EmptyState } from '@hietedu/ui';

import { AdminShell } from '@/components/admin/admin-shell';
import { ConfirmDialog, Modal } from '@/components/admin/dialog';
import { FormRow, TextAreaField, TextField, useEnumLabel } from '@/components/admin/form';
import { useToast } from '@/components/admin/toast';
import { API_BASE } from '@/lib/api';
import { adminApi, type MediaAsset, type MediaKind } from '@/lib/admin-api';
import { useRequireAuth } from '@/lib/auth';
import { useI18n } from '@/lib/i18n';

const KINDS: MediaKind[] = ['image', 'document', 'video', 'audio'];

const ICONS = {
  image: ImageIcon,
  document: FileText,
  video: Film,
  audio: Music,
};

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

/** Uploaded files are served relative to the API host, not the web app. */
function absoluteUrl(url: string): string {
  return url.startsWith('http') ? url : `${API_BASE}${url}`;
}

export default function MediaPage() {
  const { t, locale, formatDate } = useI18n();
  const enumLabel = useEnumLabel();
  const { user, loading: authLoading } = useRequireAuth(locale, ['admin']);
  const { run, notify } = useToast();
  const fileInput = useRef<HTMLInputElement>(null);

  const [rows, setRows] = useState<MediaAsset[]>([]);
  const [meta, setMeta] = useState({ total: 0, page: 1, pages: 0 });
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(1);
  const [kind, setKind] = useState<MediaKind | ''>('');
  const [search, setSearch] = useState('');
  const [uploading, setUploading] = useState(false);
  const [stats, setStats] = useState<Record<string, any> | null>(null);
  const [editing, setEditing] = useState<MediaAsset | null>(null);
  const [deleting, setDeleting] = useState<MediaAsset | null>(null);
  const [usage, setUsage] = useState<{ in_use: boolean; lessons: { id: number; title: string }[] } | null>(
    null,
  );

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [result, statResult] = await Promise.all([
        adminApi.media.list({ page, kind: kind || undefined, search }),
        adminApi.media.stats(),
      ]);
      setRows(result.items);
      setMeta({ total: result.total, page: result.page, pages: result.pages });
      setStats(statResult);
    } catch (caught) {
      notify((caught as Error).message, 'error');
    } finally {
      setLoading(false);
    }
  }, [page, kind, search, notify]);

  useEffect(() => {
    if (user) void load();
  }, [user, load]);

  async function upload(files: FileList | null) {
    if (!files?.length) return;
    setUploading(true);
    let uploaded = 0;
    for (const file of Array.from(files)) {
      const result = await run(() => adminApi.media.upload(file));
      if (result) {
        uploaded += 1;
        if (result.deduplicated) {
          notify(t('admin.med.alreadyExists', { name: file.name }), 'info');
        }
      }
    }
    setUploading(false);
    if (uploaded) {
      notify(t('admin.med.uploaded', { count: uploaded }), 'success');
      await load();
    }
  }

  if (authLoading || !user) return <AdminShell loading />;

  return (
    <AdminShell
      title={t('admin.med.title')}
      description={t('admin.med.subtitle')}
      breadcrumbs={[{ label: t('admin.a.adminCrumb'), href: '/admin' }, { label: t('admin.blk.group.Media') }]}
      actions={
        <>
          <input
            ref={fileInput}
            type="file"
            multiple
            className="sr-only"
            onChange={(event) => {
              void upload(event.target.files);
              event.target.value = '';
            }}
          />
          <Button loading={uploading} onClick={() => fileInput.current?.click()}>
            <Upload className="h-4 w-4" aria-hidden="true" />{t('admin.med.upload')}</Button>
        </>
      }
    >
      {stats && (
        <Card className="mb-4 flex flex-wrap items-center gap-4 p-3 text-sm">
          <span className="font-bold">
            {t('admin.med.fileCount', { count: Number(stats.total_files ?? 0) })}
          </span>
          <span className="text-ink-500">{formatBytes(Number(stats.total_bytes ?? 0))}</span>
          <span className="ml-auto text-xs text-ink-500">
            {t('admin.med.allowed', {
              list: (stats.allowed_extensions as string[])?.join(' ') ?? '',
            })}
          </span>
        </Card>
      )}

      <div className="mb-4 flex flex-wrap items-center gap-2">
        <input
          type="search"
          value={search}
          onChange={(event) => {
            setSearch(event.target.value);
            setPage(1);
          }}
          placeholder={t('admin.med.searchFiles')}
          aria-label={t('admin.med.searchFilesLabel')}
          className="min-w-0 flex-1 rounded-xl border-2 border-ink-200 px-3 py-2 text-sm outline-none focus:border-brand-400 sm:max-w-xs"
        />
        <button
          type="button"
          onClick={() => setKind('')}
          className={`rounded-full border-2 px-3 py-1 text-xs font-bold ${
            kind === '' ? 'border-brand-500 bg-brand-500 text-white' : 'border-ink-200'
          }`}
        >{t('admin.a.all')}</button>
        {KINDS.map((value) => (
          <button
            key={value}
            type="button"
            onClick={() => {
              setKind(value);
              setPage(1);
            }}
            className={`rounded-full border-2 px-3 py-1 text-xs font-bold ${
              kind === value ? 'border-brand-500 bg-brand-500 text-white' : 'border-ink-200'
            }`}
          >
            {enumLabel(value)}
          </button>
        ))}
      </div>

      <div
        onDragOver={(event) => event.preventDefault()}
        onDrop={(event) => {
          event.preventDefault();
          void upload(event.dataTransfer.files);
        }}
      >
        {loading ? (
          <p className="py-16 text-center text-sm text-ink-500">{t('admin.a.loading')}</p>
        ) : rows.length === 0 ? (
          <EmptyState
            title={t('admin.med.empty')}
            description={t('admin.med.emptyBody')}
            action={
              <Button onClick={() => fileInput.current?.click()}>
                <Upload className="h-4 w-4" aria-hidden="true" />{t('admin.med.upload')}</Button>
            }
          />
        ) : (
          <ul className="grid gap-3 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5">
            {rows.map((asset) => {
              const Icon = ICONS[asset.kind] ?? FileText;
              return (
                <li key={asset.id}>
                  <Card className="flex h-full flex-col p-3">
                    <div className="mb-2 flex h-28 items-center justify-center overflow-hidden rounded-xl bg-ink-50">
                      {asset.kind === 'image' ? (
                        /* eslint-disable-next-line @next/next/no-img-element */
                        <img
                          src={absoluteUrl(asset.url)}
                          alt={asset.alt_text ?? asset.original_name}
                          className="h-full w-full object-cover"
                        />
                      ) : (
                        <Icon className="h-10 w-10 text-ink-300" aria-hidden="true" />
                      )}
                    </div>
                    <p className="truncate text-sm font-bold" title={asset.original_name}>
                      {asset.title || asset.original_name}
                    </p>
                    <p className="text-xs text-ink-500">
                      {formatBytes(asset.size_bytes)}
                      {asset.width ? ` · ${asset.width}×${asset.height}` : ''}
                    </p>
                    <p className="mt-0.5 text-xs text-ink-400">{formatDate(asset.created_at)}</p>
                    <div className="mt-auto flex items-center gap-1 pt-2">
                      <button
                        type="button"
                        aria-label={t('admin.med.copyAria', { name: asset.original_name })}
                        onClick={() => {
                          void navigator.clipboard.writeText(asset.url);
                          notify(t('admin.a.urlCopied'), 'success');
                        }}
                        className="rounded-lg p-1.5 text-ink-500 hover:bg-ink-100"
                      >
                        <Copy className="h-4 w-4" aria-hidden="true" />
                      </button>
                      <button
                        type="button"
                        onClick={() => setEditing(asset)}
                        className="rounded-lg px-2 py-1 text-xs font-bold text-brand-600 hover:bg-brand-50"
                      >{t('admin.a.details')}</button>
                      <button
                        type="button"
                        aria-label={t('admin.a.deleteAria', { name: asset.original_name })}
                        onClick={async () => {
                          const result = await run(() => adminApi.media.usage(asset.id));
                          setUsage(result ?? null);
                          setDeleting(asset);
                        }}
                        className="ml-auto rounded-lg p-1.5 text-coral-500 hover:bg-coral-50"
                      >
                        <Trash2 className="h-4 w-4" aria-hidden="true" />
                      </button>
                    </div>
                  </Card>
                </li>
              );
            })}
          </ul>
        )}
      </div>

      {meta.pages > 1 && (
        <div className="mt-4 flex items-center justify-center gap-3">
          <Button size="sm" variant="outline" disabled={page <= 1} onClick={() => setPage(page - 1)}>{t('admin.a.previous')}</Button>
          <span className="text-xs font-semibold">
            Page {meta.page} of {meta.pages}
          </span>
          <Button
            size="sm"
            variant="outline"
            disabled={page >= meta.pages}
            onClick={() => setPage(page + 1)}
          >{t('admin.a.next')}</Button>
        </div>
      )}

      <Modal
        open={editing !== null}
        onClose={() => setEditing(null)}
        title={editing?.original_name ?? 'File'}
        footer={
          <>
            <Button variant="ghost" onClick={() => setEditing(null)}>{t('admin.a.close')}</Button>
            <Button
              onClick={async () => {
                if (!editing) return;
                const ok = await run(
                  () =>
                    adminApi.media.update(editing.id, {
                      title: editing.title,
                      alt_text: editing.alt_text,
                      description: editing.description,
                    }),
                  t('admin.a.saved'),
                );
                if (ok) {
                  setEditing(null);
                  await load();
                }
              }}
            >{t('admin.a.save')}</Button>
          </>
        }
      >
        {editing && (
          <div className="space-y-4">
            {editing.kind === 'image' && (
              /* eslint-disable-next-line @next/next/no-img-element */
              <img
                src={absoluteUrl(editing.url)}
                alt={editing.alt_text ?? ''}
                className="max-h-64 w-full rounded-2xl object-contain"
              />
            )}
            <FormRow label={t('admin.a.url')} hint={t('admin.med.urlHint')}>
              <TextField readOnly value={editing.url} className="font-mono text-xs" />
            </FormRow>
            <FormRow label={t('admin.a.title')} htmlFor="m-title">
              <TextField
                id="m-title"
                value={editing.title ?? ''}
                onChange={(e) => setEditing({ ...editing, title: e.target.value })}
              />
            </FormRow>
            <FormRow
              label={t('admin.med.altTextLabel')}
              htmlFor="m-alt"
              hint={t('admin.med.altHint')}
            >
              <TextField
                id="m-alt"
                value={editing.alt_text ?? ''}
                onChange={(e) => setEditing({ ...editing, alt_text: e.target.value })}
              />
            </FormRow>
            <FormRow label={t('admin.a.description')} htmlFor="m-desc">
              <TextAreaField
                id="m-desc"
                value={editing.description ?? ''}
                onChange={(e) => setEditing({ ...editing, description: e.target.value })}
              />
            </FormRow>
            <div className="flex flex-wrap gap-2 text-xs text-ink-500">
              <Badge tone="neutral">{enumLabel(editing.kind)}</Badge>
              <span>{editing.content_type}</span>
              <span>{formatBytes(editing.size_bytes)}</span>
            </div>
          </div>
        )}
      </Modal>

      <ConfirmDialog
        open={deleting !== null}
        onClose={() => {
          setDeleting(null);
          setUsage(null);
        }}
        title={t('admin.a.deleteQ', { name: deleting?.original_name ?? '' })}
        message={
          usage?.in_use ? (
            <>
              {t('admin.med.inUse', { count: usage.lessons.length })}
              <ul className="mt-2 list-disc pl-5">
                {usage.lessons.slice(0, 5).map((lesson) => (
                  <li key={lesson.id}>{lesson.title}</li>
                ))}
              </ul>
            </>
          ) : (
            t('admin.med.deleteBody')
          )
        }
        onConfirm={async () => {
          if (!deleting) return;
          const ok = await run(
            () => adminApi.media.remove(deleting.id, usage?.in_use ?? false),
            t('admin.med.deletedToast'),
          );
          if (ok !== undefined) {
            setUsage(null);
            await load();
          }
        }}
      />
    </AdminShell>
  );
}
