// Shared Notes Manager - Persistent note-taking across all pages
(() => {
    if (window.__TuneTunerNotesManagerLoaded) return;
    window.__TuneTunerNotesManagerLoaded = true;

    const NOTES_STORAGE_KEY = 'tuneTunerNotes';
    const NOTES_VERSION = 'v1';

    // Notes data structure
    let notesData = {
        version: NOTES_VERSION,
        notes: [],
        freeformText: ''
    };

    // Load notes from localStorage
    function loadNotes() {
        try {
            const stored = localStorage.getItem(NOTES_STORAGE_KEY);
            if (stored) {
                const parsed = JSON.parse(stored);
                if (parsed.version === NOTES_VERSION) {
                    notesData = parsed;
                }
            }
        } catch (error) {
            console.warn('Failed to load notes:', error);
        }
    }

    // Save notes to localStorage
    function saveNotes() {
        try {
            localStorage.setItem(NOTES_STORAGE_KEY, JSON.stringify(notesData));
        } catch (error) {
            console.warn('Failed to save notes:', error);
        }
    }

    // Add a note
    function addNote(text) {
        if (!text || !text.trim()) return;
        const note = {
            id: Date.now() + Math.random().toString(36).substr(2, 9),
            text: text.trim(),
            timestamp: Date.now()
        };
        notesData.notes.unshift(note);
        saveNotes();
        renderNotes();
        showNotification('Note added!');
    }

    // Delete a note
    function deleteNote(id) {
        notesData.notes = notesData.notes.filter(n => n.id !== id);
        saveNotes();
        renderNotes();
    }

    // Update freeform text
    function updateFreeform(text) {
        notesData.freeformText = text;
        saveNotes();
    }

    // Clear all notes
    function clearAllNotes() {
        if (confirm('Clear all notes? This cannot be undone.')) {
            notesData.notes = [];
            notesData.freeformText = '';
            saveNotes();
            renderNotes();
            showNotification('All notes cleared');
        }
    }

    function copyTextToClipboard(text) {
        const value = (text || '').toString();
        if (!value) return;
        if (window.SharedInteractions && typeof window.SharedInteractions.copyToClipboard === 'function') {
            window.SharedInteractions.copyToClipboard(value);
            return;
        }
        try {
            navigator.clipboard.writeText(value);
        } catch (e) {
        }
    }

    function copyAllNotes() {
        const text = (notesData.notes || []).map(n => (n && n.text ? n.text : '')).filter(Boolean).join('\n');
        if (!text) return;
        copyTextToClipboard(text);
        showNotification('Copied all notes');
    }

    // Show notification
    function showNotification(message) {
        const existing = document.getElementById('notesNotification');
        if (existing) existing.remove();

        const notif = document.createElement('div');
        notif.id = 'notesNotification';
        notif.style.cssText = 'position: fixed; left: 50%; bottom: calc(18px + env(safe-area-inset-bottom, 0px)); transform: translateX(-50%); background: rgba(31, 27, 22, 0.92); color: #fff; padding: 12px 18px; border-radius: 999px; z-index: 10110; font-size: 0.95rem; box-shadow: 0 6px 18px rgba(0,0,0,0.25); max-width: calc(100vw - 24px); white-space: nowrap;';
        notif.textContent = message;
        document.body.appendChild(notif);

        setTimeout(() => {
            notif.style.opacity = '0';
            notif.style.transition = 'opacity 0.25s';
            setTimeout(() => notif.remove(), 260);
        }, 1400);
    }

    // Render notes in drawer
    function renderNotes() {
        const container = document.getElementById('notesListContainer');
        const freeformArea = document.getElementById('notesFreeform');
        const countLine = document.getElementById('notesCountLine');
        const globalBadge = document.getElementById('globalNotesCountBadge');
        
        if (!container) return;

        const count = notesData.notes.length;

        if (countLine) {
            countLine.textContent = count === 1 ? '1 saved item' : (count + ' saved items');
        }
        if (globalBadge) {
            globalBadge.textContent = count;
            globalBadge.style.display = count > 0 ? 'inline-block' : 'none';
        }

        // Render freeform textarea
        if (freeformArea && freeformArea.value !== notesData.freeformText) {
            freeformArea.value = notesData.freeformText;
        }

        // Render notes list
        if (notesData.notes.length === 0) {
            container.innerHTML = '<div style="text-align: center; color: #999; padding: 20px; font-size: 0.9rem;">No saved notes yet.<br><small>Double-click items to add them here.</small></div>';
            return;
        }

        let html = '';
        notesData.notes.forEach(note => {
            const date = new Date(note.timestamp).toLocaleString('en-US', {
                month: 'short',
                day: 'numeric',
                hour: 'numeric',
                minute: '2-digit'
            });
            const encoded = encodeURIComponent(note.text || '');
            html += `
                <div class="note-item" data-id="${note.id}">
                    <div class="note-text" data-clickable data-clickable-mode="copy-only" data-text="${encoded}">${escapeHtml(note.text)}</div>
                    <div class="note-meta">
                        <span class="note-date">${date}</span>
                        <button class="note-delete" onclick="window.NotesManager.deleteNote('${note.id}')" title="Delete note">×</button>
                    </div>
                </div>
            `;
        });
        container.innerHTML = html;

        try {
            if (window.SharedInteractions && typeof window.SharedInteractions.autoApplyClickable === 'function') {
                window.SharedInteractions.autoApplyClickable();
            }
        } catch (e) {
        }
    }

    let isInitialized = false;
    let domObserver = null;

    function getElements() {
        const drawer = document.getElementById('notesDrawer');
        const backdrop = document.getElementById('notesBackdrop');
        return { drawer, backdrop };
    }

    function hardResetOverlayState() {
        const { drawer, backdrop } = getElements();
        document.body.classList.remove('notes-open');
        if (drawer) {
            drawer.classList.remove('show');
            drawer.style.transform = 'translateX(-100%)';
            drawer.style.pointerEvents = 'none';
        }
        if (backdrop) {
            backdrop.classList.remove('show');
            backdrop.style.display = 'none';
            backdrop.style.opacity = '0';
            backdrop.style.pointerEvents = 'none';
        }
    }

    function openNotesDrawer() {
        const { drawer, backdrop } = getElements();
        if (!drawer || !backdrop) {
            init();
        }
        const els = getElements();
        if (!els.drawer || !els.backdrop) return;
        document.body.classList.add('notes-open');
        els.drawer.classList.add('show');
        els.backdrop.classList.add('show');
        els.drawer.style.transform = 'translateX(0)';
        els.drawer.style.pointerEvents = 'auto';
        els.backdrop.style.display = 'block';
        els.backdrop.style.opacity = '1';
        els.backdrop.style.pointerEvents = 'auto';
        renderNotes();
    }

    // Toggle notes drawer
    function toggleNotesDrawer() {
        const { drawer, backdrop } = getElements();
        if (!drawer || !backdrop) {
            init();
        }
        const els = getElements();
        if (!els.drawer || !els.backdrop) return;
        const isOpen = document.body.classList.contains('notes-open');
        if (isOpen) {
            closeNotesDrawer();
        } else {
            openNotesDrawer();
        }
    }

    // Close notes drawer
    function closeNotesDrawer() {
        const { drawer, backdrop } = getElements();
        document.body.classList.remove('notes-open');
        if (drawer) {
            drawer.classList.remove('show');
            drawer.style.transform = 'translateX(-100%)';
            drawer.style.pointerEvents = 'none';
        }
        if (backdrop) {
            backdrop.classList.remove('show');
            backdrop.style.opacity = '0';
            backdrop.style.pointerEvents = 'none';
            backdrop.style.display = 'none';
        }
    }

    // Escape HTML
    function escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    // Initialize notes system
    function init() {
        if (isInitialized) return;
        isInitialized = true;

        loadNotes();

        // Remove any existing injections from prior deploys (even the first one)
        document.querySelectorAll('#notesBackdrop').forEach((el) => el.remove());
        document.querySelectorAll('#notesDrawer').forEach((el) => el.remove());
        document.querySelectorAll('style[data-notes-style="true"]').forEach((el) => el.remove());

        const drawerHTML = `
            <div id="notesBackdrop" class="notes-backdrop" onclick="window.NotesManager.closeNotesDrawer()"></div>
            <div id="notesDrawer" class="notes-drawer">
                <button class="notes-close" onclick="window.NotesManager.closeNotesDrawer()">&times;</button>
                <div class="notes-header">
                    <div style="font-weight: 700; color: #1f1b16; font-size: 1.1rem;">Notes</div>
                    <div id="notesCountLine" style="margin-top: 4px; font-weight: 500; color: #6f675c; font-size: 0.9rem;"></div>
                </div>

                <div class="notes-drawer-content">
                    <div class="notes-freeform-section">
                        <label style="font-size: 0.85rem; color: #6f675c; margin-bottom: 4px; display: block;">Freeform Notes</label>
                        <textarea id="notesFreeform" placeholder="Type your notes here..." style="width: 100%; min-height: 120px; padding: 10px; border: 1px solid #d4cec4; border-radius: 6px; font-size: 0.9rem; font-family: inherit; resize: vertical;"></textarea>
                    </div>
                    
                    <div class="notes-section">
                        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; gap: 10px;">
                            <label style="font-size: 0.85rem; color: #6f675c;">Saved Items</label>
                            <div style="display: flex; gap: 8px; align-items: center;">
                                <button onclick="window.NotesManager.copyAllNotes()" style="font-size: 0.75rem; padding: 6px 12px; background: #f6f4ee; border: 1px solid #d4cec4; border-radius: 999px; cursor: pointer; color: #2c2520; font-weight: 650;">Copy All</button>
                                <button id="notesAddBtn" style="font-size: 0.8rem; padding: 6px 12px; background: #2c2520; border: 1px solid #2c2520; border-radius: 999px; cursor: pointer; color: #fff; font-weight: 600;">Add</button>
                                <button onclick="window.NotesManager.clearAllNotes()" style="font-size: 0.75rem; padding: 6px 12px; background: #f6f4ee; border: 1px solid #d4cec4; border-radius: 999px; cursor: pointer; color: #c33; font-weight: 600;">Clear</button>
                            </div>
                        </div>
                        <div id="notesListContainer"></div>
                    </div>
                </div>
            </div>
        `;
        
        // Inject styles
            const styles = `
            <style data-notes-style="true">
                body.notes-open {
                    overflow: hidden;
                }
                .notes-backdrop {
                    display: none;
                    position: fixed;
                    top: 0;
                    left: 0;
                    width: 100%;
                    height: 100%;
                    background: rgba(0, 0, 0, 0.4);
                    z-index: 10090;
                    opacity: 0;
                    transition: opacity 0.3s ease;
                    pointer-events: none;
                }
                .notes-backdrop.show {
                    opacity: 1;
                    pointer-events: auto;
                }
                .notes-drawer {
                    position: fixed;
                    top: 0;
                    left: 0;
                    width: 420px;
                    max-width: 92vw;
                    height: 100vh;
                    background: #fdfbf7;
                    border-right: 2px solid #d4cec4;
                    box-shadow: 4px 0 12px rgba(0,0,0,0.15);
                    z-index: 10100;
                    overflow: hidden;
                    padding: 20px;
                    transform: translateX(-100%);
                    transition: transform 0.3s ease;
                    pointer-events: none;
                    display: flex;
                    flex-direction: column;
                    box-sizing: border-box;
                }
                .notes-drawer.show {
                    transform: translateX(0);
                    pointer-events: auto;
                }
                .notes-header {
                    padding-top: 34px;
                    padding-bottom: 14px;
                }
                .notes-drawer-content {
                    flex: 1;
                    overflow-y: auto;
                    -webkit-overflow-scrolling: touch;
                    overscroll-behavior: contain;
                    touch-action: pan-y;
                    padding-bottom: calc(90px + env(safe-area-inset-bottom, 0px));
                }

                @media (max-width: 768px) {
                    .notes-drawer {
                        width: 75vw;
                        max-width: 75vw;
                        padding: 18px;
                    }
                    .notes-close {
                        top: 12px;
                        right: 12px;
                    }
                }
                .notes-close {
                    position: absolute;
                    top: 14px;
                    right: 14px;
                    background: transparent;
                    border: none;
                    font-size: 1.8rem;
                    cursor: pointer;
                    color: #1f1b16;
                    padding: 4px 8px;
                    line-height: 1;
                    font-weight: 300;
                    z-index: 10101;
                }
                .notes-close:hover {
                    color: #8b7355;
                }
                .notes-freeform-section {
                    margin-bottom: 24px;
                }
                .notes-section {
                    margin-top: 24px;
                }
                .note-item {
                    background: white;
                    border: 1px solid #e8dcc8;
                    border-radius: 6px;
                    padding: 12px;
                    margin-bottom: 10px;
                    transition: all 0.2s;
                }
                .note-item { cursor: pointer; }
                .note-item:hover {
                    border-color: #d4c4a8;
                    box-shadow: 0 2px 6px rgba(0,0,0,0.08);
                }
                .note-text {
                    font-size: 0.9rem;
                    line-height: 1.5;
                    color: #1f1b16;
                    margin-bottom: 8px;
                    word-wrap: break-word;
                }
                .note-meta {
                    display: flex;
                    justify-content: space-between;
                    align-items: center;
                }
                .note-date {
                    font-size: 0.75rem;
                    color: #999;
                }
                .note-delete {
                    background: transparent;
                    border: none;
                    color: #c33;
                    font-size: 1.3rem;
                    cursor: pointer;
                    padding: 0 4px;
                    line-height: 1;
                }
                .note-delete:hover {
                    color: #a00;
                }
                @keyframes slideIn {
                    from { transform: translateX(20px); opacity: 0; }
                    to { transform: translateX(0); opacity: 1; }
                }
            </style>
        `;
        
        document.head.insertAdjacentHTML('beforeend', styles);
        document.body.insertAdjacentHTML('beforeend', drawerHTML);

        // Initialize drawer after injection
        setTimeout(() => {
            // Setup freeform textarea auto-save with debounce
            const freeformArea = document.getElementById('notesFreeform');
            if (freeformArea) {
                let saveTimeout;
                freeformArea.addEventListener('input', (e) => {
                    clearTimeout(saveTimeout);
                    saveTimeout = setTimeout(() => {
                        updateFreeform(e.target.value);
                    }, 500);
                });
            }

            const addBtn = document.getElementById('notesAddBtn');
            if (addBtn) {
                addBtn.addEventListener('click', () => {
                    const area = document.getElementById('notesFreeform');
                    const selection = area && typeof area.selectionStart === 'number' && typeof area.selectionEnd === 'number'
                        ? area.value.slice(area.selectionStart, area.selectionEnd).trim()
                        : '';
                    const fallback = area ? area.value.trim() : '';
                    const text = selection || (fallback ? fallback : (prompt('Add a note') || '').trim());
                    if (!text) return;
                    addNote(text);
                });
            }

            // Close drawer on backdrop click
            const backdrop = document.getElementById('notesBackdrop');
            if (backdrop) {
                backdrop.addEventListener('click', closeNotesDrawer);
            }

            // ESC closes notes
            window.addEventListener('keydown', (e) => {
                if (e.key === 'Escape' && document.body.classList.contains('notes-open')) {
                    closeNotesDrawer();
                }
            });

            // Initial render
            renderNotes();

            // Ensure we never leave the screen blocked
            hardResetOverlayState();
            
            // Apply noteable behavior initially and on DOM changes
            autoApplyNoteable();
            
            // Watch for new elements and apply noteable behavior
            if (domObserver) {
                try { domObserver.disconnect(); } catch (e) {}
            }
            domObserver = new MutationObserver(() => {
                autoApplyNoteable();

                // Watchdog: if backdrop is visible but body isn't open, hard reset
                const bd = document.getElementById('notesBackdrop');
                if (bd && bd.classList.contains('show') && !document.body.classList.contains('notes-open')) {
                    hardResetOverlayState();
                }
            });
            domObserver.observe(document.body, { childList: true, subtree: true });
        }, 100);
    }

    function _getOriginalClickExecutor(element) {
        const prop = element.__notesOriginalOnClickFn;
        const attr = element.__notesOriginalOnClickAttr;

        if (typeof prop === 'function') {
            return function(ev) {
                try {
                    prop.call(element, ev);
                } catch (error) {
                    console.warn('Failed to run original click handler:', error);
                }
            };
        }

        if (attr && typeof attr === 'string') {
            return function() {
                try {
                    // eslint-disable-next-line no-new-func
                    Function(attr).call(element);
                } catch (error) {
                    console.warn('Failed to eval original onclick attribute:', error);
                }
            };
        }

        return null;
    }

    // Helper to make elements single-click copy, double-click add-to-notes
    function makeNoteable(element, textGetter) {
        let singleClickTimer = null;
        const runOriginal = _getOriginalClickExecutor(element);

        function getText() {
            return typeof textGetter === 'function' ? textGetter(element) : (element.textContent || '').trim();
        }

        function flashFeedback() {
            const prevOutline = element.style.outline;
            const prevBoxShadow = element.style.boxShadow;
            element.style.outline = '2px solid rgba(45, 80, 22, 0.45)';
            element.style.boxShadow = '0 0 0 2px rgba(45, 80, 22, 0.15) inset';
            setTimeout(() => {
                element.style.outline = prevOutline;
                element.style.boxShadow = prevBoxShadow;
            }, 180);
        }

        element.addEventListener('click', (e) => {
            // We own the click: single click copies, then replays original click action.
            e.preventDefault();
            e.stopPropagation();
            if (typeof e.stopImmediatePropagation === 'function') {
                e.stopImmediatePropagation();
            }

            if (singleClickTimer) {
                clearTimeout(singleClickTimer);
                singleClickTimer = null;
            }

            singleClickTimer = setTimeout(() => {
                const text = getText();
                if (text) {
                    navigator.clipboard.writeText(text).then(() => {
                        flashFeedback();
                    });
                }
                // Preserve existing UX by running the original click after copy.
                if (typeof runOriginal === 'function') {
                    runOriginal(e);
                }
            }, 220);
        }, true);

        element.addEventListener('dblclick', (e) => {
            // Double click: add to notes, do NOT run original click (prevents drawer/bubble veils).
            if (singleClickTimer) {
                clearTimeout(singleClickTimer);
                singleClickTimer = null;
            }
            e.preventDefault();
            e.stopPropagation();
            if (typeof e.stopImmediatePropagation === 'function') {
                e.stopImmediatePropagation();
            }
            const text = getText();
            if (!text) return;
            addNote(text);
            flashFeedback();
        }, true);
    }

    // Apply noteable behavior to all matching elements
    function applyNoteableToElements(selector, textGetter, options) {
        const opts = options || {};
        const captureOriginalClick = opts.captureOriginalClick !== false;
        const elements = document.querySelectorAll(selector);
        elements.forEach(el => {
            if (!el.dataset.noteable) {
                if (captureOriginalClick) {
                    // Capture original click behavior so we can replay it after copying.
                    if (el.getAttribute) {
                        const attr = el.getAttribute('onclick');
                        if (attr) {
                            el.__notesOriginalOnClickAttr = attr;
                            el.removeAttribute('onclick');
                        }
                    }
                    if (typeof el.onclick === 'function') {
                        el.__notesOriginalOnClickFn = el.onclick;
                        try { el.onclick = null; } catch (e) {}
                    }
                }
                makeNoteable(el, textGetter);
                el.dataset.noteable = 'true';
                el.style.cursor = 'pointer';
                el.title = 'Click to copy, double-click to add to notes';
            }
        });
    }

    // Auto-apply to common elements
    function autoApplyNoteable() {
        // Rhyme chips
        applyNoteableToElements('.rhyme-chip:not([data-noteable])', null, { captureOriginalClick: true });
        
        // Tone chips
        applyNoteableToElements('.tone-chip:not([data-noteable])', null, { captureOriginalClick: true });
        
        // Category chips
        applyNoteableToElements('.category-chip:not([data-noteable])', null, { captureOriginalClick: true });
        
        // Tone association tags
        applyNoteableToElements('.tag:not([data-noteable])', null, { captureOriginalClick: true });
        
        // Classification chips
        applyNoteableToElements('.chip:not([data-noteable])', null, { captureOriginalClick: true });
        
        // Motif badges
        applyNoteableToElements('.motif-badge:not([data-noteable])', null, { captureOriginalClick: true });

        // Drawer/sidebar copy buttons across pages
        applyNoteableToElements('button.copy-btn:not([data-noteable])', function(el) {
            const encoded = el.getAttribute('data-text') || '';
            try {
                return decodeURIComponent(encoded);
            } catch (e) {
                return encoded;
            }
        }, { captureOriginalClick: true });

        applyNoteableToElements('button.copy-all-btn:not([data-noteable])', function(el) {
            const encoded = el.getAttribute('data-text') || '';
            try {
                return decodeURIComponent(encoded);
            } catch (e) {
                return encoded;
            }
        }, { captureOriginalClick: true });

        // Creative Gens drawer lines are already copyable; allow dblclick to add
        applyNoteableToElements('.drawer-line:not([data-noteable])', function(el) {
            return (el.textContent || '').trim();
        }, { captureOriginalClick: true });

        // Quotes drawer items
        applyNoteableToElements('.preview-item:not([data-noteable])', function(el) {
            return (el.innerText || el.textContent || '').trim();
        }, { captureOriginalClick: true });

        // Rhyme reference drawer items
        applyNoteableToElements('.rhyme-chip-bubble-item:not([data-noteable])', function(el) {
            return (el.innerText || el.textContent || '').trim();
        }, { captureOriginalClick: true });
    }

    // Export public API
    window.NotesManager = {
        addNote,
        deleteNote,
        clearAllNotes,
        copyAllNotes,
        toggleNotesDrawer,
        closeNotesDrawer,
        openNotesDrawer,
        hardResetOverlayState,
        makeNoteable,
        applyNoteableToElements,
        autoApplyNoteable,
        init
    };

    window.addEventListener('storage', function(e) {
        if (!e) return;
        if (e.key !== NOTES_STORAGE_KEY) return;
        loadNotes();
        renderNotes();
    });

    // Auto-initialize
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
