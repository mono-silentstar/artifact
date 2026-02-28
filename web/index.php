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
  <link rel="stylesheet" href="static/style.css?v=4">
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
      knowledge fragments, and graph recall &mdash; all within a fixed token budget.
      The AI wakes up inside it with no memory of its own.
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

  <p class="budget-line">
    No fine-tuning. No vector database. Personality, knowledge, scored memory,
    compressed history, and conversation &mdash; assembled into ~10K tokens, fresh every turn.
  </p>

  <div class="features">
    <div class="feature feature-mirror">
      <div class="feature-header">
        <div>
          <h3 class="feature-title">mirror</h3>
          <p class="feature-teaser">Three-model pipeline. Rolling compression.</p>
        </div>
        <span class="feature-toggle">+</span>
      </div>
      <div class="pipeline">
        <span class="pipeline-node">H</span>
        <span class="pipeline-line"></span>
        <span class="pipeline-node">S</span>
        <span class="pipeline-line"></span>
        <span class="pipeline-node">O</span>
      </div>
      <div class="feature-detail">
        <p class="feature-body">
          Haiku strips formatting and noise. When conversations include dense
          action sequences, Sonnet adds an extra compression pass.
          Then Opus writes a summary and suggests working memory tags &mdash;
          pins, patterns, and descriptions that should persist.
        </p>
        <p class="feature-body">
          Each new summary folds in the previous one. Generation 0 covers the
          first batch; generation 5 covers the entire conversation. The most
          recent summary always carries everything &mdash; a few hundred tokens
          for the whole history. Pipeline fires automatically every ~1500
          conversation tokens.
        </p>
      </div>
    </div>

    <div class="feature feature-decay">
      <div class="feature-header">
        <div>
          <h3 class="feature-title">decay</h3>
          <p class="feature-teaser">Nine types, two axes, pressure-driven.</p>
        </div>
        <span class="feature-toggle">+</span>
      </div>
      <div class="decay-gradient">
        <div class="decay-item">
          <span class="decay-label">feeling</span>
          <span class="decay-fill" style="--fill: 12%"></span>
          <span class="decay-time">~2h</span>
        </div>
        <div class="decay-item">
          <span class="decay-label">thought</span>
          <span class="decay-fill" style="--fill: 30%"></span>
          <span class="decay-time">~12h</span>
        </div>
        <div class="decay-item">
          <span class="decay-label">pattern</span>
          <span class="decay-fill" style="--fill: 65%"></span>
          <span class="decay-time">~1w</span>
        </div>
        <div class="decay-item">
          <span class="decay-label">pin</span>
          <span class="decay-fill" style="--fill: 92%"></span>
          <span class="decay-time">~2w</span>
        </div>
      </div>
      <div class="feature-detail">
        <p class="feature-body">
          Each memory type decays on two axes &mdash; hours elapsed and turns
          elapsed &mdash; combined multiplicatively. Feelings fade in ~2 hours
          or 3 turns. Thoughts last 12 hours or 8 turns. Pins hold for 2 weeks
          or 100 turns. Secrets never fade.
        </p>
        <p class="feature-body">
          Timed plans use a submersion curve: spike when created, drop to
          near-zero, then resurface as the due date approaches. When working
          memory is near capacity, conversation history decays faster &mdash;
          a pressure mechanic that prioritizes what you're actively holding.
        </p>
      </div>
    </div>

    <div class="feature feature-compass">
      <div class="feature-header">
        <div>
          <h3 class="feature-title">compass</h3>
          <p class="feature-teaser">Time + topic scoring, every turn.</p>
        </div>
        <span class="feature-toggle">+</span>
      </div>
      <div class="feature-detail">
        <p class="feature-body">
          Every turn, all active working memory items are scored on two axes:
          time urgency (proximity to due date) and topic relevance (keyword
          overlap with the current conversation). Either axis alone is
          sufficient &mdash; max wins.
        </p>
        <p class="feature-body">
          Items scoring above 0.15 that aren't already in working memory fill
          the remaining token budget, highest scores first. Recall results from
          the knowledge graph get priority. Blocked items surface in shallow
          form &mdash; just the subject and what's blocking them.
        </p>
      </div>
    </div>
  </div>

  <p class="key-helper">Private demo. Keys isolate sessions and token budgets per reviewer.</p>

  <script>
  document.querySelectorAll('.feature').forEach(function(card) {
    card.addEventListener('click', function() { card.classList.toggle('open'); });
  });
  </script>

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