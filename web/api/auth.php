<?php
declare(strict_types=1);

require_once __DIR__ . '/../lib/auth.php';

try {
    art_require_method('POST');

    $body = art_read_json_body();
    $key = trim((string)($body['key'] ?? ''));

    if ($key === '') {
        art_json_response(400, ['ok' => false, 'error' => 'missing_key']);
    }

    if (!art_attempt_login($key)) {
        art_json_response(401, ['ok' => false, 'error' => 'invalid_key']);
    }

    $keyId = art_current_key_id();
    $usage = art_get_usage($keyId);

    art_json_response(200, [
        'ok'    => true,
        'usage' => $usage,
    ]);
} catch (Throwable $e) {
    error_log('auth.php: ' . $e->getMessage());
    art_json_response(500, ['ok' => false, 'error' => 'internal_error']);
}
