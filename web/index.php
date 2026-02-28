<?php
declare(strict_types=1);
?>
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
  <meta name="theme-color" content="#0e0e12">
  <meta name="description" content="Artifact — Persistent Memory for Stateless AI. A live demonstration of context assembly, decay-scored memory, and graph-based knowledge recall.">
  <title>Artifact — Persistent Memory for Stateless AI</title>
  <link rel="manifest" href="manifest.json">
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600&display=swap" rel="stylesheet">
  <link rel="stylesheet" href="static/style.css?v=2">
</head>
<body>

<canvas id="space-canvas"></canvas>

<!-- Landing page (unauthenticated) -->
<div id="landing" class="landing">
  <div class="hero">
    <h1 class="hero-title">artifact</h1>
    <p class="hero-sub">Persistent memory for stateless AI</p>
    <p class="hero-description">
      Every turn, a context window is assembled from scored memory,
      knowledge fragments, and graph recall. The AI wakes up inside it.
    </p>
  </div>

  <div class="assembly">
    <p class="assembly-label">context window &mdash; assembled fresh every turn</p>
    <div class="assembly-window">
      <div class="frag frag-static" style="--delay: 0.2s; --from-x: -35px; --from-y: -20px">
        <span class="frag-type">self-state</span> what I know
      </div>
      <div class="frag frag-summary" style="--delay: 0.6s; --from-x: 30px; --from-y: -25px; --final-opacity: 0.75">
        <span class="frag-type">summaries</span> compressed history
      </div>
      <div class="frag frag-wm" style="--delay: 1.1s; --from-x: -50px; --from-y: 5px; --final-opacity: 0.95">
        <span class="frag-type">lingering</span> current feeling
        <span class="decay-bar" style="--decay: 0.9"></span>
      </div>
      <div class="frag frag-wm" style="--delay: 1.5s; --from-x: 45px; --from-y: 10px; --final-opacity: 0.35">
        <span class="frag-type">lingering</span> old thought
        <span class="decay-bar" style="--decay: 0.25"></span>
      </div>
      <div class="frag frag-recalled" style="--delay: 2.0s; --from-x: 40px; --from-y: 25px; --final-opacity: 0.85">
        <span class="frag-type">recalled</span> crystal fragment
      </div>
      <div class="frag frag-surfaced" style="--delay: 2.4s; --from-x: -40px; --from-y: 25px; --final-opacity: 0.8">
        <span class="frag-type">surfaced</span> related memory
      </div>
      <div class="frag frag-conversation" style="--delay: 2.9s; --from-x: 0px; --from-y: 35px">
        <span class="frag-type">recent</span> conversation &middot; FIFO
      </div>
      <div class="frag frag-hot" style="--delay: 3.4s; --from-x: 0px; --from-y: 30px">
        <span class="frag-type">hot</span> your message
      </div>
    </div>
  </div>

  <p class="key-helper">Private demo. Keys isolate sessions and token budgets per reviewer.</p>

  <form id="key-form" class="key-form">
    <input id="key-input" class="key-input" type="password"
           placeholder="Enter API key..." required autocomplete="off">
    <button class="key-submit" type="submit">explore</button>
    <p id="key-error" class="key-error"></p>
  </form>
</div>

<!-- Chat shell (authenticated) -->
<div id="chat-shell" class="hidden">
  <div class="shell">

    <div class="header">
      <div class="header-left">
        <span class="site-name">artifact</span>
        <div class="bridge-status">
          <span id="bridge-dot" class="bridge-dot"></span>
          <span id="bridge-label">...</span>
        </div>
      </div>
      <div class="header-right">
        <span id="usage-badge" class="usage-badge"></span>
        <button id="context-toggle" class="context-toggle">context</button>
        <button id="logout-btn" class="logout-btn">logout</button>
      </div>
    </div>

    <div id="chat-area" class="chat-area">
      <div id="chat-log"></div>
    </div>

    <div class="input-area">
      <div class="tone-row">
        <button type="button" class="tone-chip active" data-tone="casual" aria-pressed="true">casual</button>
        <button type="button" class="tone-chip" data-tone="technical" aria-pressed="false">technical</button>
        <button type="button" class="tone-chip" data-tone="creative" aria-pressed="false">creative</button>
      </div>
      <form id="chat-form">
        <div class="input-row">
          <textarea id="msg-input" class="msg-input" rows="1"
                    placeholder="Ask about the architecture..." aria-label="Message"></textarea>
          <button type="submit" id="send-btn" class="send-btn">send</button>
        </div>
      </form>
    </div>

  </div>
</div>

<!-- Context panel -->
<div id="context-panel" class="context-panel">
  <h2>Context Inspector</h2>
  <p class="ctx-subtitle">Live snapshot of working memory, recall state, and token usage</p>
  <div id="context-body"></div>
</div>

<script src="static/space.js?v=1"></script>
<script src="static/app.js?v=1"></script>

</body>
</html>