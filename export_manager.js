(() => {
    const NOTES_STORAGE_KEY = 'tuneTunerNotes';
    const LAST_LYRICS_KEY = 'tuneTunerLastLyrics';
    const LAST_LYRICS_META_KEY = 'tuneTunerLastLyricsMeta';
    const LAST_SONG_DRAFT_KEY = 'tuneTunerLastSongDraft';

    function $(id) {
        return document.getElementById(id);
    }

    function nowStamp() {
        const d = new Date();
        const pad = (n) => String(n).padStart(2, '0');
        return `${d.getFullYear()}${pad(d.getMonth() + 1)}${pad(d.getDate())}_${pad(d.getHours())}${pad(d.getMinutes())}${pad(d.getSeconds())}`;
    }

    function safeJsonParse(text) {
        try {
            return JSON.parse(text);
        } catch (e) {
            return null;
        }
    }

    function getNotesPayload() {
        const raw = localStorage.getItem(NOTES_STORAGE_KEY);
        if (!raw) {
            return { version: 'v1', notes: [], freeformText: '' };
        }
        const parsed = safeJsonParse(raw);
        if (!parsed || typeof parsed !== 'object') {
            return { version: 'v1', notes: [], freeformText: '' };
        }
        if (!Array.isArray(parsed.notes)) parsed.notes = [];
        if (typeof parsed.freeformText !== 'string') parsed.freeformText = '';
        return parsed;
    }

    function notesToTxt(notesPayload) {
        const out = [];
        const notes = Array.isArray(notesPayload.notes) ? notesPayload.notes : [];
        if (notesPayload.freeformText) {
            out.push(notesPayload.freeformText.trim());
            out.push('');
        }
        notes.forEach((n) => {
            const txt = n && n.text ? String(n.text).trim() : '';
            if (!txt) return;
            out.push(txt);
            out.push('');
        });
        return out.join('\n').trim() + '\n';
    }

    function downloadText(filename, text, mime) {
        const blob = new Blob([text], { type: mime || 'text/plain' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        a.remove();
        setTimeout(() => URL.revokeObjectURL(url), 800);
    }

    function downloadJson(filename, obj) {
        const text = JSON.stringify(obj, null, 2);
        downloadText(filename, text, 'application/json');
    }

    async function copyText(text) {
        if (!text) return;
        try {
            if (window.SharedInteractions && typeof window.SharedInteractions.copyToClipboard === 'function') {
                await window.SharedInteractions.copyToClipboard(text);
                return;
            }
        } catch (e) {
        }
        try {
            await navigator.clipboard.writeText(text);
        } catch (e) {
        }
    }

    async function loadClipboardToLyrics() {
        const el = $('ttLyrics');
        if (!el) return;
        try {
            const txt = await navigator.clipboard.readText();
            if (txt) {
                el.value = txt;
                updateLyricsStatus();
            }
        } catch (e) {
        }
    }

    function loadLastDraftToLyrics() {
        const el = $('ttLyrics');
        if (!el) return;
        try {
            const txt = (localStorage.getItem(LAST_LYRICS_KEY) || '').toString();
            if (!txt.trim()) return;
            el.value = txt;
            updateLyricsStatus();
        } catch (e) {
        }
    }

    function getLastDraftMeta() {
        try {
            const raw = localStorage.getItem(LAST_LYRICS_META_KEY);
            if (!raw) return null;
            const parsed = safeJsonParse(raw);
            if (!parsed || typeof parsed !== 'object') return null;
            return parsed;
        } catch (e) {
            return null;
        }
    }

    function getLastSongDraftBundle() {
        try {
            const raw = localStorage.getItem(LAST_SONG_DRAFT_KEY);
            if (!raw) return null;
            const parsed = safeJsonParse(raw);
            if (!parsed || typeof parsed !== 'object') return null;
            return parsed;
        } catch (e) {
            return null;
        }
    }

    function loadLastDraftBundleToLyrics() {
        const bundle = getLastSongDraftBundle();
        if (!bundle || !bundle.lyrics) return;
        const el = $('ttLyrics');
        if (!el) return;
        try {
            const txt = (bundle.lyrics || '').toString();
            if (!txt.trim()) return;
            el.value = txt;
            updateLyricsStatus();
        } catch (e) {
        }
    }

    function formatOutlineTxt(outline) {
        try {
            if (!outline || typeof outline !== 'object') return '';
            const sections = Array.isArray(outline.sections) ? outline.sections : [];
            if (!sections.length) return '';
            const parts = [];
            sections.forEach((s) => {
                if (!s) return;
                const name = s.name ? String(s.name) : 'Section';
                parts.push(name.toUpperCase());
                const bullets = Array.isArray(s.bullets) ? s.bullets : [];
                bullets.forEach((b) => {
                    const t = (b || '').toString().trim();
                    if (t) parts.push(`- ${t}`);
                });
                parts.push('');
            });
            return parts.join('\n').trim();
        } catch (e) {
            return '';
        }
    }

    function getLyrics() {
        const el = $('ttLyrics');
        return el ? (el.value || '') : '';
    }

    function updateNotesStatus() {
        const el = $('ttNotesStatus');
        if (!el) return;
        const payload = getNotesPayload();
        const count = Array.isArray(payload.notes) ? payload.notes.length : 0;
        el.textContent = count === 1 ? '1 item' : `${count} items`;
    }

    function updateLyricsStatus() {
        const el = $('ttLyricsStatus');
        if (!el) return;
        const text = getLyrics();
        const lines = text ? text.split(/\r?\n/).filter((l) => l.trim()).length : 0;
        el.textContent = lines ? `${lines} lines` : 'Paste or load from clipboard';
    }

    async function loadFeatures() {
        try {
            const resp = await fetch('/api/features', { cache: 'no-store' });
            if (!resp.ok) return null;
            return await resp.json();
        } catch (e) {
            return null;
        }
    }

    async function init() {
        const features = await loadFeatures();
        const dbg = $('ttDebug');
        if (!features) {
            if (dbg) dbg.textContent = 'Not staging (or /api/features unavailable).';
            return;
        }

        updateNotesStatus();
        updateLyricsStatus();

        const notesJsonBtn = $('ttExportNotesJson');
        const notesTxtBtn = $('ttExportNotesTxt');
        const copyNotesJsonBtn = $('ttCopyNotesJson');

        const lyricsJsonBtn = $('ttExportLyricsJson');
        const lyricsTxtBtn = $('ttExportLyricsTxt');
        const copyLyricsBtn = $('ttCopyLyrics');
        const loadLastDraftBtn = $('ttLoadLastDraft');
        const loadLastDraftBundleBtn = $('ttLoadLastDraftBundle');
        const loadClipboardBtn = $('ttLoadClipboard');
        const clearLyricsBtn = $('ttClearLyrics');

        const bundleJsonBtn = $('ttExportBundleJson');
        const bundleTxtBtn = $('ttExportBundleTxt');

        if (notesJsonBtn) {
            notesJsonBtn.onclick = () => {
                const payload = getNotesPayload();
                downloadJson(`tune_tuner_notes_${nowStamp()}.json`, payload);
            };
        }
        if (notesTxtBtn) {
            notesTxtBtn.onclick = () => {
                const payload = getNotesPayload();
                downloadText(`tune_tuner_notes_${nowStamp()}.txt`, notesToTxt(payload), 'text/plain');
            };
        }
        if (copyNotesJsonBtn) {
            copyNotesJsonBtn.onclick = async () => {
                const payload = getNotesPayload();
                await copyText(JSON.stringify(payload, null, 2));
            };
        }

        if (lyricsJsonBtn) {
            lyricsJsonBtn.onclick = () => {
                const text = getLyrics();
                downloadJson(`tune_tuner_lyrics_${nowStamp()}.json`, { lyrics: text });
            };
        }
        if (lyricsTxtBtn) {
            lyricsTxtBtn.onclick = () => {
                const text = getLyrics();
                downloadText(`tune_tuner_lyrics_${nowStamp()}.txt`, (text || '').toString(), 'text/plain');
            };
        }
        if (copyLyricsBtn) {
            copyLyricsBtn.onclick = async () => {
                await copyText(getLyrics());
            };
        }
        if (loadClipboardBtn) {
            loadClipboardBtn.onclick = loadClipboardToLyrics;
        }
        if (loadLastDraftBtn) {
            loadLastDraftBtn.onclick = () => {
                loadLastDraftToLyrics();
            };
        }
        if (loadLastDraftBundleBtn) {
            loadLastDraftBundleBtn.onclick = () => {
                loadLastDraftBundleToLyrics();
            };
        }
        if (clearLyricsBtn) {
            clearLyricsBtn.onclick = () => {
                const el = $('ttLyrics');
                if (el) {
                    el.value = '';
                    updateLyricsStatus();
                }
            };
        }

        if (bundleJsonBtn) {
            bundleJsonBtn.onclick = () => {
                const payload = {
                    exported_at: new Date().toISOString(),
                    notes: getNotesPayload(),
                    lyrics: getLyrics(),
                    last_song_draft: getLastSongDraftBundle()
                };
                downloadJson(`tune_tuner_bundle_${nowStamp()}.json`, payload);
            };
        }
        if (bundleTxtBtn) {
            bundleTxtBtn.onclick = () => {
                const parts = [];
                parts.push('NOTES');
                parts.push('-----');
                parts.push(notesToTxt(getNotesPayload()).trim());
                parts.push('');

                const lastBundle = getLastSongDraftBundle();
                if (lastBundle && (lastBundle.metadata || lastBundle.outline)) {
                    parts.push('LAST SONG DRAFT');
                    parts.push('--------------');
                    try {
                        if (lastBundle.metadata && typeof lastBundle.metadata === 'object') {
                            const m = lastBundle.metadata;
                            if (m.theme) parts.push(`theme: ${m.theme}`);
                            if (m.tone) parts.push(`tone: ${m.tone}`);
                            if (m.structure) parts.push(`structure: ${m.structure}`);
                        }
                    } catch (e) {
                    }
                    const outlineTxt = formatOutlineTxt(lastBundle.outline);
                    if (outlineTxt) {
                        parts.push('');
                        parts.push('OUTLINE');
                        parts.push('-------');
                        parts.push(outlineTxt);
                    }
                    parts.push('');
                }

                parts.push('LYRICS');
                parts.push('------');
                parts.push((getLyrics() || '').toString().trim());
                parts.push('');
                downloadText(`tune_tuner_bundle_${nowStamp()}.txt`, parts.join('\n'), 'text/plain');
            };
        }

        const lyricsEl = $('ttLyrics');
        if (lyricsEl) {
            lyricsEl.addEventListener('input', updateLyricsStatus);
        }

        if (dbg) {
            const meta = getLastDraftMeta();
            const bundle = getLastSongDraftBundle();
            const metaBits = [];
            if (meta && meta.savedAt) {
                try {
                    metaBits.push(`last_draft=${new Date(Number(meta.savedAt)).toLocaleString()}`);
                } catch (e) {
                }
            }
            if (meta && meta.theme) metaBits.push(`theme=${meta.theme}`);
            if (meta && meta.tone) metaBits.push(`tone=${meta.tone}`);
            if (bundle && bundle.outline) metaBits.push('outline=1');
            dbg.textContent = `environment=${features.environment || 'unknown'} • export_manager=${String(!!(features.features && features.features.export_manager))}${metaBits.length ? ' • ' + metaBits.join(' • ') : ''}`;
        }
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
