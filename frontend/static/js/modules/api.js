// API base URL — resolved once at load time and shared across all modules.
export const ORCHESTRA_API_BASE = (() => {
    try {
        const params    = new URLSearchParams(window.location.search);
        const queryBase = params.get('api');
        if (queryBase) localStorage.setItem('orchestraApiBase', queryBase);
        const savedBase  = localStorage.getItem('orchestraApiBase');
        const fallback   = window.location.protocol === 'file:'
            ? 'https://orchestra-272079333717.us-central1.run.app'
            : window.location.origin;
        return (queryBase || savedBase || fallback).replace(/\/$/, '');
    } catch (_) {
        return window.location.origin;
    }
})();

export function apiUrl(path) {
    if (/^https?:\/\//i.test(path)) return path;
    return `${ORCHESTRA_API_BASE}${path.startsWith('/') ? path : `/${path}`}`;
}

// ── Session token helpers ────────────────────────────────────────────────────
export function getSessionToken() {
    try { return localStorage.getItem('orch-session-token') || ''; } catch (_) { return ''; }
}

export function setSessionToken(token) {
    try { localStorage.setItem('orch-session-token', token); } catch (_) {}
}

export function clearSessionToken() {
    try { localStorage.removeItem('orch-session-token'); } catch (_) {}
}

export function isAuthenticated() {
    return !!getSessionToken();
}

// ── Authenticated fetch wrapper ──────────────────────────────────────────────
export function apiFetch(path, options = {}) {
    const url     = /^https?:\/\//i.test(path) ? path : apiUrl(path);
    const token   = getSessionToken();
    const headers = { ...(options.headers || {}) };
    if (token) headers['X-Session-Token'] = token;
    return fetch(url, { ...options, headers });
}

// Expose for legacy inline scripts and console debugging
window.ORCHESTRA_API_BASE = ORCHESTRA_API_BASE;
window.apiUrl   = apiUrl;
window.apiFetch = apiFetch;
