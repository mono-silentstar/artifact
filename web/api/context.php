<?php
declare(strict_types=1);

require_once __DIR__ . '/../lib/auth.php';

/**
 * Behind-the-curtain API: returns a snapshot of what was assembled
 * for the most recent turn. Shows fragments, working memory, recall
 * results, and token counts.
 */

try {
    art_require_method('GET');
    art_require_login();

    $keyId = art_current_key_id();
    $sessionDb = art_session_db($keyId);

    // If no session DB exists yet, return empty
    if (!is_file($sessionDb)) {
        art_json_response(200, [
            'ok' => true,
            'context' => [
                'turn' => 0,
                'working_memory' => [],
                'events_count' => 0,
                'summaries_count' => 0,
                'pending_recall' => [],
                'usage' => art_get_usage($keyId),
            ],
        ]);
    }

    $pdo = new PDO('sqlite:' . $sessionDb);
    $pdo->setAttribute(PDO::ATTR_ERRMODE, PDO::ERRMODE_EXCEPTION);

    // Current turn
    $turnRow = $pdo->query(
        "SELECT value FROM state WHERE key = 'current_turn'"
    )->fetch(PDO::FETCH_ASSOC);
    $turn = $turnRow ? (int)$turnRow['value'] : 0;

    // Active working memory items
    $wmRows = $pdo->query(
        "SELECT type, content, actor, created_at, refreshed_at FROM working_memory WHERE status = 'active' ORDER BY refreshed_at DESC"
    )->fetchAll(PDO::FETCH_ASSOC);

    // Events count
    $eventsCount = (int)$pdo->query("SELECT COUNT(*) FROM events")->fetchColumn();

    // Pending recall results
    $recallRow = $pdo->query(
        "SELECT value FROM state WHERE key = 'pending_recall'"
    )->fetch(PDO::FETCH_ASSOC);
    $pendingRecall = $recallRow ? json_decode($recallRow['value'], true) : [];

    // Mirror summaries count (from per-session summaries.sqlite)
    $summariesCount = 0;
    $sessionDir = dirname($sessionDb);
    $summariesDb = $sessionDir . '/summaries.sqlite';
    if (is_file($summariesDb)) {
        try {
            $sumPdo = new PDO('sqlite:' . $summariesDb);
            $sumPdo->setAttribute(PDO::ATTR_ERRMODE, PDO::ERRMODE_EXCEPTION);
            $summariesCount = (int)$sumPdo->query(
                "SELECT COUNT(*) FROM summaries WHERE level = 'L0'"
            )->fetchColumn();
        } catch (Throwable $e) {
            // summaries.sqlite may not have schema yet — ignore
        }
    }

    art_json_response(200, [
        'ok' => true,
        'context' => [
            'turn' => $turn,
            'working_memory' => $wmRows ?: [],
            'events_count' => $eventsCount,
            'summaries_count' => $summariesCount,
            'pending_recall' => is_array($pendingRecall) ? $pendingRecall : [],
            'usage' => art_get_usage($keyId),
        ],
    ]);
} catch (Throwable $e) {
    error_log('context.php: ' . $e->getMessage());
    art_json_response(500, ['ok' => false, 'error' => 'internal_error']);
}
