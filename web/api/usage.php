<?php
declare(strict_types=1);

require_once __DIR__ . '/../lib/auth.php';

try {
    art_require_method('GET');
    art_require_login();

    $keyId = art_current_key_id();
    $usage = art_get_usage($keyId);

    art_json_response(200, [
        'ok'    => true,
        'usage' => $usage,
    ]);
} catch (Throwable $e) {
    error_log('usage.php: ' . $e->getMessage());
    art_json_response(500, ['ok' => false, 'error' => 'internal_error']);
}
