<?php
declare(strict_types=1);

/* --- Paths --- */

function art_web_root(): string
{
    return dirname(__DIR__);
}

function art_data_dir(): string
{
    $configured = trim((string)art_cfg('data_dir', 'data'));
    if ($configured === '') {
        $configured = 'data';
    }
    $path = $configured;
    if (!art_is_absolute($path)) {
        $path = art_web_root() . '/' . $path;
    }
    return rtrim($path, '/\\');
}

function art_jobs_dir(): string
{
    return art_data_dir() . '/jobs';
}

function art_state_dir(): string
{
    return art_data_dir() . '/state';
}

function art_sessions_dir(): string
{
    return art_data_dir() . '/sessions';
}

function art_session_dir(string $keyId): string
{
    // Sanitize key_id to prevent path traversal
    $safe = preg_replace('/[^a-f0-9]/', '', $keyId);
    if ($safe === '' || $safe !== $keyId) {
        throw new RuntimeException('invalid key id');
    }
    return art_sessions_dir() . '/' . $safe;
}

function art_session_history(string $keyId): string
{
    return art_session_dir($keyId) . '/history.jsonl';
}

function art_session_db(string $keyId): string
{
    return art_session_dir($keyId) . '/memory.sqlite';
}

function art_keys_db_path(): string
{
    $configured = trim((string)art_cfg('keys_db', 'data/keys.sqlite'));
    if (!art_is_absolute($configured)) {
        return art_web_root() . '/' . $configured;
    }
    return $configured;
}

function art_is_absolute(string $path): bool
{
    if ($path === '') return false;
    if (str_starts_with($path, '/')) return true;
    if (preg_match('/^[A-Za-z]:[\\\\\\/]/', $path) === 1) return true;
    return false;
}

/* --- Config --- */

function art_load_config(): array
{
    static $cfg = null;
    if (is_array($cfg)) return $cfg;

    $cfg = require art_web_root() . '/config.php';
    if (!is_array($cfg)) {
        throw new RuntimeException('config.php must return an array');
    }

    $tz = trim((string)($cfg['timezone'] ?? 'UTC'));
    if ($tz !== '') {
        date_default_timezone_set($tz);
    }
    return $cfg;
}

function art_cfg(string $key, mixed $default = null): mixed
{
    $cfg = art_load_config();
    return array_key_exists($key, $cfg) ? $cfg[$key] : $default;
}

/* --- Utilities --- */

function art_now_iso(): string
{
    return gmdate('c');
}

function art_random_id(int $bytes = 12): string
{
    return bin2hex(random_bytes($bytes));
}

function art_ensure_dir(string $dir): void
{
    if (is_dir($dir)) return;
    if (!mkdir($dir, 0700, true) && !is_dir($dir)) {
        throw new RuntimeException('cannot create directory: ' . $dir);
    }
}

function art_init_storage(): void
{
    art_ensure_dir(art_data_dir());
    art_ensure_dir(art_jobs_dir());
    art_ensure_dir(art_state_dir());
    art_ensure_dir(art_sessions_dir());
}

function art_json_response(int $status, array $payload): never
{
    http_response_code($status);
    header('Content-Type: application/json; charset=utf-8');
    header('Cache-Control: no-store');
    echo json_encode($payload, JSON_UNESCAPED_SLASHES | JSON_UNESCAPED_UNICODE);
    exit;
}

function art_require_method(string $method): void
{
    $actual = strtoupper((string)($_SERVER['REQUEST_METHOD'] ?? 'GET'));
    if ($actual !== strtoupper($method)) {
        art_json_response(405, [
            'ok' => false,
            'error' => 'method_not_allowed',
        ]);
    }
}

function art_read_json_body(): array
{
    $raw = file_get_contents('php://input');
    if ($raw === false || trim($raw) === '') return [];
    $decoded = json_decode($raw, true);
    if (!is_array($decoded)) {
        art_json_response(400, ['ok' => false, 'error' => 'invalid_json']);
    }
    return $decoded;
}

function art_write_json_atomic(string $path, array $payload): void
{
    $tmp = $path . '.tmp.' . art_random_id(4);
    $encoded = json_encode($payload, JSON_PRETTY_PRINT | JSON_UNESCAPED_SLASHES | JSON_UNESCAPED_UNICODE);
    if ($encoded === false) {
        throw new RuntimeException('json encode failed');
    }
    if (file_put_contents($tmp, $encoded . "\n", LOCK_EX) === false) {
        throw new RuntimeException('write failed: ' . $tmp);
    }
    if (!rename($tmp, $path)) {
        @unlink($tmp);
        throw new RuntimeException('rename failed: ' . $path);
    }
}

function art_read_json_file(string $path): ?array
{
    if (!is_file($path)) return null;
    $raw = file_get_contents($path);
    if ($raw === false) return null;
    $decoded = json_decode($raw, true);
    return is_array($decoded) ? $decoded : null;
}

function art_with_lock(string $name, callable $fn): mixed
{
    $lockDir = art_state_dir();
    art_ensure_dir($lockDir);
    $fh = fopen($lockDir . '/' . $name . '.lock', 'c+');
    if ($fh === false) {
        throw new RuntimeException('cannot open lock: ' . $name);
    }
    try {
        if (!flock($fh, LOCK_EX)) {
            throw new RuntimeException('cannot acquire lock: ' . $name);
        }
        return $fn();
    } finally {
        flock($fh, LOCK_UN);
        fclose($fh);
    }
}
