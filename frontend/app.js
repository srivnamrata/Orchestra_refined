/**
 * Orchestra — ES module entry point.
 *
 * Each import triggers the module's side-effects (window.xxx assignments)
 * and exports, so all public API is available for inline HTML handlers before
 * the user can interact with the page.
 *
 * Module responsibilities:
 *   api.js        — ORCHESTRA_API_BASE, apiUrl()
 *   feed.js       — activityFeed (generative UI, widget rendering)
 *   navigation.js — switchView(), openPalette(), keyboard shortcuts
 *   audio.js      — playAudio(), toggleVoiceInput()
 *   renderers.js  — renderNews(), renderTasks(), renderResearch(), …
 *   goal.js       — submitGoal() + SSE streaming
 *   demos.js      — runDemo(), fetchIntel(), switchIntel()
 *   veda.js       — submitVeda(), fetchBooks()
 *   guru.js       — runGuruAudit()
 *   theme.js      — applyTheme(), toggleTheme()
 *   helpers.js    — exportTasks(), setGoal(), autoExpandGoal(), …
 *   monitor.js    — runScan(), clearScan(), switchTraceAgent(), …
 *   init.js       — initUI(), clock, DOMContentLoaded bootstrap
 */

import './static/js/modules/api.js';
import './static/js/modules/feed.js';
import './static/js/modules/navigation.js';
import './static/js/modules/audio.js';
import './static/js/modules/renderers.js';
import './static/js/modules/theme.js';
import './static/js/modules/helpers.js';
import './static/js/modules/goal.js';
import './static/js/modules/demos.js';
import './static/js/modules/veda.js';
import './static/js/modules/guru.js?v=2';
import './static/js/modules/integrations.js';
import './static/js/modules/monitor.js?v=2';
import './static/js/modules/audits.js?v=2';
import './static/js/modules/init.js';
