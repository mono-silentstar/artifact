<?php
declare(strict_types=1);

require_once __DIR__ . '/bootstrap.php';

/**
 * API key authentication for Artifact.
 *
 * Keys are stored as SHA-256 hashes in keys.sqlite.
 * On successful auth, session stores key_id for per-key isolation.
 */

function art_keys_db(): PDO
{
    static $pdo = null;
    if ($pdo !== null) return $pdo;

    $path = art_keys_db_path();
    art_ensure_dir(dirname($path));

    $pdo = new PDO('sqlite:' . $path);
    $pdo->setAttribute(PDO::ATTR_ERRMODE, PDO::ERRMODE_EXCEPTION);
    $pdo->exec('PRAGMA journal_mode=WAL');
    $pdo->exec('PRAGMA busy_timeout = 5000');

    // Auto-migrate
    $pdo->exec(<<<SQL
        CREATE TABLE IF NOT EXISTS api_keys (
            id TEXT PRIMARY KEY,
            key_hash TEXT NOT NULL,
            label TEXT NOT NULL DEFAULT '',
            token_budget INTEGER NOT NULL DEFAULT 100000,
            tokens_used INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL,
            last_used_at TEXT,
            active INTEGER NOT NULL DEFAULT 1
        )
    SQL);

    return $pdo;
}

function art_session_start(): void
{
    if (session_status() === PHP_SESSION_ACTIVE) return;

    $name = (string)art_cfg('session_cookie_name', 'artifact_session');
    if ($name !== '') session_name($name);

    $secure = !empty($_SERVER['HTTPS']) && $_SERVER['HTTPS'] !== 'off';
    session_set_cookie_params([
        'lifetime' => 0,
        'path'     => '/',
        'secure'   => $secure,
        'httponly'  => true,
        'samesite'  => 'Lax',
    ]);
    session_start();
}

function art_validate_key(string $key): ?array
{
    $hash = hash('sha256', $key);
    $pdo = art_keys_db();

    $stmt = $pdo->prepare(
        'SELECT id, label, token_budget, tokens_used, active FROM api_keys WHERE key_hash = ?'
    );
    $stmt->execute([$hash]);
    $row = $stmt->fetch(PDO::FETCH_ASSOC);

    if (!$row) return null;
    if (!$row['active']) return null;

    // Update last_used_at
    $pdo->prepare('UPDATE api_keys SET last_used_at = ? WHERE id = ?')
        ->execute([art_now_iso(), $row['id']]);

    return $row;
}

function art_attempt_login(string $key): bool
{
    art_session_start();
    $row = art_validate_key($key);
    if ($row === null) return false;

    session_regenerate_id(true);
    $_SESSION['art_key_id'] = $row['id'];
    $_SESSION['art_label'] = $row['label'];
    $_SESSION['art_auth_at'] = time();

    // Ensure per-key session directory exists
    $dir = art_session_dir($row['id']);
    art_ensure_dir($dir);

    return true;
}

function art_is_logged_in(): bool
{
    art_session_start();
    return !empty($_SESSION['art_key_id']);
}

function art_require_login(): void
{
    if (!art_is_logged_in()) {
        art_json_response(401, ['ok' => false, 'error' => 'unauthorized']);
    }
}

function art_current_key_id(): string
{
    art_session_start();
    return (string)($_SESSION['art_key_id'] ?? '');
}

function art_get_usage(string $keyId): array
{
    $pdo = art_keys_db();
    $stmt = $pdo->prepare(
        'SELECT token_budget, tokens_used FROM api_keys WHERE id = ?'
    );
    $stmt->execute([$keyId]);
    $row = $stmt->fetch(PDO::FETCH_ASSOC);

    if (!$row) return ['budget' => 0, 'used' => 0, 'remaining' => 0];

    $budget = (int)$row['token_budget'];
    $used = (int)$row['tokens_used'];
    return [
        'budget'    => $budget,
        'used'      => $used,
        'remaining' => max(0, $budget - $used),
    ];
}

function art_track_usage(string $keyId, int $inputTokens, int $outputTokens): void
{
    $total = $inputTokens + $outputTokens;
    if ($total <= 0) return;

    $pdo = art_keys_db();
    $pdo->prepare(
        'UPDATE api_keys SET tokens_used = tokens_used + ?, last_used_at = ? WHERE id = ?'
    )->execute([$total, art_now_iso(), $keyId]);
}

function art_budget_exhausted(string $keyId): bool
{
    $usage = art_get_usage($keyId);
    return $usage['remaining'] <= 0;
}

function art_logout(): void
{
    art_session_start();
    $_SESSION = [];
    if (ini_get('session.use_cookies')) {
        $p = session_get_cookie_params();
        setcookie(
            session_name(),
            '',
            time() - 42000,
            $p['path'],
            $p['domain'] ?? '',
            (bool)$p['secure'],
            (bool)$p['httponly']
        );
    }
    session_destroy();
}
