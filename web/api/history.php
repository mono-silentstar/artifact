<?php
declare(strict_types=1);

require_once __DIR__ . '/../lib/auth.php';
require_once __DIR__ . '/../lib/history.php';

try {
    art_require_method('GET');
    art_require_login();

    $keyId = art_current_key_id();
    $limit = max(1, min(200, (int)($_GET['limit'] ?? 50)));
    $offset = max(0, (int)($_GET['offset'] ?? 0));

    $result = art_read_history($keyId, $limit, $offset);

    art_json_response(200, [
        'ok'      => true,
        'entries' => $result['entries'],
        'total'   => $result['total'],
    ]);
} catch (Throwable $e) {
    error_log('history.php: ' . $e->getMessage());
    art_json_response(500, ['ok' => false, 'error' => 'internal_error']);
}
