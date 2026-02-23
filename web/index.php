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
    <p class="hero-sub">A public demo of a private memory architecture for stateless AI</p>
    <p class="hero-description">
      Artifact is a live slice of the Silentstar memory system.
      Every conversation turn, it assembles a fresh context window from
      decay-scored working memory, graph-connected knowledge fragments,
      and recent conversation history — then hands it to Claude, who wakes
      up inside it with no memory of its own.
      Open the Context Inspector to see exactly what gets built.
    </p>
  </div>

  <div class="how-it-works">
    <div class="step">
      <span class="step-num">1</span>
      <span class="step-label">Knowledge lives in fragments — three depth tiers, from ambient to deep inventory</span>
    </div>
    <div class="step">
      <span class="step-num">2</span>
      <span class="step-label">Working memory decays with type-specific half-lives — feelings fade fast, pins persist</span>
    </div>
    <div class="step">
      <span class="step-num">3</span>
      <span class="step-label">Every turn, context is assembled fresh — the AI wakes up inside the result</span>
    </div>
    <div class="step">
      <span class="step-num">4</span>
      <span class="step-label">Graph edges connect fragments — the AI can recall related knowledge on demand</span>
    </div>
  </div>

  <div class="architecture-map">
    <h3 class="map-title">Architecture Map</h3>
    <div class="map-grid">
      <div class="map-item">
        <span class="map-icon">Heart</span>
        <span class="map-chip live">Live in demo</span>
        <span class="map-desc">Conversational instance — the AI you're talking to</span>
      </div>
      <div class="map-item">
        <span class="map-icon">Gem</span>
        <span class="map-chip live">Live in demo</span>
        <span class="map-desc">Compiled knowledge store — fragments with three depth tiers</span>
      </div>
      <div class="map-item">
        <span class="map-icon">Lens</span>
        <span class="map-chip partial">Partially represented</span>
        <span class="map-desc">Read and extraction tool — recall queries use this path</span>
      </div>
      <div class="map-item">
        <span class="map-icon">Loom</span>
        <span class="map-chip parent">Parent system</span>
        <span class="map-desc">Multi-agent analysis pipeline</span>
      </div>
      <div class="map-item">
        <span class="map-icon">Mirror</span>
        <span class="map-chip parent">Parent system</span>
        <span class="map-desc">Compression pipeline — distills conversation into knowledge</span>
      </div>
      <div class="map-item">
        <span class="map-icon">Compass</span>
        <span class="map-chip parent">Parent system</span>
        <span class="map-desc">Autonomous planning system</span>
      </div>
      <div class="map-item">
        <span class="map-icon">Anvil</span>
        <span class="map-chip parent">Parent system</span>
        <span class="map-desc">Collaborative editing sessions</span>
      </div>
    </div>
  </div>

  <p class="key-helper">Private demo access. Keys isolate sessions and token budgets per reviewer.</p>

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