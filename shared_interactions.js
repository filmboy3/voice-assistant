// Shared interaction utilities for click/double-click behavior
(() => {
    if (window.__TuneTunerInteractionsLoaded) return;
    window.__TuneTunerInteractionsLoaded = true;

    function ensureSharedUiStyles() {
        if (document.getElementById('ttSharedUiStyles')) return;
        const style = document.createElement('style');
        style.id = 'ttSharedUiStyles';
        style.textContent = `
            :where(button.copy-btn, button.copy-all-btn, button.load-more-btn, button.panel-more) {
                border-radius: 999px;
                border: 1px solid #d4cec4;
                background: transparent;
                color: #4b4338;
                padding: 8px 14px;
                font-weight: 650;
                cursor: pointer;
            }
            :where(button.copy-btn, button.copy-all-btn, button.load-more-btn, button.panel-more):hover {
                background: #f4eee1;
            }
            :where(.chip, .tag, .category-chip) {
                border-radius: 999px;
            }
            :where([data-clickable], .chip, .tag, .category-chip, .drawer-line, .drawer-item, .rhyme-chip) {
                -webkit-user-select: none;
                user-select: none;
                -webkit-touch-callout: none;
                -webkit-tap-highlight-color: transparent;
                touch-action: manipulation;
            }
            :where([data-clickable].tt-touch-active, .chip.tt-touch-active, .drawer-line.tt-touch-active, .drawer-item.tt-touch-active, .rhyme-chip.tt-touch-active) {
                background: rgba(244, 238, 225, 0.7) !important;
            }
        `;
        document.head.appendChild(style);
    }

    // Show toast notification
    function showToast(message) {
        const existing = document.getElementById('interactionToast');
        if (existing) existing.remove();

        const toast = document.createElement('div');
        toast.id = 'interactionToast';
        toast.style.cssText = 'position: fixed; left: 50%; bottom: 18px; transform: translateX(-50%); background: rgba(31, 27, 22, 0.92); color: #fff; padding: 12px 18px; border-radius: 999px; z-index: 10000; font-size: 0.95rem; box-shadow: 0 6px 18px rgba(0,0,0,0.25); max-width: calc(100vw - 24px); white-space: nowrap;';
        toast.textContent = message;
        document.body.appendChild(toast);

        setTimeout(() => {
            toast.style.opacity = '0';
            toast.style.transition = 'opacity 0.25s';
            setTimeout(() => toast.remove(), 260);
        }, 1400);
    }

    // Copy text to clipboard
    async function copyToClipboard(text) {
        try {
            await navigator.clipboard.writeText(text);
            showToast('Copied!');
            return true;
        } catch (err) {
            console.warn('Clipboard write failed:', err);
            return false;
        }
    }

    // Add text to notes
    function addToNotes(text) {
        if (window.NotesManager && window.NotesManager.addNote) {
            window.NotesManager.addNote(text);
        } else {
            console.warn('NotesManager not available');
        }
    }

    // Make an element clickable with copy/notes behavior
    function makeClickable(element, getText) {
        if (element.__clickableInitialized) return;
        element.__clickableInitialized = true;

        let clickTimeout = null;
        let clickCount = 0;

        let tapTimeout = null;
        let tapCount = 0;

        element.style.cursor = 'pointer';
        element.style.userSelect = 'none';
        element.style.webkitUserSelect = 'none';
        element.style.webkitTouchCallout = 'none';
        element.style.webkitTapHighlightColor = 'transparent';
        element.style.touchAction = 'manipulation';

        let suppressNextClick = false;
        let touchStartX = null;
        let touchStartY = null;
        let touchMoved = false;
        const MOVE_THRESHOLD_PX = 18;

        function resolveText() {
            return typeof getText === 'function' ? getText() : getText;
        }

        function getMode() {
            try {
                return (element.getAttribute('data-clickable-mode') || '').toString().trim();
            } catch (e) {
                return '';
            }
        }

        element.addEventListener('touchstart', (e) => {
            touchMoved = false;
            suppressNextClick = false;
            try {
                const t = e.touches && e.touches[0];
                if (t) {
                    touchStartX = t.clientX;
                    touchStartY = t.clientY;
                }
            } catch (err) {
            }
            element.classList.add('tt-touch-active');
        }, { passive: true });

        element.addEventListener('touchmove', (e) => {
            try {
                const t = e.touches && e.touches[0];
                if (!t || touchStartX === null || touchStartY === null) return;
                const dx = Math.abs(t.clientX - touchStartX);
                const dy = Math.abs(t.clientY - touchStartY);
                if (dx > MOVE_THRESHOLD_PX || dy > MOVE_THRESHOLD_PX) {
                    touchMoved = true;
                    suppressNextClick = true;
                    element.classList.remove('tt-touch-active');
                }
            } catch (err) {
            }
        }, { passive: true });

        element.addEventListener('touchend', () => {
            element.classList.remove('tt-touch-active');

            if (touchMoved) {
                suppressNextClick = true;
                touchMoved = false;
                tapCount = 0;
                if (tapTimeout) {
                    clearTimeout(tapTimeout);
                    tapTimeout = null;
                }
                return;
            }

            suppressNextClick = true;

            tapCount++;
            if (tapCount === 1) {
                tapTimeout = setTimeout(() => {
                    const text = resolveText();
                    if (text) {
                        copyToClipboard(text);
                    }
                    tapCount = 0;
                    tapTimeout = null;
                }, 320);
            } else if (tapCount === 2) {
                if (tapTimeout) {
                    clearTimeout(tapTimeout);
                    tapTimeout = null;
                }
                const mode = getMode();
                if (mode !== 'copy-only') {
                    const text = resolveText();
                    if (text) {
                        addToNotes(text);
                        showToast('Saved to Notes');
                    }
                }
                tapCount = 0;
            }
        }, { passive: true });

        element.addEventListener('touchcancel', () => {
            element.classList.remove('tt-touch-active');
        }, { passive: true });

        element.addEventListener('contextmenu', (e) => {
            e.preventDefault();
        });

        element.addEventListener('click', (e) => {
            if (suppressNextClick || touchMoved) {
                e.preventDefault();
                e.stopPropagation();
                suppressNextClick = false;
                touchMoved = false;
                clickCount = 0;
                return;
            }
            e.preventDefault();
            e.stopPropagation();

            clickCount++;

            if (clickCount === 1) {
                clickTimeout = setTimeout(() => {
                    // Single click: copy
                    const text = resolveText();
                    if (text) {
                        copyToClipboard(text);
                    }
                    clickCount = 0;
                }, 320);
            } else if (clickCount === 2) {
                // Double click: add to notes
                clearTimeout(clickTimeout);
                const mode = getMode();
                if (mode !== 'copy-only') {
                    const text = resolveText();
                    if (text) {
                        addToNotes(text);
                        showToast('Saved to Notes');
                    }
                }
                clickCount = 0;
            }
        });
    }

    // Auto-apply clickable behavior to elements with data-clickable attribute
    function autoApplyClickable() {
        document.querySelectorAll('[data-clickable]:not([data-clickable-initialized])').forEach(el => {
            el.setAttribute('data-clickable-initialized', 'true');
            const rawAttr = el.getAttribute('data-text');
            let text = rawAttr || el.textContent;
            if (rawAttr) {
                try {
                    if (rawAttr.includes('%')) {
                        text = decodeURIComponent(rawAttr);
                    }
                } catch (e) {
                }
            }
            makeClickable(el, text);
        });
    }

    // Expose public API
    window.SharedInteractions = {
        showToast,
        copyToClipboard,
        addToNotes,
        makeClickable,
        autoApplyClickable,
        ensureSharedUiStyles
    };

    // Auto-apply on DOM changes
    const observer = new MutationObserver(() => {
        autoApplyClickable();
    });

    // Start observing after DOM is ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', () => {
            ensureSharedUiStyles();
            autoApplyClickable();
            observer.observe(document.body, { childList: true, subtree: true });
        });
    } else {
        ensureSharedUiStyles();
        autoApplyClickable();
        observer.observe(document.body, { childList: true, subtree: true });
    }
})();
