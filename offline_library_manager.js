(() => {
    const CACHE_DB = 'MetaphorGymCache';
    const QUEUE_DB = 'TuneTunerOfflineQueue';

    function $(id) {
        return document.getElementById(id);
    }

    function formatBytes(bytes) {
        const b = Number(bytes || 0);
        if (!isFinite(b) || b <= 0) return '0 B';
        const units = ['B', 'KB', 'MB', 'GB'];
        let v = b;
        let idx = 0;
        while (v >= 1024 && idx < units.length - 1) {
            v /= 1024;
            idx += 1;
        }
        const out = idx === 0 ? String(Math.round(v)) : v.toFixed(1);
        return `${out} ${units[idx]}`;
    }

    async function openDb(name) {
        return new Promise((resolve, reject) => {
            const req = indexedDB.open(name);
            req.onsuccess = () => resolve(req.result);
            req.onerror = () => reject(req.error);
        });
    }

    async function listStores(db) {
        try {
            return Array.from(db.objectStoreNames || []);
        } catch (e) {
            return [];
        }
    }

    async function estimateStore(db, storeName) {
        return new Promise((resolve) => {
            let totalBytes = 0;
            let count = 0;
            try {
                const tx = db.transaction([storeName], 'readonly');
                const store = tx.objectStore(storeName);
                const req = store.getAll();
                req.onsuccess = () => {
                    const rows = req.result || [];
                    count = rows.length;
                    try {
                        for (const r of rows) {
                            totalBytes += new Blob([JSON.stringify(r || {})]).size;
                        }
                    } catch (e) {
                    }
                    resolve({ count, totalBytes });
                };
                req.onerror = () => resolve({ count: 0, totalBytes: 0 });
            } catch (e) {
                resolve({ count: 0, totalBytes: 0 });
            }
        });
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

    async function refreshStorageEstimate() {
        const usageEl = $('ttUsage');
        const quotaEl = $('ttQuota');
        const pctEl = $('ttUsagePct');

        if (!navigator.storage || !navigator.storage.estimate) {
            usageEl.textContent = 'Not supported';
            quotaEl.textContent = 'Not supported';
            pctEl.textContent = '—';
            return;
        }

        try {
            const est = await navigator.storage.estimate();
            const usage = est && est.usage ? est.usage : 0;
            const quota = est && est.quota ? est.quota : 0;
            usageEl.textContent = formatBytes(usage);
            quotaEl.textContent = formatBytes(quota);
            const pct = quota > 0 ? Math.min(100, Math.round((usage / quota) * 100)) : 0;
            pctEl.textContent = quota > 0 ? `${pct}%` : '—';
        } catch (e) {
            usageEl.textContent = 'Error';
            quotaEl.textContent = 'Error';
            pctEl.textContent = '—';
        }
    }

    function renderCacheRow(storeName, stats) {
        const row = document.createElement('div');
        row.className = 'row';

        const left = document.createElement('div');
        left.className = 'row-left';

        const label = document.createElement('div');
        label.className = 'label';
        label.textContent = storeName;

        const meta = document.createElement('div');
        meta.className = 'meta';
        meta.textContent = `${stats.count} items • ~${formatBytes(stats.totalBytes)}`;

        left.appendChild(label);
        left.appendChild(meta);

        const badge = document.createElement('div');
        badge.className = 'badge';
        badge.textContent = stats.count > 0 ? 'Cached' : 'Empty';

        row.appendChild(left);
        row.appendChild(badge);
        return row;
    }

    async function refreshCacheInfo() {
        const list = $('ttCacheList');
        const status = $('ttCacheStatus');
        list.innerHTML = '';

        try {
            const db = await openDb(CACHE_DB);
            const stores = await listStores(db);
            if (!stores.length) {
                status.textContent = 'No stores';
                const p = document.createElement('div');
                p.className = 'muted';
                p.textContent = 'Cache DB has no object stores.';
                list.appendChild(p);
                return;
            }

            let totalItems = 0;
            for (const s of stores) {
                const st = await estimateStore(db, s);
                totalItems += st.count;
                list.appendChild(renderCacheRow(s, st));
            }

            status.textContent = `${stores.length} stores • ${totalItems} items`;
        } catch (e) {
            status.textContent = 'Unavailable';
            const p = document.createElement('div');
            p.className = 'muted';
            p.textContent = 'Unable to open cache DB.';
            list.appendChild(p);
        }
    }

    function renderQueueRow(item) {
        const row = document.createElement('div');
        row.className = 'row';

        const left = document.createElement('div');
        left.className = 'row-left';

        const label = document.createElement('div');
        label.className = 'label';
        const method = (item && item.method ? item.method : 'POST').toUpperCase();
        const url = item && item.url ? String(item.url) : '';
        label.textContent = `${method} ${url}`;

        const meta = document.createElement('div');
        meta.className = 'meta';
        const createdAt = item && item.createdAt ? Number(item.createdAt) : 0;
        const ageSec = createdAt ? Math.max(0, Math.round((Date.now() - createdAt) / 1000)) : 0;
        const status = item && item.status ? String(item.status) : 'queued';
        const attempts = item && item.attempts ? Number(item.attempts) : 0;
        const nextAttemptAt = item && item.nextAttemptAt ? Number(item.nextAttemptAt) : 0;
        const nextInSec = nextAttemptAt ? Math.max(0, Math.round((nextAttemptAt - Date.now()) / 1000)) : 0;
        const lastError = item && item.lastError ? item.lastError : null;
        const errMsg = lastError && lastError.message ? String(lastError.message) : '';
        const errType = lastError && lastError.type ? String(lastError.type) : '';
        const errStatus = lastError && typeof lastError.status !== 'undefined' ? String(lastError.status) : '';
        const errSummary = errMsg ? `${errType || 'error'}${errStatus ? ' ' + errStatus : ''}: ${errMsg}` : '';
        const bits = [];
        bits.push(item && item.id ? `id=${item.id}` : '');
        bits.push(`age=${ageSec}s`);
        bits.push(`status=${status}`);
        bits.push(`attempts=${attempts}`);
        if (nextAttemptAt) bits.push(`next=${nextInSec}s`);
        if (errSummary) bits.push(errSummary.slice(0, 120));
        meta.textContent = bits.filter(Boolean).join(' • ');

        left.appendChild(label);
        left.appendChild(meta);

        const badge = document.createElement('div');
        badge.className = 'badge';
        const badgeText = status === 'failed' ? 'Failed' : status === 'retrying' ? 'Retrying' : 'Queued';
        badge.textContent = badgeText;

        row.appendChild(left);
        row.appendChild(badge);
        return row;
    }

    async function listQueueItems() {
        try {
            const db = await openDb(QUEUE_DB);
            const stores = await listStores(db);
            if (!stores.includes('requests')) return [];

            return new Promise((resolve) => {
                try {
                    const tx = db.transaction(['requests'], 'readonly');
                    const req = tx.objectStore('requests').getAll();
                    req.onsuccess = () => resolve(req.result || []);
                    req.onerror = () => resolve([]);
                } catch (e) {
                    resolve([]);
                }
            });
        } catch (e) {
            return [];
        }
    }

    async function refreshQueueInfo() {
        const list = $('ttQueueList');
        const status = $('ttQueueStatus');
        list.innerHTML = '';

        const items = await listQueueItems();
        let lastFlush = null;
        try {
            lastFlush = JSON.parse(localStorage.getItem('tuneTunerLastQueueFlush') || 'null');
        } catch (e) {
            lastFlush = null;
        }
        const base = `${items.length} queued`;
        if (lastFlush && typeof lastFlush === 'object') {
            const flushed = typeof lastFlush.flushed === 'number' ? lastFlush.flushed : 0;
            const remaining = typeof lastFlush.remaining === 'number' ? lastFlush.remaining : null;
            status.textContent = `${base} • last flush: +${flushed}${remaining !== null ? `, rem=${remaining}` : ''}`;
        } else {
            status.textContent = base;
        }

        if (!items.length) {
            const p = document.createElement('div');
            p.className = 'muted';
            p.textContent = 'No queued requests.';
            list.appendChild(p);
            return;
        }

        const sorted = items.slice().sort((a, b) => (Number(a.createdAt || 0) - Number(b.createdAt || 0)));
        for (const item of sorted.slice(0, 30)) {
            list.appendChild(renderQueueRow(item));
        }

        if (sorted.length > 30) {
            const p = document.createElement('div');
            p.className = 'muted';
            p.textContent = `Showing 30 of ${sorted.length}…`;
            list.appendChild(p);
        }
    }

    async function clearQueue() {
        try {
            const db = await openDb(QUEUE_DB);
            const stores = await listStores(db);
            if (!stores.includes('requests')) return;
            await new Promise((resolve) => {
                const tx = db.transaction(['requests'], 'readwrite');
                tx.objectStore('requests').clear();
                tx.oncomplete = () => resolve();
                tx.onerror = () => resolve();
            });
        } catch (e) {
        }
    }

    async function clearCache() {
        if (window.MetaphorGymCache && typeof window.MetaphorGymCache.clearAll === 'function') {
            try {
                await window.MetaphorGymCache.clearAll();
                return;
            } catch (e) {
            }
        }

        try {
            const db = await openDb(CACHE_DB);
            const stores = await listStores(db);
            if (!stores.length) return;
            await new Promise((resolve) => {
                const tx = db.transaction(stores, 'readwrite');
                for (const s of stores) {
                    try {
                        tx.objectStore(s).clear();
                    } catch (e) {
                    }
                }
                tx.oncomplete = () => resolve();
                tx.onerror = () => resolve();
            });
        } catch (e) {
        }
    }

    async function flushQueueViaServiceWorker() {
        try {
            if (!('serviceWorker' in navigator)) return;
            const reg = await navigator.serviceWorker.ready;
            const sw = reg && reg.active ? reg.active : navigator.serviceWorker.controller;
            if (sw) sw.postMessage({ type: 'TT_FLUSH_QUEUE' });
        } catch (e) {
        }
    }

    async function refreshDebug() {
        const dbg = $('ttDebug');
        const parts = [];
        parts.push(`online=${navigator.onLine !== false}`);
        parts.push(`sw=${'serviceWorker' in navigator}`);
        try {
            const regs = ('serviceWorker' in navigator) ? await navigator.serviceWorker.getRegistrations() : [];
            parts.push(`sw_registrations=${regs.length}`);
        } catch (e) {
            parts.push('sw_registrations=error');
        }
        dbg.textContent = parts.join(' • ');
    }

    async function init() {
        const env = $('ttEnvBadge');
        const features = await loadFeatures();
        if (!features) {
            env.textContent = 'Not staging';
            return;
        }

        env.textContent = features.environment === 'staging' ? 'Staging' : (features.environment || 'Unknown');

        $('ttRefreshCache').onclick = async () => {
            await refreshCacheInfo();
            await refreshStorageEstimate();
        };

        $('ttClearCache').onclick = async () => {
            $('ttCacheStatus').textContent = 'Clearing…';
            await clearCache();
            await refreshCacheInfo();
            await refreshStorageEstimate();
        };

        $('ttFlushQueue').onclick = async () => {
            $('ttQueueStatus').textContent = 'Flushing…';
            await flushQueueViaServiceWorker();
            setTimeout(refreshQueueInfo, 600);
        };

        $('ttClearQueue').onclick = async () => {
            $('ttQueueStatus').textContent = 'Clearing…';
            await clearQueue();
            await refreshQueueInfo();
        };

        await refreshStorageEstimate();
        await refreshCacheInfo();
        await refreshQueueInfo();
        await refreshDebug();

        try {
            if ('serviceWorker' in navigator) {
                navigator.serviceWorker.addEventListener('message', (event) => {
                    const data = event && event.data ? event.data : null;
                    if (!data || data.type !== 'TT_QUEUE_FLUSH_RESULT') return;
                    try {
                        localStorage.setItem('tuneTunerLastQueueFlush', JSON.stringify({
                            savedAt: Date.now(),
                            flushed: data.flushed,
                            remaining: data.remaining,
                            skipped: data.skipped,
                            failed: data.failed,
                            duration_ms: data.duration_ms,
                        }));
                    } catch (e) {
                    }
                    refreshQueueInfo();
                    refreshDebug();
                });
            }
        } catch (e) {
        }

        window.addEventListener('online', () => {
            refreshQueueInfo();
            refreshDebug();
        });
        window.addEventListener('offline', refreshDebug);
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
