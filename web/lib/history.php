<?php
declare(strict_types=1);

require_once __DIR__ . '/bootstrap.php';

/**
 * Per-key conversation history — JSONL files in per-key session directories.
 * JSON API only (no HTML rendering — the frontend handles display).
 */

function art_append_history(string $keyId, array $entry): void
{
    $path = art_session_history($keyId);
    art_ensure_dir(dirname($path));
    $line = json_encode($entry, JSON_UNESCAPED_SLASHES | JSON_UNESCAPED_UNICODE);
    file_put_contents($path, $line . "\n", FILE_APPEND | LOCK_EX);
}

function art_read_history(string $keyId, int $limit = 50, int $offset = 0): array
{
    $path = art_session_history($keyId);
    if (!is_file($path)) return ['entries' => [], 'total' => 0];

    $lines = file($path, FILE_IGNORE_NEW_LINES | FILE_SKIP_EMPTY_LINES);
    if (!is_array($lines) || count($lines) === 0) return ['entries' => [], 'total' => 0];

    $total = count($lines);
    $start = max(0, $total - $limit - $offset);
    $end = $total - $offset;
    if ($end <= 0) return ['entries' => [], 'total' => $total];

    $slice = array_slice($lines, $start, $end - $start);
    $entries = [];
    foreach ($slice as $line) {
        $decoded = json_decode($line, true);
        if (is_array($decoded)) $entries[] = $decoded;
    }
    return ['entries' => $entries, 'total' => $total];
}
