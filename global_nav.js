(() => {
    const ICONS = {
        home: `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 9l9-7 9 7"></path><path d="M9 22V12h6v10"></path></svg>`,
        search: `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="8"></circle><path d="m21 21-4.3-4.3"></path></svg>`,
        book: `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"></path><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"></path></svg>`,
        tones: `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M9 18V5l12-2v13"></path><circle cx="6" cy="18" r="3"></circle><circle cx="18" cy="16" r="3"></circle></svg>`,
        gens: `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 20h9"></path><path d="M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4Z"></path></svg>`,
        quotes: `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 21c3 0 5-2 5-5V8H3V3h5v5"></path><path d="M16 21c3 0 5-2 5-5V8h-5V3h5v5"></path></svg>`,
        dynamic: `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"></path><polyline points="7.5 4.21 12 6.81 16.5 4.21"></polyline><polyline points="7.5 19.79 7.5 14.6 3 12"></polyline><polyline points="21 12 16.5 14.6 16.5 19.79"></polyline><polyline points="3.27 6.96 12 12.01 20.73 6.96"></polyline><line x1="12" y1="22.08" x2="12" y2="12"></line></svg>`,
        notes: `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M9 18h6"></path><path d="M10 22h4"></path><path d="M12 2a7 7 0 0 0-4 12c.6.6 1 1.2 1 2h6c0-.8.4-1.4 1-2a7 7 0 0 0-4-12Z"></path></svg>`,
        menu: `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 6h16"></path><path d="M4 12h16"></path><path d="M4 18h16"></path></svg>`
    };

    const NAV_CONFIG = {
        brandTitle: "Tune Tuner",
        brandIcon: `<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="margin-right: 8px; vertical-align: -3px;"><path d="M9 18V5l12-2v13"></path><circle cx="6" cy="18" r="3"></circle><circle cx="18" cy="16" r="3"></circle></svg>`,
        brandSubtitle: "Creative Stack",
        links: [
            { label: "Search", href: "/", icon: ICONS.search, iconLabel: "Search", iconOnly: true },
            { label: "Reference", href: "/quick-helper", icon: ICONS.book, iconLabel: "Reference" },
            { label: "Tones", href: "/tones", icon: ICONS.tones, iconLabel: "Tones" },
            { label: "Mash-Ups", href: "/creative-gens", icon: ICONS.gens, iconLabel: "Mash-Ups" },
            { label: "Creative Quotes", href: "/creative-quotes", icon: ICONS.quotes, iconLabel: "Quotes" },
            { label: "Dynamic", href: "/dynamic-gens", icon: ICONS.dynamic, iconLabel: "Dynamic" },
            { label: "SongSource", href: "/comprehensive-songs-r2", icon: ICONS.book, iconLabel: "SongSource" }
        ]
    };

    const STYLES = `
        :root {
            --nav-bg: #14100b;
            --nav-text: #f8f5ed;
            --nav-muted: #cfc7b8;
            --nav-highlight: #f4d07a;
            --global-nav-height: 76px;
        }
        .tt-offline-banner {
            position: fixed;
            left: 50%;
            transform: translateX(-50%);
            top: calc(var(--global-sticky-top-offset, var(--global-nav-height, 76px)) + 8px);
            z-index: 995;
            padding: 10px 14px;
            border-radius: 999px;
            font-size: 0.85rem;
            font-weight: 650;
            box-shadow: 0 10px 26px rgba(0,0,0,0.22);
            border: 1px solid rgba(255,255,255,0.18);
            background: rgba(20, 16, 11, 0.96);
            color: var(--nav-text);
            display: none;
            align-items: center;
            gap: 10px;
        }
        .tt-offline-banner.show {
            display: inline-flex;
        }
        .tt-offline-pill {
            width: 10px;
            height: 10px;
            border-radius: 999px;
            background: #d96b6b;
            box-shadow: 0 0 0 3px rgba(217, 107, 107, 0.16);
        }
        .tt-online-pill {
            width: 10px;
            height: 10px;
            border-radius: 999px;
            background: #67d990;
            box-shadow: 0 0 0 3px rgba(103, 217, 144, 0.16);
        }
        body.has-global-nav {
            padding-top: 0;
        }
        body.has-global-nav > .container,
        body.has-global-nav > div:not(.global-nav) {
            margin-top: calc(var(--global-nav-height) + 12px);
        }
        .global-nav {
            position: sticky;
            top: 0;
            left: 0;
            width: 100%;
            z-index: 999;
            background: var(--nav-bg);
            color: var(--nav-text);
            box-shadow: 0 6px 18px rgba(0, 0, 0, 0.25);
        }
        .global-nav .nav-inner {
            max-width: 1200px;
            margin: 0 auto;
            padding: 18px 24px;
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 24px;
            flex-wrap: wrap;
        }

        .global-nav .nav-left,
        .global-nav .nav-right {
            display: flex;
            align-items: center;
            gap: 12px;
        }
        .global-nav .brand {
            display: flex;
            flex-direction: column;
            line-height: 1.2;
        }
        .global-nav .brand-title {
            font-size: 1.1rem;
            font-weight: 600;
        }
        .global-nav .brand-subtitle {
            font-size: 0.8rem;
            color: var(--nav-muted);
            letter-spacing: 0.08em;
            text-transform: uppercase;
        }
        .global-nav .nav-actions {
            display: flex;
            gap: 12px;
            flex-wrap: wrap;
            align-items: center;
            justify-content: flex-end;
        }

        .global-nav .nav-hamburger {
            display: inline-flex;
            appearance: none;
            -webkit-appearance: none;
            cursor: pointer;
        }
        /* Hide nav link buttons on desktop too - use hamburger menu */
        .global-nav .nav-actions a.nav-link {
            display: none;
        }

        .nav-menu-backdrop {
            position: fixed;
            inset: 0;
            background: rgba(0,0,0,0.35);
            z-index: 998;
            opacity: 0;
            pointer-events: none;
            transition: opacity 0.18s ease;
        }

        .nav-menu-backdrop.show {
            opacity: 1;
            pointer-events: auto;
        }

        .nav-menu-panel {
            position: fixed;
            top: calc(var(--global-nav-height) + 6px);
            right: 10px;
            width: min(320px, calc(100vw - 20px));
            background: rgba(20, 16, 11, 0.98);
            border: 1px solid rgba(255,255,255,0.14);
            border-radius: 16px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.45);
            z-index: 999;
            transform: translateY(-6px);
            opacity: 0;
            pointer-events: none;
            transition: opacity 0.18s ease, transform 0.18s ease;
            padding: 12px;
        }

        .nav-menu-panel.show {
            opacity: 1;
            pointer-events: auto;
            transform: translateY(0);
        }

        .nav-menu-panel a {
            display: flex;
            align-items: center;
            gap: 10px;
            padding: 12px 12px;
            border-radius: 12px;
            text-decoration: none;
            color: var(--nav-text);
            font-weight: 650;
            border: 1px solid transparent;
        }

        .nav-menu-panel a.active {
            background: var(--nav-highlight);
            color: #1a1307;
        }

        .nav-menu-panel a:hover {
            border-color: rgba(244, 208, 122, 0.65);
        }

        .nav-menu-panel .nav-menu-title {
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 10px;
            margin-bottom: 10px;
            padding: 4px 6px;
            color: var(--nav-muted);
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 0.08em;
            font-size: 0.74rem;
        }

        .nav-menu-panel .nav-menu-close {
            width: 34px;
            height: 34px;
            border-radius: 999px;
            border: 1px solid rgba(255,255,255,0.2);
            background: transparent;
            color: var(--nav-text);
            cursor: pointer;
            display: inline-flex;
            align-items: center;
            justify-content: center;
            font-size: 1.2rem;
        }

        :root {
            --scroll-btn-size: 44px;
            --scroll-btn-gap: 48px;
            --scroll-btn-right: 14px;
            --scroll-btn-center-shift: 0px;
        }

        .global-scroll-controls {
            position: fixed;
            left: 50%;
            right: auto;
            top: 0;
            bottom: 0;
            transform: translateX(-50%);
            display: none;
            flex-direction: column;
            justify-content: space-between;
            padding: calc(var(--global-sticky-top-offset, var(--global-nav-height, 76px)) + 10px + env(safe-area-inset-top, 0px)) 0 calc(12px + env(safe-area-inset-bottom, 0px)) 0;
            gap: 0;
            z-index: 990;
            pointer-events: none;
        }

        body.tt-scroll-locked {
            overflow: hidden;
            overscroll-behavior: none;
            touch-action: none;
        }

        .global-scroll-controls button {
            width: var(--scroll-btn-size);
            height: var(--scroll-btn-size);
            border-radius: 999px;
            border: none;
            background: rgba(44, 37, 32, 0.72);
            color: #fff;
            cursor: pointer;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 1.2rem;
            box-shadow: 0 2px 8px rgba(0,0,0,0.2);
            transition: transform 0.12s ease, background 0.12s ease;
            pointer-events: auto;
        }

        .global-scroll-controls button:active {
            transform: scale(0.96);
            background: rgba(44, 37, 32, 0.86);
        }
        .global-nav .notes-btn-badge {
            background: var(--nav-highlight);
            color: #1a1307;
            font-size: 0.7rem;
            padding: 2px 6px;
            border-radius: 10px;
            font-weight: 600;
            min-width: 18px;
            text-align: center;
        }
        .global-nav .nav-link {
            color: var(--nav-text);
            text-decoration: none;
            border: 1px solid rgba(255, 255, 255, 0.2);
            border-radius: 999px;
            background: transparent;
            padding: 8px 18px;
            font-size: 0.9rem;
            transition: all 0.2s ease;
            display: inline-flex;
            align-items: center;
            gap: 8px;
        }
        .global-nav .notes-btn {
            appearance: none;
            -webkit-appearance: none;
            background: transparent;
        }
        .global-nav .notes-btn-label {
            display: inline;
        }
        .global-nav .notes-btn-icon {
            display: inline-flex;
            width: 18px;
            height: 18px;
            flex: 0 0 auto;
        }
        .global-nav .nav-link .nav-link-icon {
            display: inline-flex;
            width: 18px;
            height: 18px;
            flex: 0 0 auto;
        }
        .global-nav .nav-link .nav-link-label {
            display: inline;
        }
        .global-nav .nav-link.icon-only .nav-link-icon {
            display: inline-flex;
        }
        .global-nav .nav-link.icon-only .nav-link-label {
            display: none;
        }
        .global-nav .nav-link:hover {
            border-color: var(--nav-highlight);
            color: var(--nav-highlight);
        }
        .global-nav .nav-link.active {
            background: var(--nav-highlight);
            color: #1a1307;
            border-color: var(--nav-highlight);
            font-weight: 600;
        }
        @media (max-width: 640px) {
            .global-nav .nav-inner {
                display: grid;
                grid-template-columns: auto 1fr auto;
                align-items: center;
                gap: 10px;
                padding: 12px 12px;
            }
            .global-nav .nav-left {
                justify-content: flex-start;
            }
            .global-nav .nav-right {
                justify-content: flex-end;
            }
            .global-nav .nav-actions {
                width: auto;
                display: flex;
                gap: 10px;
                flex-wrap: nowrap;
                justify-content: flex-end;
            }
            .global-nav .brand {
                flex: 1 1 auto;
                align-items: center;
                text-align: center;
            }
            .global-nav .brand-subtitle {
                display: none;
            }
            .global-nav .nav-link {
                padding: 10px 12px;
                font-size: 0.85rem;
            }
            .global-nav .nav-actions a.nav-link {
                display: none;
            }
            .global-nav .nav-link .nav-link-icon {
                display: inline-flex;
            }
            .global-nav .nav-link .nav-link-label {
                display: none;
            }
            .global-nav .notes-btn-label {
                display: none;
            }
            .global-nav .nav-hamburger {
                display: inline-flex;
            }
        }
    `;

    let menuState = { isOpen: false, hamburgerBtn: null, backdrop: null, panel: null };
    let scrollControlsState = { wrapper: null, upBtn: null, downBtn: null };

    let scrollLockState = { locked: false, scrollY: 0, installed: false };

    let offlineState = { banner: null, installed: false };

    function ensureOfflineBanner() {
        if (offlineState.banner) return offlineState.banner;
        const banner = document.createElement('div');
        banner.className = 'tt-offline-banner';
        banner.id = 'ttOfflineBanner';
        banner.innerHTML = `<span class="tt-offline-pill" aria-hidden="true"></span><span id="ttOfflineBannerText">Offline</span>`;
        document.body.appendChild(banner);
        offlineState.banner = banner;
        return banner;
    }

    function setOfflineBanner(online, message) {
        const banner = ensureOfflineBanner();
        const txt = banner.querySelector('#ttOfflineBannerText');
        const pill = banner.querySelector('.tt-offline-pill, .tt-online-pill');
        if (pill) {
            pill.className = online ? 'tt-online-pill' : 'tt-offline-pill';
        }
        if (txt) {
            txt.textContent = message || (online ? 'Online' : 'Offline');
        }
        banner.classList.toggle('show', !online);
    }

    async function fetchStagingFeatures() {
        try {
            const resp = await fetch('/api/features', { cache: 'no-store' });
            if (!resp.ok) return null;
            const data = await resp.json();
            if (!data || typeof data !== 'object') return null;
            return data.features || null;
        } catch (e) {
            return null;
        }
    }

    async function flushServiceWorkerQueue() {
        try {
            if (!('serviceWorker' in navigator)) return;
            const reg = await navigator.serviceWorker.ready;
            const sw = reg && reg.active ? reg.active : navigator.serviceWorker.controller;
            if (sw) sw.postMessage({ type: 'TT_FLUSH_QUEUE' });
        } catch (e) {
        }
    }

    async function initOfflinePOC() {
        if (offlineState.installed) return;
        offlineState.installed = true;

        const host = (window.location && window.location.hostname ? window.location.hostname : '').toLowerCase();
        const mightBeStaging = host.includes('staging');

        const features = await fetchStagingFeatures();
        if (!features && !mightBeStaging) {
            return;
        }

        if (features && features.pattison_exercise_lab) {
            const hasLink = NAV_CONFIG.links.some((l) => l && l.href === '/pattison-exercise-lab');
            if (!hasLink) {
                NAV_CONFIG.links.push({ label: 'Pattison Lab', href: '/pattison-exercise-lab', icon: ICONS.book, iconLabel: 'Pattison Lab' });
            }
        }

        if (features && features.export_manager && features.agentic_endpoints) {
            try {
                if (!window.__ttLastDraftCaptureInstalled) {
                    window.__ttLastDraftCaptureInstalled = true;
                    const originalFetch = window.fetch.bind(window);
                    window.fetch = async (input, init) => {
                        const resp = await originalFetch(input, init);
                        try {
                            const url = (typeof input === 'string') ? input : (input && input.url ? input.url : '');
                            if (url && url.indexOf('/api/llm/song-draft') !== -1 && resp && resp.ok && resp.clone) {
                                const clone = resp.clone();
                                clone.json().then((data) => {
                                    try {
                                        if (data && data.success && typeof data.lyrics === 'string' && data.lyrics.trim()) {
                                            localStorage.setItem('tuneTunerLastLyrics', data.lyrics);
                                            const meta = {
                                                savedAt: Date.now(),
                                                theme: data.metadata && data.metadata.theme ? data.metadata.theme : '',
                                                tone: data.metadata && data.metadata.tone ? data.metadata.tone : '',
                                                structure: data.metadata && data.metadata.structure ? data.metadata.structure : ''
                                            };
                                            localStorage.setItem('tuneTunerLastLyricsMeta', JSON.stringify(meta));

                                            try {
                                                const draftBundle = {
                                                    savedAt: meta.savedAt,
                                                    lyrics: data.lyrics,
                                                    outline: (data.outline && typeof data.outline === 'object') ? data.outline : null,
                                                    metadata: (data.metadata && typeof data.metadata === 'object') ? data.metadata : {},
                                                };
                                                localStorage.setItem('tuneTunerLastSongDraft', JSON.stringify(draftBundle));
                                            } catch (e) {
                                            }
                                        }
                                    } catch (e) {
                                    }
                                }).catch(() => {
                                });
                            }
                        } catch (e) {
                        }
                        return resp;
                    };
                }
            } catch (e) {
            }
        }

        const swEnabled = mightBeStaging || !!(features && features.service_worker);

        if (swEnabled && ('serviceWorker' in navigator)) {
            try {
                await navigator.serviceWorker.register('/sw.js', { scope: '/' });
            } catch (e) {
            }
        }

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
                });
            }
        } catch (e) {
        }

        const update = () => {
            const online = navigator.onLine !== false;
            if (online) {
                setOfflineBanner(true, 'Online');
            } else {
                setOfflineBanner(false, 'Offline');
            }
        };

        window.addEventListener('online', () => {
            update();
            flushServiceWorkerQueue();
        });
        window.addEventListener('offline', update);

        update();
    }

    function setScrollBtnVisibility(btn, visible) {
        if (!btn) return;
        btn.style.visibility = visible ? 'visible' : 'hidden';
        btn.style.pointerEvents = visible ? 'auto' : 'none';
    }

    function shouldBlockZoomTarget(target) {
        if (!target) return true;
        const el = target.nodeType === 1 ? target : null;
        if (!el) return true;
        if (el.closest('input, textarea, select')) return false;
        if (el.isContentEditable) return false;
        return true;
    }

    function installZoomGuards() {
        if (window.__TuneTunerZoomGuardsInstalled) return;
        window.__TuneTunerZoomGuardsInstalled = true;

        let lastTouchEnd = 0;
        document.addEventListener('touchend', function(e) {
            const now = Date.now();
            if (now - lastTouchEnd < 350 && shouldBlockZoomTarget(e.target)) {
                e.preventDefault();
            }
            lastTouchEnd = now;
        }, { passive: false });

        document.addEventListener('gesturestart', function(e) {
            e.preventDefault();
        }, { passive: false });

        document.addEventListener('dblclick', function(e) {
            if (shouldBlockZoomTarget(e.target)) {
                e.preventDefault();
            }
        }, { passive: false });
    }

    function ensureMenu() {
        if (menuState.backdrop && menuState.panel) return menuState;

        const backdrop = document.createElement('div');
        backdrop.className = 'nav-menu-backdrop';

        const panel = document.createElement('div');
        panel.className = 'nav-menu-panel';

        const title = document.createElement('div');
        title.className = 'nav-menu-title';
        title.innerHTML = '<span>Menu</span>';

        const closeBtn = document.createElement('button');
        closeBtn.className = 'nav-menu-close';
        closeBtn.type = 'button';
        closeBtn.setAttribute('aria-label', 'Close menu');
        closeBtn.textContent = '×';
        closeBtn.onclick = function() {
            setMenuOpen(false);
        };
        title.appendChild(closeBtn);
        panel.appendChild(title);

        const currentPath = (window.location.pathname || '').replace(/\/+$/, '') || '/';
        const currentHash = window.location.hash || '';

        NAV_CONFIG.links.forEach((link) => {
            const anchor = document.createElement('a');
            anchor.href = link.href;
            anchor.innerHTML = `<span aria-hidden="true">${link.icon || ''}</span><span>${link.label}</span>`;
            const [linkPath, linkHash = ""] = link.href.split("#");
            const normalizedLinkPath = (linkPath || "").replace(/\/+$/, "") || "/";
            const isActive =
                normalizedLinkPath === currentPath &&
                (linkHash ? `#${linkHash}` === currentHash : true);
            if (isActive) anchor.classList.add('active');
            panel.appendChild(anchor);
        });

        backdrop.addEventListener('click', function() {
            setMenuOpen(false);
        });

        document.body.appendChild(backdrop);
        document.body.appendChild(panel);

        menuState.backdrop = backdrop;
        menuState.panel = panel;
        return menuState;
    }

    function setMenuOpen(isOpen) {
        const { backdrop, panel, hamburgerBtn } = ensureMenu();
        menuState.isOpen = !!isOpen;
        backdrop.classList.toggle('show', menuState.isOpen);
        panel.classList.toggle('show', menuState.isOpen);
        if (hamburgerBtn) {
            hamburgerBtn.setAttribute('aria-expanded', menuState.isOpen ? 'true' : 'false');
        }
    }

    function hasOpenOverlay() {
        if (menuState && menuState.isOpen) return true;
        if (document.body.classList.contains('notes-open')) return true;
        if (document.documentElement.classList.contains('drawer-open')) return true;
        if (document.querySelector('.drawer-backdrop.show')) return true;
        if (document.querySelector('#drawerBackdrop.show')) return true;
        if (document.querySelector('#notesBackdrop.show')) return true;
        return false;
    }

    function hasScrollLockOverlay() {
        // Only lock for drawers/backdrops/notes (not the hamburger menu)
        if (document.body.classList.contains('notes-open')) return true;
        if (document.documentElement.classList.contains('drawer-open')) return true;
        if (document.querySelector('.drawer-backdrop.show')) return true;
        if (document.querySelector('#drawerBackdrop.show')) return true;
        if (document.querySelector('#notesBackdrop.show')) return true;
        return false;
    }

    function isAllowedScrollTarget(target) {
        const el = target && target.nodeType === 1 ? target : null;
        if (!el) return false;
        return !!el.closest(
            '#unifiedDrawer, .rhyme-chip-bubble, #itemsDrawer, .items-drawer, #quoteDrawer, .quote-drawer, #gensDrawer, .gens-drawer, #notesDrawer, .notes-drawer'
        );
    }

    function lockBodyScroll() {
        if (scrollLockState.locked) return;
        scrollLockState.locked = true;
        scrollLockState.scrollY = window.scrollY || document.documentElement.scrollTop || 0;
        document.body.classList.add('tt-scroll-locked');
        // Use position: fixed to prevent iOS background scroll
        document.body.style.position = 'fixed';
        document.body.style.top = `-${scrollLockState.scrollY}px`;
        document.body.style.left = '0';
        document.body.style.right = '0';
        document.body.style.width = '100%';
    }

    function unlockBodyScroll() {
        if (!scrollLockState.locked) return;
        scrollLockState.locked = false;
        document.body.classList.remove('tt-scroll-locked');
        const y = scrollLockState.scrollY || 0;
        document.body.style.position = '';
        document.body.style.top = '';
        document.body.style.left = '';
        document.body.style.right = '';
        document.body.style.width = '';
        window.scrollTo({ top: y, behavior: 'auto' });
    }

    function ensureScrollLockHandlers() {
        if (scrollLockState.installed) return;
        scrollLockState.installed = true;

        window.addEventListener('wheel', function(e) {
            if (!scrollLockState.locked) return;
            if (isAllowedScrollTarget(e.target)) return;
            e.preventDefault();
        }, { passive: false });

        window.addEventListener('touchmove', function(e) {
            if (!scrollLockState.locked) return;
            if (isAllowedScrollTarget(e.target)) return;
            e.preventDefault();
        }, { passive: false });
    }

    function updateBodyScrollLock() {
        if (hasScrollLockOverlay()) {
            lockBodyScroll();
        } else {
            unlockBodyScroll();
        }
    }

    function ensureScrollControls() {
        if (scrollControlsState.wrapper) return scrollControlsState;
        const wrapper = document.createElement('div');
        wrapper.className = 'global-scroll-controls';
        wrapper.id = 'globalScrollControls';

        const upBtn = document.createElement('button');
        upBtn.type = 'button';
        upBtn.setAttribute('aria-label', 'Scroll to top');
        upBtn.textContent = '↑';
        upBtn.onclick = function(e) {
            e.preventDefault();
            window.scrollTo({ top: 0, behavior: 'smooth' });
        };

        const downBtn = document.createElement('button');
        downBtn.type = 'button';
        downBtn.setAttribute('aria-label', 'Scroll to bottom');
        downBtn.textContent = '↓';
        downBtn.onclick = function(e) {
            e.preventDefault();
            const bottom = Math.max(0, document.documentElement.scrollHeight - window.innerHeight);
            window.scrollTo({ top: bottom, behavior: 'smooth' });
        };

        wrapper.appendChild(upBtn);
        wrapper.appendChild(downBtn);
        document.body.appendChild(wrapper);

        scrollControlsState = { wrapper, upBtn, downBtn };
        return scrollControlsState;
    }

    function updateScrollControls() {
        const { wrapper, upBtn, downBtn } = ensureScrollControls();
        if (!wrapper || !upBtn || !downBtn) return;

        if (hasOpenOverlay()) {
            wrapper.style.display = 'none';
            return;
        }

        const scrollTop = window.scrollY || document.documentElement.scrollTop || 0;
        const maxScroll = Math.max(0, document.documentElement.scrollHeight - window.innerHeight);
        const atBottom = maxScroll - scrollTop < 24;

        updateStickyTopOffset();

        if (maxScroll < 300) {
            wrapper.style.display = 'none';
            return;
        }

        wrapper.style.display = 'flex';
        // IMPORTANT: Use visibility rather than display:none so the down button never "jumps" to the top
        // when the up button is hidden on initial page load.
        setScrollBtnVisibility(upBtn, scrollTop > 120);
        setScrollBtnVisibility(downBtn, !atBottom);
    }

    function updateStickyTopOffset() {
        // Goal: place the top scroll arrow below any "sticky at top" UI (nav + page sticky bars)
        // without requiring each page to manually wire offsets.
        try {
            const nav = document.querySelector('.global-nav');
            const navRect = nav ? nav.getBoundingClientRect() : null;
            let maxBottom = navRect ? navRect.bottom : 0;

            // Known sticky elements in this app that sit at/near the top of the viewport.
            const candidates = [
                '#stickyResultsBar',
                '.control-bar',
                '.search-box',
                '.header'
            ];

            candidates.forEach(function(sel) {
                const el = document.querySelector(sel);
                if (!el) return;
                const style = window.getComputedStyle(el);
                if (!style) return;
                if (style.display === 'none' || style.visibility === 'hidden') return;

                const pos = (style.position || '').toLowerCase();
                if (pos !== 'sticky' && pos !== 'fixed') return;

                const rect = el.getBoundingClientRect();
                if (!rect || rect.height < 2) return;

                // Only treat it as part of the sticky stack if it's currently pinned near the top stack.
                if (rect.top <= maxBottom + 2) {
                    maxBottom = Math.max(maxBottom, rect.bottom);
                }
            });

            if (maxBottom > 0) {
                document.documentElement.style.setProperty('--global-sticky-top-offset', `${Math.ceil(maxBottom)}px`);
            }
        } catch (e) {
        }
    }

    function ensureStyles() {
        if (document.getElementById("global-nav-styles")) return;
        const style = document.createElement("style");
        style.id = "global-nav-styles";
        style.textContent = STYLES;
        document.head.appendChild(style);
    }

    function buildNav() {
        const nav = document.createElement("nav");
        nav.className = "global-nav";
        const inner = document.createElement("div");
        inner.className = "nav-inner";

        const left = document.createElement('div');
        left.className = 'nav-left';

        const right = document.createElement('div');
        right.className = 'nav-right';

        const brand = document.createElement("div");
        brand.className = "brand";
        brand.innerHTML = `
            <span class="brand-title">${NAV_CONFIG.brandIcon || ''}${NAV_CONFIG.brandTitle}</span>
            <span class="brand-subtitle">${NAV_CONFIG.brandSubtitle}</span>
        `;

        const actionsWrapper = document.createElement("div");
        actionsWrapper.className = "nav-actions";

        const notesBtn = document.createElement("button");
        notesBtn.className = "nav-link notes-btn";
        notesBtn.type = 'button';
        notesBtn.onclick = () => window.NotesManager?.toggleNotesDrawer();
        notesBtn.setAttribute('aria-label', 'Notes');
        notesBtn.innerHTML = `
            <span class="notes-btn-icon" aria-hidden="true">${ICONS.notes}</span>
            <span class="notes-btn-label">Notes</span>
            <span class="notes-btn-badge" id="globalNotesCountBadge" style="display: none;">0</span>
        `;

        const currentPath = (window.location.pathname || "").replace(/\/+$/, "") || "/";
        const currentHash = window.location.hash || "";

        left.appendChild(notesBtn);

        NAV_CONFIG.links.forEach((link) => {
            const anchor = document.createElement("a");
            anchor.className = "nav-link";
            anchor.href = link.href;
            if (link.icon) {
                anchor.innerHTML = `<span class="nav-link-icon" aria-hidden="true">${link.icon}</span><span class="nav-link-label">${link.label}</span>`;
                if (link.iconLabel) {
                    anchor.setAttribute('aria-label', link.iconLabel);
                } else {
                    anchor.setAttribute('aria-label', link.label);
                }
                if (link.iconOnly) {
                    anchor.classList.add('icon-only');
                }
            } else {
                anchor.textContent = link.label;
                anchor.setAttribute('aria-label', link.label);
            }

            const [linkPath, linkHash = ""] = link.href.split("#");
            const normalizedLinkPath = (linkPath || "").replace(/\/+$/, "") || "/";
            const isActive =
                normalizedLinkPath === currentPath &&
                (linkHash ? `#${linkHash}` === currentHash : true);

            if (isActive) {
                anchor.classList.add("active");
            }

            actionsWrapper.appendChild(anchor);
        });

        const hamburgerBtn = document.createElement('button');
        hamburgerBtn.className = 'nav-link nav-hamburger';
        hamburgerBtn.type = 'button';
        hamburgerBtn.setAttribute('aria-label', 'Menu');
        hamburgerBtn.setAttribute('aria-expanded', 'false');
        hamburgerBtn.innerHTML = `<span class="nav-link-icon" aria-hidden="true">${ICONS.menu}</span>`;
        hamburgerBtn.onclick = function() {
            menuState.hamburgerBtn = hamburgerBtn;
            setMenuOpen(!menuState.isOpen);
        };
        actionsWrapper.appendChild(hamburgerBtn);

        right.appendChild(actionsWrapper);

        inner.appendChild(left);
        inner.appendChild(brand);
        inner.appendChild(right);
        nav.appendChild(inner);
        return nav;
    }

    async function initGlobalNav() {
        try {
            const params = new URLSearchParams(window.location.search);
            if (params.get('embed') === '1') return;
        } catch (e) {
        }
        if (document.body.classList.contains("has-global-nav")) return;
        ensureStyles();
        installZoomGuards();
        const nav = buildNav();
        document.body.insertAdjacentElement("afterbegin", nav);
        document.body.classList.add("has-global-nav");

        await initOfflinePOC();

        ensureMenu();
        ensureScrollControls();
        updateScrollControls();
        window.addEventListener('scroll', updateScrollControls, { passive: true });

        ensureScrollLockHandlers();
        updateBodyScrollLock();
        try {
            const overlayObserver = new MutationObserver(() => {
                updateBodyScrollLock();
                updateScrollControls();
            });
            overlayObserver.observe(document.body, { childList: true, subtree: true, attributes: true, attributeFilter: ['class'] });
            overlayObserver.observe(document.documentElement, { attributes: true, attributeFilter: ['class'] });
        } catch (e) {
        }

        const setNavHeight = () => {
            const height = Math.ceil(nav.getBoundingClientRect().height);
            if (height > 0) {
                document.documentElement.style.setProperty('--global-nav-height', `${height}px`);
                document.documentElement.style.setProperty('--global-sticky-top-offset', `${height}px`);
            }
            updateScrollControls();
            updateBodyScrollLock();
        };
        setNavHeight();
        window.addEventListener('resize', setNavHeight);
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", initGlobalNav);
    } else {
        initGlobalNav();
    }
})();
