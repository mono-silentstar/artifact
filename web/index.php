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
  <link rel="stylesheet" href="static/style.css?v=1">
</head>
<body>

<canvas id="space-canvas"></canvas>

<!-- Landing page (unauthenticated) -->
<div id="landing" class="landing">
  <div class="hero">
    <h1 class="hero-title">artifact</h1>
    <p class="hero-sub">Persistent Memory for Stateless AI</p>
    <p class="hero-description">
      Claude is stateless — every conversation starts from zero.
      Artifact gives it continuity: a memory system built from
      decay-scored knowledge, graph-connected fragments, and
      context assembly that constructs what the AI wakes up inside.
    </p>
  </div>

  <div class="how-it-works">
    <div class="step">
      <span class="step-num">1</span>
      <span class="step-label">Knowledge stored as fragments with three depth tiers</span>
    </div>
    <div class="step">
      <span class="step-num">2</span>
      <span class="step-label">Working memory decays naturally over time and turns</span>
    </div>
    <div class="step">
      <span class="step-num">3</span>
      <span class="step-label">Context assembled fresh for every conversation turn</span>
    </div>
    <div class="step">
      <span class="step-num">4</span>
      <span class="step-label">Graph edges connect related knowledge for recall</span>
    </div>
  </div>

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
      </div>
    </div>

    <div id="chat-area" class="chat-area">
      <div id="chat-log"></div>
    </div>

    <div class="input-area">
      <div class="tone-row">
        <span class="tone-chip active" data-tone="casual" role="button" tabindex="0" aria-pressed="true">casual</span>
        <span class="tone-chip" data-tone="technical" role="button" tabindex="0" aria-pressed="false">technical</span>
        <span class="tone-chip" data-tone="creative" role="button" tabindex="0" aria-pressed="false">creative</span>
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
  <h2>What Claude Sees</h2>
  <div id="context-body"></div>
</div>

<script src="static/space.js?v=1"></script>
<script src="static/app.js?v=1"></script>

</body>
</html>