/*
 * app.js — Artifact frontend
 *
 * Landing page auth + chat SPA + context panel.
 * Vanilla JS, no dependencies beyond space.js for the background.
 */

(function () {
  'use strict';

  // --- State ---
  let currentTone = 'casual';
  let pendingJobId = null;
  let pollTimer = null;
  let pollErrors = 0;
  const MAX_POLL_ERRORS = 10;
  let bridgeTimer = null;
  let contextOpen = false;

  // --- DOM refs ---
  const landing = document.getElementById('landing');
  const chatShell = document.getElementById('chat-shell');
  const contextPanel = document.getElementById('context-panel');
  const contextBody = document.getElementById('context-body');
  const chatLog = document.getElementById('chat-log');
  const chatArea = document.getElementById('chat-area');
  const msgInput = document.getElementById('msg-input');
  const sendBtn = document.getElementById('send-btn');
  const bridgeDot = document.getElementById('bridge-dot');
  const bridgeLabel = document.getElementById('bridge-label');
  const usageBadge = document.getElementById('usage-badge');
  const contextToggle = document.getElementById('context-toggle');

  // --- Auth ---

  const keyForm = document.getElementById('key-form');
  const keyInput = document.getElementById('key-input');
  const keyError = document.getElementById('key-error');

  if (keyForm) {
    keyForm.addEventListener('submit', async (e) => {
      e.preventDefault();
      const key = keyInput.value.trim();
      if (!key) return;

      keyError.textContent = '';
      keyInput.disabled = true;

      try {
        const resp = await fetch('api/auth.php', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ key }),
        });
        const data = await resp.json();

        if (!data.ok) {
          keyError.textContent = data.error === 'invalid_key'
            ? 'Invalid API key' : (data.error || 'Authentication failed');
          keyInput.disabled = false;
          return;
        }

        // Success — switch to chat
        enterChat(data.usage);
      } catch (err) {
        keyError.textContent = 'Connection error';
        keyInput.disabled = false;
      }
    });
  }

  function enterChat(usage) {
    landing.classList.add('hidden');
    chatShell.classList.remove('hidden');
    updateUsage(usage);
    loadHistory();
    startBridgePolling();
    msgInput.focus();
  }

  // --- Usage ---

  function updateUsage(usage) {
    if (!usage || !usageBadge) return;
    const remaining = usage.remaining || 0;
    const budget = usage.budget || 0;
    const pct = budget > 0 ? Math.round((remaining / budget) * 100) : 0;
    usageBadge.textContent = `${remaining.toLocaleString()} tokens (${pct}%)`;
    usageBadge.classList.toggle('low', pct < 20);
    usageBadge.classList.toggle('empty', remaining <= 0);
  }

  async function refreshUsage() {
    try {
      const resp = await fetch('api/usage.php');
      const data = await resp.json();
      if (data.ok) updateUsage(data.usage);
    } catch (e) { /* ignore */ }
  }

  // --- Tone chips ---

  function selectTone(chip) {
    document.querySelectorAll('.tone-chip').forEach(c => {
      c.classList.remove('active');
      c.setAttribute('aria-pressed', 'false');
    });
    chip.classList.add('active');
    chip.setAttribute('aria-pressed', 'true');
    currentTone = chip.dataset.tone;
  }

  document.querySelectorAll('.tone-chip').forEach(chip => {
    chip.addEventListener('click', () => selectTone(chip));
    chip.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' || e.key === ' ') {
        e.preventDefault();
        selectTone(chip);
      }
    });
  });

  // --- Chat form ---

  const chatForm = document.getElementById('chat-form');
  if (chatForm) {
    chatForm.addEventListener('submit', async (e) => {
      e.preventDefault();
      const message = msgInput.value.trim();
      if (!message || pendingJobId) return;

      // Show visitor message immediately
      appendMessage('visitor', message);
      msgInput.value = '';
      autoResize(msgInput);

      // Disable send while processing
      sendBtn.disabled = true;

      // Show breathing indicator
      const pending = appendPending();

      // Submit
      try {
        const resp = await fetch('api/submit.php', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ message, tone: currentTone }),
        });
        const data = await resp.json();

        if (!data.ok) {
          removePending(pending);
          sendBtn.disabled = false;
          if (data.error === 'budget_exhausted') {
            appendSystem(data.message || 'Token budget exhausted. Thanks for exploring!');
          } else if (data.error === 'bridge_busy') {
            appendSystem('The system is processing another request. Please wait a moment.');
          } else {
            appendSystem('Error: ' + (data.error || 'unknown'));
          }
          return;
        }

        pendingJobId = data.job_id;
        startPolling(pending);
      } catch (err) {
        removePending(pending);
        sendBtn.disabled = false;
        appendSystem('Connection error. Please try again.');
      }
    });
  }

  // Auto-resize textarea
  if (msgInput) {
    msgInput.addEventListener('input', () => autoResize(msgInput));
    msgInput.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        chatForm.dispatchEvent(new Event('submit'));
      }
    });
  }

  function autoResize(el) {
    el.style.height = 'auto';
    el.style.height = Math.min(el.scrollHeight, 200) + 'px';
  }

  // --- Message rendering ---

  function appendMessage(actor, text, spans, timestamp) {
    const turn = document.createElement('div');
    turn.className = 'turn';

    const msg = document.createElement('div');
    msg.className = `msg ${actor === 'visitor' ? 'visitor' : 'artifact'}`;

    const actorEl = document.createElement('span');
    actorEl.className = 'actor';
    actorEl.textContent = actor;
    msg.appendChild(actorEl);

    const body = document.createElement('div');
    body.className = 'body';

    if (spans && spans.length > 0) {
      spans.forEach(span => {
        const p = document.createElement('p');
        p.className = span.tag === 'do' ? 'display-do' :
                       span.tag === 'narrate' ? 'display-narrate' : 'display-say';
        p.innerHTML = renderMarkdown(escapeHtml(span.content));
        body.appendChild(p);
      });
    } else {
      const p = document.createElement('p');
      p.innerHTML = renderMarkdown(escapeHtml(text));
      body.appendChild(p);
    }

    msg.appendChild(body);

    const meta = document.createElement('div');
    meta.className = 'msg-meta';
    const timeEl = document.createElement('time');
    timeEl.className = 'msg-time';
    const ts = timestamp ? new Date(timestamp) : new Date();
    timeEl.textContent = ts.toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' });
    meta.appendChild(timeEl);
    msg.appendChild(meta);

    turn.appendChild(msg);
    chatLog.appendChild(turn);
    scrollToBottom();
  }

  function appendSystem(text) {
    const turn = document.createElement('div');
    turn.className = 'turn';
    const msg = document.createElement('div');
    msg.className = 'msg system';
    const body = document.createElement('div');
    body.className = 'body';
    body.textContent = text;
    msg.appendChild(body);
    turn.appendChild(msg);
    chatLog.appendChild(turn);
    scrollToBottom();
  }

  function appendPending() {
    const turn = document.createElement('div');
    turn.className = 'turn pending';
    turn.innerHTML = '<div class="breathing"></div>';
    chatLog.appendChild(turn);
    scrollToBottom();
    return turn;
  }

  function removePending(el) {
    if (el && el.parentNode) el.parentNode.removeChild(el);
  }

  function escapeHtml(str) {
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
  }

  function renderMarkdown(text) {
    // **bold** then *italic*
    text = text.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
    text = text.replace(/\*(.+?)\*/g, '<em>$1</em>');
    // newlines
    text = text.replace(/\n/g, '<br>');
    return text;
  }

  function scrollToBottom() {
    if (chatArea) {
      chatArea.scrollTop = chatArea.scrollHeight;
    }
  }

  // --- Polling for job completion ---

  function startPolling(pendingEl) {
    if (pollTimer) clearInterval(pollTimer);
    pollTimer = setInterval(() => pollJob(pendingEl), 1200);
  }

  async function pollJob(pendingEl) {
    if (!pendingJobId) {
      clearInterval(pollTimer);
      return;
    }

    try {
      const resp = await fetch(`api/status.php?id=${encodeURIComponent(pendingJobId)}`);
      const data = await resp.json();
      pollErrors = 0;

      if (!data.ok) {
        clearInterval(pollTimer);
        removePending(pendingEl);
        appendSystem('Error checking response status.');
        pendingJobId = null;
        return;
      }

      if (data.status === 'queued' || data.status === 'running') {
        return; // still working
      }

      clearInterval(pollTimer);
      removePending(pendingEl);

      sendBtn.disabled = false;

      if (data.status === 'error') {
        appendSystem('Error: ' + (data.error || 'unknown error'));
      } else if (data.status === 'done') {
        const actor = data.actor || 'artifact';
        const display = data.display || [];
        if (display.length > 0) {
          appendMessage(actor, '', display);
        }
        refreshUsage();
        refreshContext();
      }

      pendingJobId = null;
    } catch (err) {
      pollErrors++;
      if (pollErrors >= MAX_POLL_ERRORS) {
        clearInterval(pollTimer);
        removePending(pendingEl);
        sendBtn.disabled = false;
        appendSystem('Connection lost. Please refresh and try again.');
        pendingJobId = null;
      }
    }
  }

  // --- Bridge status ---

  function startBridgePolling() {
    checkBridge();
    bridgeTimer = setInterval(checkBridge, 10000);
  }

  async function checkBridge() {
    try {
      const resp = await fetch('api/status.php');
      const data = await resp.json();
      if (data.ok) {
        const online = data.online;
        bridgeDot.className = 'bridge-dot ' + (online ? 'online' : 'offline');
        bridgeLabel.textContent = online ? 'online' : 'offline';
      }
    } catch (e) {
      bridgeDot.className = 'bridge-dot offline';
      bridgeLabel.textContent = 'offline';
    }
  }

  // --- History ---

  async function loadHistory() {
    try {
      const resp = await fetch('api/history.php?limit=50');
      const data = await resp.json();
      if (!data.ok || !data.entries) return;

      data.entries.forEach(entry => {
        const ts = entry.ts || null;
        // Visitor message
        if (entry.mono) {
          const actor = entry.mono.actor || 'visitor';
          appendMessage(actor, entry.mono.text || '', null, ts);
        }
        // Claude response
        if (entry.claude && entry.claude.display && entry.claude.display.length > 0) {
          const actor = entry.claude.actor || 'artifact';
          appendMessage(actor, '', entry.claude.display, ts);
        }
      });
    } catch (e) { /* ignore */ }
  }

  // --- Context panel ---

  if (contextToggle) {
    contextToggle.addEventListener('click', () => {
      contextOpen = !contextOpen;
      contextPanel.classList.toggle('open', contextOpen);
      contextToggle.classList.toggle('active', contextOpen);
      if (contextOpen) refreshContext();
    });
  }

  async function refreshContext() {
    if (!contextOpen) return;

    try {
      const resp = await fetch('api/context.php');
      const data = await resp.json();
      if (!data.ok || !data.context) return;

      const ctx = data.context;
      let html = '';

      // Turn counter
      html += `<div class="ctx-section"><h3>Turn</h3><p>${ctx.turn}</p></div>`;

      // Usage
      if (ctx.usage) {
        const pct = ctx.usage.budget > 0
          ? Math.round((ctx.usage.remaining / ctx.usage.budget) * 100) : 0;
        html += `<div class="ctx-section"><h3>Token Budget</h3>`;
        html += `<p>${ctx.usage.remaining.toLocaleString()} / ${ctx.usage.budget.toLocaleString()} (${pct}%)</p>`;
        html += `</div>`;
      }

      // Working memory
      html += `<div class="ctx-section"><h3>Working Memory</h3>`;
      if (ctx.working_memory && ctx.working_memory.length > 0) {
        html += '<ul>';
        ctx.working_memory.forEach(item => {
          html += `<li><span class="wm-type">[${escapeHtml(item.type)}]</span> ${escapeHtml(item.content)}</li>`;
        });
        html += '</ul>';
      } else {
        html += '<p class="empty">No active items</p>';
      }
      html += '</div>';

      // Events
      html += `<div class="ctx-section"><h3>Events Logged</h3><p>${ctx.events_count}</p></div>`;

      // Pending recall
      html += `<div class="ctx-section"><h3>Pending Recall</h3>`;
      if (ctx.pending_recall && ctx.pending_recall.length > 0) {
        html += '<ul>';
        ctx.pending_recall.forEach(r => {
          html += `<li><strong>[${escapeHtml(r.key)}]</strong> (${escapeHtml(r.depth)})`;
          if (r.neighbors && r.neighbors.length > 0) {
            html += '<ul>';
            r.neighbors.forEach(n => {
              html += `<li class="neighbor">[${escapeHtml(n.key)}] ${escapeHtml(n.relation || '')}</li>`;
            });
            html += '</ul>';
          }
          html += '</li>';
        });
        html += '</ul>';
      } else {
        html += '<p class="empty">None</p>';
      }
      html += '</div>';

      contextBody.innerHTML = html;
    } catch (e) {
      contextBody.innerHTML = '<p class="empty">Failed to load context</p>';
    }
  }

  // --- Check if already authenticated (session cookie) ---

  async function checkExistingSession() {
    try {
      const resp = await fetch('api/usage.php');
      if (resp.status === 200) {
        const data = await resp.json();
        if (data.ok) {
          enterChat(data.usage);
          return;
        }
      }
    } catch (e) { /* not logged in */ }
  }

  checkExistingSession();
})();
