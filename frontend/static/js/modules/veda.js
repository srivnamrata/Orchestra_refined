import { apiFetch } from './api.js';
import { activityFeed } from './feed.js';

export async function submitVeda(text) {
    const inp = document.getElementById('veda-input');
    if (!text?.trim()) return;
    if (inp) inp.value = '';
    activityFeed.log(`📚 Veda: processing "${text}"`, 'status', 'VEDA');
    try {
        const res  = await apiFetch('/api/veda', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ text }) });
        const data = await res.json();
        if (data.status === 'success') {
            activityFeed.log(`📚 Veda: ${data.result?.message || 'Done!'}`, 'success', 'VEDA');
            setTimeout(() => window.fetchBooks(), 800);
        } else {
            activityFeed.log(`📚 Veda: ${data.message || 'Something went wrong'}`, 'warning', 'VEDA');
        }
    } catch (e) { activityFeed.log('📚 Veda: ' + e.message, 'warning', 'VEDA'); }
}

export async function fetchBooks() {
    const shelf = document.getElementById('bookshelf');
    if (!shelf) return;
    try {
        const res   = await apiFetch('/api/books');
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const books = await res.json();
        if (!books?.length) {
            // Populate with some dummy books
            books.push(
                { title: 'Deep Work', author: 'Cal Newport', pct: 45, status: 'in-progress', current_page: 135, total_pages: 300 },
                { title: 'Thinking, Fast and Slow', author: 'Daniel Kahneman', pct: 100, status: 'done', current_page: 499, total_pages: 499 },
                { title: 'Atomic Habits', author: 'James Clear', pct: 0, status: 'to-read', current_page: 0, total_pages: 320 }
            );
        }
        shelf.innerHTML = books.map(b => {
            const pct  = b.pct || 0;
            const sc   = b.status==='done' ? 'var(--g-green)' : b.status==='in-progress' ? 'var(--g-blue)' : 'var(--md-dim)';
            const sl   = b.status==='done' ? 'Finished' : b.status==='in-progress' ? 'Reading' : 'To Read';
            const safe = t => t.replace(/'/g,"\\'");
            return `
                <div class="run-card" style="display:flex;flex-direction:column;gap:10px">
                    <div style="display:flex;justify-content:space-between;align-items:start">
                        <div><div class="run-title" style="font-size:14px">${b.title}</div><div style="font-size:11px;color:var(--md-dim);margin-top:2px">${b.author||'Unknown author'}</div></div>
                        <span class="chip" style="background:${sc}22;color:${sc};font-size:10px">${sl}</span>
                    </div>
                    ${b.status==='in-progress'?`
                    <div>
                        <div style="display:flex;justify-content:space-between;font-size:10px;color:var(--md-dim);margin-bottom:4px"><span>Page ${b.current_page} / ${b.total_pages}</span><span>${pct}%</span></div>
                        <div class="run-bar-bg"><div class="run-bar-fill" style="width:${pct}%;background:var(--g-blue)"></div></div>
                    </div>`:''}
                    <div style="display:flex;gap:6px">
                        <button class="na-btn" onclick="playAudio('${safe(b.title)} by ${safe(b.author||'')}. You are ${pct} percent through.')">🎧 Listen</button>
                        <button class="na-btn" onclick="activityFeed.log('Veda: Updating progress for ${safe(b.title)}...','status','VEDA')">✏️ Update</button>
                        <button class="na-btn" style="border-color:var(--g-violet)" onclick="window.submitVeda('Give me a key insight from ${safe(b.title)} for my work')">🧠 Insight</button>
                    </div>
                </div>`;
        }).join('');
    } catch (e) {
        shelf.innerHTML = `<div style="grid-column:1/-1;text-align:center;padding:20px;color:var(--g-red)">Could not load books: ${e.message}</div>`;
    }
}

window.submitVeda = submitVeda;
window.fetchBooks = fetchBooks;
