(() => {
    const CACHE_NAME = 'tune-tuner-offline-v1';
    const QUEUE_DB_NAME = 'TuneTunerOfflineQueue';
    const QUEUE_DB_VERSION = 1;
    const QUEUE_STORE = 'requests';

    const QUEUE_MAX_ATTEMPTS = 6;
    const QUEUE_MIN_BACKOFF_MS = 1_500;
    const QUEUE_MAX_BACKOFF_MS = 120_000;
    let _flushInProgress = false;

    function nowMs() {
        return Date.now();
    }

    function clamp(n, lo, hi) {
        return Math.max(lo, Math.min(hi, n));
    }

    function backoffMs(attempts) {
        const a = Math.max(0, Number(attempts || 0));
        const raw = QUEUE_MIN_BACKOFF_MS * Math.pow(2, a);
        return clamp(Math.round(raw), QUEUE_MIN_BACKOFF_MS, QUEUE_MAX_BACKOFF_MS);
    }

    function fnv1a(str) {
        let h = 0x811c9dc5;
        const s = String(str || '');
        for (let i = 0; i < s.length; i += 1) {
            h ^= s.charCodeAt(i);
            h = (h + ((h << 1) + (h << 4) + (h << 7) + (h << 8) + (h << 24))) >>> 0;
        }
        return ('00000000' + h.toString(16)).slice(-8);
    }

    async function broadcastToClients(message) {
        try {
            const clients = await self.clients.matchAll({ includeUncontrolled: true, type: 'window' });
            for (const c of clients) {
                try {
                    c.postMessage(message);
                } catch (e) {
                }
            }
        } catch (e) {
        }
    }

    function openQueueDB() {
        return new Promise((resolve, reject) => {
            const req = indexedDB.open(QUEUE_DB_NAME, QUEUE_DB_VERSION);
            req.onupgradeneeded = () => {
                const db = req.result;
                if (!db.objectStoreNames.contains(QUEUE_STORE)) {
                    db.createObjectStore(QUEUE_STORE, { keyPath: 'id' });
                }
            };
            req.onsuccess = () => resolve(req.result);
            req.onerror = () => reject(req.error);
        });
    }

    async function queueRequest(record) {
        const db = await openQueueDB();
        return new Promise((resolve, reject) => {
            const tx = db.transaction([QUEUE_STORE], 'readwrite');
            tx.objectStore(QUEUE_STORE).put(record);
            tx.oncomplete = () => resolve();
            tx.onerror = () => reject(tx.error);
        });
    }

    async function listQueuedRequests() {
        const db = await openQueueDB();
        return new Promise((resolve, reject) => {
            const tx = db.transaction([QUEUE_STORE], 'readonly');
            const req = tx.objectStore(QUEUE_STORE).getAll();
            req.onsuccess = () => resolve(req.result || []);
            req.onerror = () => reject(req.error);
        });
    }

    async function deleteQueuedRequest(id) {
        const db = await openQueueDB();
        return new Promise((resolve, reject) => {
            const tx = db.transaction([QUEUE_STORE], 'readwrite');
            tx.objectStore(QUEUE_STORE).delete(id);
            tx.oncomplete = () => resolve();
            tx.onerror = () => reject(tx.error);
        });
    }

    function isApiRequest(url) {
        try {
            return url && url.pathname && url.pathname.startsWith('/api/');
        } catch (e) {
            return false;
        }
    }

    async function serializeRequest(request) {
        const headers = {};
        request.headers.forEach((v, k) => {
            headers[k] = v;
        });

        let bodyText = '';
        try {
            bodyText = await request.clone().text();
        } catch (e) {
            bodyText = '';
        }

        return {
            url: request.url,
            method: request.method,
            headers,
            bodyText,
            mode: request.mode,
            credentials: request.credentials,
            cache: request.cache,
            redirect: request.redirect,
            referrer: request.referrer,
            referrerPolicy: request.referrerPolicy,
            integrity: request.integrity,
            keepalive: request.keepalive
        };
    }

    function _queueIdForSerialized(serialized) {
        const method = (serialized && serialized.method ? String(serialized.method) : 'POST').toUpperCase();
        const url = serialized && serialized.url ? String(serialized.url) : '';
        const bodyText = serialized && typeof serialized.bodyText === 'string' ? serialized.bodyText : '';
        return `q_${fnv1a(method + ' ' + url + ' ' + bodyText)}`;
    }

    function deserializeRequest(record) {
        const init = {
            method: record.method,
            headers: record.headers || {},
            body: record.bodyText || undefined,
            mode: record.mode,
            credentials: record.credentials,
            cache: record.cache,
            redirect: record.redirect,
            referrer: record.referrer,
            referrerPolicy: record.referrerPolicy,
            integrity: record.integrity,
            keepalive: record.keepalive
        };
        return new Request(record.url, init);
    }

    async function flushQueue() {
        if (_flushInProgress) {
            const remaining = (await listQueuedRequests()).length;
            return { flushed: 0, remaining, skipped: 0, failed: 0, in_progress: true };
        }

        _flushInProgress = true;
        try {
            const items = await listQueuedRequests();
            if (!items.length) {
                const result = { flushed: 0, remaining: 0, skipped: 0, failed: 0 };
                await broadcastToClients({ type: 'TT_QUEUE_FLUSH_RESULT', ...result });
                return result;
            }

            const sorted = items.slice().sort((a, b) => (Number(a.createdAt || 0) - Number(b.createdAt || 0)));
            const startedAt = nowMs();
            let flushed = 0;
            let skipped = 0;
            let failed = 0;

            for (const item of sorted) {
                const status = item && item.status ? String(item.status) : 'queued';
                const attempts = Number(item && item.attempts ? item.attempts : 0);
                const nextAttemptAt = Number(item && item.nextAttemptAt ? item.nextAttemptAt : 0);
                if (status === 'failed') {
                    skipped += 1;
                    continue;
                }
                if (nextAttemptAt && nextAttemptAt > nowMs()) {
                    skipped += 1;
                    continue;
                }
                if (attempts >= QUEUE_MAX_ATTEMPTS) {
                    try {
                        await queueRequest({
                            ...item,
                            status: 'failed',
                            nextAttemptAt: 0,
                            lastError: item && item.lastError ? item.lastError : { message: 'Max attempts exceeded' },
                        });
                    } catch (e) {
                    }
                    failed += 1;
                    continue;
                }

                let updated = { ...item };
                updated.attempts = attempts + 1;
                updated.lastAttemptAt = nowMs();
                updated.status = 'retrying';
                try {
                    await queueRequest(updated);
                } catch (e) {
                }

                try {
                    const req = deserializeRequest(item);
                    const resp = await fetch(req);
                    if (resp && resp.ok) {
                        await deleteQueuedRequest(item.id);
                        flushed += 1;
                        continue;
                    }

                    let detail = '';
                    try {
                        detail = resp ? String(await resp.clone().text()) : '';
                    } catch (e) {
                        detail = '';
                    }

                    const nextAt = nowMs() + backoffMs(updated.attempts);
                    await queueRequest({
                        ...updated,
                        status: updated.attempts >= QUEUE_MAX_ATTEMPTS ? 'failed' : 'queued',
                        nextAttemptAt: updated.attempts >= QUEUE_MAX_ATTEMPTS ? 0 : nextAt,
                        lastError: {
                            type: 'http',
                            status: resp ? resp.status : 0,
                            message: resp ? resp.statusText : 'HTTP error',
                            detail: (detail || '').slice(0, 800),
                            at: nowMs(),
                        },
                    });
                    failed += 1;
                } catch (e) {
                    const nextAt = nowMs() + backoffMs(updated.attempts);
                    try {
                        await queueRequest({
                            ...updated,
                            status: updated.attempts >= QUEUE_MAX_ATTEMPTS ? 'failed' : 'queued',
                            nextAttemptAt: updated.attempts >= QUEUE_MAX_ATTEMPTS ? 0 : nextAt,
                            lastError: {
                                type: 'exception',
                                message: e && e.message ? String(e.message) : 'Fetch failed',
                                at: nowMs(),
                            },
                        });
                    } catch (e2) {
                    }
                    failed += 1;
                }
            }

            const remaining = (await listQueuedRequests()).length;
            const result = {
                flushed,
                remaining,
                skipped,
                failed,
                duration_ms: nowMs() - startedAt,
            };
            await broadcastToClients({ type: 'TT_QUEUE_FLUSH_RESULT', ...result });
            return result;
        } finally {
            _flushInProgress = false;
        }
    }

    self.addEventListener('install', (event) => {
        event.waitUntil(
            caches.open(CACHE_NAME).then((cache) =>
                cache.addAll([
                    '/',
                    '/home',
                    '/tones',
                    '/creative-gens',
                    '/creative-quotes',
                    '/quick-helper',
                    '/offline-library',
                    '/export-manager',
                    '/global-nav.js',
                    '/notes_manager.js',
                    '/shared_interactions.js',
                    '/shared-cache.js',
                    '/offline_library_manager.js',
                    '/export_manager.js'
                ])
            )
        );
        self.skipWaiting();
    });

    self.addEventListener('activate', (event) => {
        event.waitUntil(
            (async () => {
                const keys = await caches.keys();
                await Promise.all(keys.map((k) => (k === CACHE_NAME ? null : caches.delete(k))));
                await self.clients.claim();
            })()
        );
    });

    self.addEventListener('message', (event) => {
        const data = event.data || {};
        if (data && data.type === 'TT_FLUSH_QUEUE') {
            event.waitUntil(flushQueue());
        }
    });

    self.addEventListener('fetch', (event) => {
        const request = event.request;
        const url = new URL(request.url);

        if (request.method !== 'GET') {
            if (request.method === 'POST' && isApiRequest(url)) {
                event.respondWith(
                    (async () => {
                        try {
                            return await fetch(request);
                        } catch (e) {
                            const serialized = await serializeRequest(request);
                            const id = _queueIdForSerialized(serialized);
                            const ts = nowMs();
                            const record = {
                                id,
                                createdAt: ts,
                                updatedAt: ts,
                                status: 'queued',
                                attempts: 0,
                                nextAttemptAt: 0,
                                lastAttemptAt: 0,
                                lastError: null,
                                ...serialized,
                            };
                            try {
                                await queueRequest(record);
                            } catch (e2) {
                            }
                            return new Response(
                                JSON.stringify({ success: true, queued: true, id }),
                                { status: 202, headers: { 'Content-Type': 'application/json' } }
                            );
                        }
                    })()
                );
                return;
            }
            return;
        }

        if (isApiRequest(url)) {
            event.respondWith(fetch(request));
            return;
        }

        event.respondWith(
            (async () => {
                const cache = await caches.open(CACHE_NAME);
                try {
                    const resp = await fetch(request);
                    if (resp && resp.ok && (url.origin === self.location.origin)) {
                        cache.put(request, resp.clone());
                    }
                    return resp;
                } catch (e) {
                    const cached = await cache.match(request);
                    if (cached) return cached;
                    if (url.pathname === '/' || url.pathname === '/home') {
                        const fallback = await cache.match('/');
                        if (fallback) return fallback;
                    }
                    return new Response('Offline', { status: 503, statusText: 'Offline' });
                }
            })()
        );
    });
})();
