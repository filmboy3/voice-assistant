// Shared data cache using IndexedDB for all routes
(() => {
    const DB_NAME = 'MetaphorGymCache';
    const DB_VERSION = 5; // Increment to force cache clear
    const STORES = {
        CREATIVE_GENS: 'creative_gens_data',
        RHYME_INDEX: 'rhyme_index_data',
        CLUSTER_INDEX: 'cluster_index_data',
        TONE_DATA: 'tone_data',
        CREATIVE_QUOTES: 'creative_quotes_data',
        CREATIVE_QUOTES_GROUPS: 'creative_quotes_groups'
    };
    const CACHE_DURATION = 7 * 24 * 60 * 60 * 1000; // 7 days
    const CACHE_VERSION_KEY = 'metaphor_gym_cache_version';

    let db = null;
    let cacheClearPromise = null;
    
    // Check if we need to clear the cache due to version upgrade
    const storedVersion = localStorage.getItem(CACHE_VERSION_KEY);
    if (storedVersion !== String(DB_VERSION)) {
        console.log(`[Cache] Version mismatch (stored: ${storedVersion}, current: ${DB_VERSION}), clearing IndexedDB...`);
        cacheClearPromise = new Promise((resolve) => {
            let resolved = false;
            
            // Force resolve after 500ms if deletion hangs
            const forceTimeout = setTimeout(() => {
                if (!resolved) {
                    console.warn('[Cache] IndexedDB deletion timed out, proceeding without cache');
                    localStorage.setItem(CACHE_VERSION_KEY, String(DB_VERSION));
                    resolved = true;
                    resolve();
                }
            }, 500);
            
            const deleteRequest = indexedDB.deleteDatabase(DB_NAME);
            deleteRequest.onsuccess = () => {
                if (!resolved) {
                    clearTimeout(forceTimeout);
                    console.log('[Cache] IndexedDB cleared successfully');
                    localStorage.setItem(CACHE_VERSION_KEY, String(DB_VERSION));
                    resolved = true;
                    resolve();
                }
            };
            deleteRequest.onerror = () => {
                if (!resolved) {
                    clearTimeout(forceTimeout);
                    console.error('[Cache] Failed to clear IndexedDB:', deleteRequest.error);
                    localStorage.setItem(CACHE_VERSION_KEY, String(DB_VERSION));
                    resolved = true;
                    resolve(); // Resolve anyway to allow app to continue
                }
            };
            deleteRequest.onblocked = () => {
                console.warn('[Cache] IndexedDB deletion blocked (another tab has it open)');
                // forceTimeout will handle this
            };
        });
    } else {
        cacheClearPromise = Promise.resolve();
    }

    async function openDB() {
        console.log('[Cache] openDB called, db:', db ? 'cached' : 'null');
        
        // Wait for cache clear to complete if in progress
        if (cacheClearPromise) {
            console.log('[Cache] Waiting for cache clear to complete...');
            try {
                await cacheClearPromise;
                cacheClearPromise = null;
            } catch (err) {
                console.error('[Cache] Cache clear failed:', err);
            }
        }
        
        return new Promise((resolve, reject) => {
            if (db) {
                console.log('[Cache] Using cached DB connection');
                resolve(db);
                return;
            }
            console.log('[Cache] Opening new IndexedDB connection...');
            
            // Add 2-second timeout to prevent infinite hangs
            const timeout = setTimeout(() => {
                console.error('[Cache] IndexedDB open() timed out after 2s');
                reject(new Error('IndexedDB open timeout'));
            }, 2000);
            
            const request = indexedDB.open(DB_NAME, DB_VERSION);
            request.onerror = () => {
                clearTimeout(timeout);
                console.error('[Cache] IndexedDB open error:', request.error);
                reject(request.error);
            };
            request.onsuccess = () => {
                clearTimeout(timeout);
                console.log('[Cache] IndexedDB opened successfully');
                db = request.result;
                resolve(db);
            };
            request.onupgradeneeded = (event) => {
                console.log('[Cache] IndexedDB upgrade needed');
                const database = event.target.result;
                Object.values(STORES).forEach(storeName => {
                    if (!database.objectStoreNames.contains(storeName)) {
                        console.log(`[Cache] Creating object store: ${storeName}`);
                        database.createObjectStore(storeName);
                    }
                });
            };
        });
    }

    async function getCached(storeName, key) {
        console.log(`[Cache] getCached called for ${key}`);
        try {
            console.log(`[Cache] Opening DB for ${key}...`);
            const database = await openDB();
            console.log(`[Cache] DB opened for ${key}, creating transaction...`);
            return new Promise((resolve, reject) => {
                const transaction = database.transaction([storeName], 'readonly');
                const store = transaction.objectStore(storeName);
                const request = store.get(key);
                console.log(`[Cache] IndexedDB get() called for ${key}`);
                request.onsuccess = () => {
                    console.log(`[Cache] IndexedDB get() success for ${key}`);
                    const cached = request.result;
                    if (!cached) {
                        console.log(`[Cache] No cached data for ${key}`);
                        resolve(null);
                        return;
                    }
                    const age = Date.now() - cached.timestamp;
                    if (age > CACHE_DURATION) {
                        console.log(`[Cache] Cached data expired for ${key}`);
                        resolve(null);
                        return;
                    }
                    console.log(`[Cache] Returning cached data for ${key}`);
                    resolve(cached.data);
                };
                request.onerror = () => {
                    console.error(`[Cache] IndexedDB error for ${key}:`, request.error);
                    reject(request.error);
                };
            });
        } catch (err) {
            console.error(`[Cache] getCached error for ${key}:`, err);
            throw err;
        }
    }

    async function setCache(storeName, key, data) {
        const database = await openDB();
        return new Promise((resolve, reject) => {
            const transaction = database.transaction([storeName], 'readwrite');
            const store = transaction.objectStore(storeName);
            const request = store.put({ data, timestamp: Date.now() }, key);
            request.onsuccess = () => resolve();
            request.onerror = () => reject(request.error);
        });
    }

    async function fetchWithCache(url, storeName, key) {
        console.log(`[Cache] fetchWithCache called: url=${url}, key=${key}`);
        try {
            const cached = await getCached(storeName, key);
            if (cached) {
                console.log(`[Cache] Using cached data for ${key}`);
                return cached;
            }
        } catch (err) {
            console.warn('[Cache] Failed to read cache, will fetch from network:', err);
        }

        console.log(`[Cache] Fetching fresh data for ${key} from ${url}`);
        try {
            console.log(`[Cache] About to call fetch() for ${key}...`);
            const response = await fetch(url);
            console.log(`[Cache] ✅ Fetch completed for ${key}`);
            console.log(`[Cache] Response status: ${response.status}, ok: ${response.ok}, headers:`, {
                contentType: response.headers.get('content-type'),
                contentEncoding: response.headers.get('content-encoding'),
                contentLength: response.headers.get('content-length')
            });
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            console.log(`[Cache] About to parse JSON for ${key}...`);
            const data = await response.json();
            console.log(`[Cache] ✅ JSON parsed successfully for ${key}, type:`, typeof data, 'keys:', Object.keys(data).slice(0, 5));

            try {
                await setCache(storeName, key, data);
                console.log(`[Cache] Saved data for ${key}`);
            } catch (err) {
                console.warn('[Cache] Failed to save cache:', err);
            }

            return data;
        } catch (err) {
            console.error(`[Cache] ERROR fetching ${key}:`, err);
            throw err;
        }
    }

    window.MetaphorGymCache = {
        async getCreativeGensData() {
            return fetchWithCache('/api/creative-gens/web-data', STORES.CREATIVE_GENS, 'web_data');
        },
        async getCreativeGensRhymes() {
            return fetchWithCache('/api/creative-gens/rhymes', STORES.RHYME_INDEX, 'rhyme_index_v2');
        },
        async getCreativeGensClusters() {
            return fetchWithCache('/api/creative-gens/clusters', STORES.CLUSTER_INDEX, 'cluster_index');
        },
        async getCreativeQuotesData() {
            return fetchWithCache('/api/creative-quotes/data', STORES.CREATIVE_QUOTES, 'creative_quotes_v6');
        },
        async getCreativeQuotesCategoriesGrouped() {
            return fetchWithCache('/api/creative-quotes/categories-grouped', STORES.CREATIVE_QUOTES_GROUPS, 'categories_grouped_v1');
        },
        async getRhymeData() {
            return fetchWithCache('/api/rhyme-data', STORES.RHYME_INDEX, 'rhyme_data');
        },
        async clearAll() {
            const database = await openDB();
            const transaction = database.transaction(Object.values(STORES), 'readwrite');
            Object.values(STORES).forEach(storeName => {
                transaction.objectStore(storeName).clear();
            });
            return new Promise((resolve, reject) => {
                transaction.oncomplete = () => {
                    console.log('[Cache] All caches cleared');
                    resolve();
                };
                transaction.onerror = () => reject(transaction.error);
            });
        }
    };

    window.fetchWithCache = fetchWithCache;
})();
