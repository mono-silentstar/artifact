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
      <div class="frag frag-ambient" style="--delay: 0.3s; --from-x: -40px; --from-y: -20px">
        <span class="frag-type">ambient</span> personality &middot; tone
      </div>
      <div class="frag frag-ambient" style="--delay: 0.6s; --from-x: 35px; --from-y: -25px">
        <span class="frag-type">ambient</span> boundaries &middot; voice
      </div>
      <div class="frag frag-knowledge" style="--delay: 1.0s; --from-x: 45px; --from-y: -15px">
        <span class="frag-type">knowledge</span> domain expertise
      </div>
      <div class="frag frag-wm" style="--delay: 1.5s; --from-x: -50px; --from-y: 10px; --final-opacity: 0.95">
        <span class="frag-type">memory</span> current mood
        <span class="decay-bar" style="--decay: 0.9"></span>
      </div>
      <div class="frag frag-wm" style="--delay: 1.9s; --from-x: 45px; --from-y: 15px; --final-opacity: 0.4">
        <span class="frag-type">memory</span> old observation
        <span class="decay-bar" style="--decay: 0.3"></span>
      </div>
      <div class="frag frag-surfaced" style="--delay: 2.5s; --from-x: 0px; --from-y: 35px; --final-opacity: 0.85">
        <span class="frag-type">surfaced</span> recalled fragment
      </div>
      <div class="frag frag-summary" style="--delay: 3.1s; --from-x: 30px; --from-y: 30px; --final-opacity: 0.7">
        <span class="frag-type">summary</span> compressed history
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