<?php
declare(strict_types=1);

require_once __DIR__ . '/../lib/auth.php';
require_once __DIR__ . '/../lib/jobs.php';

try {
    art_require_method('GET');
    art_require_login();

    $jobId = trim((string)($_GET['id'] ?? ''));

    // No job ID: return bridge status
    if ($jobId === '') {
        $state = art_get_bridge_state();
        art_json_response(200, [
            'ok'     => true,
            'online' => art_bridge_is_online($state),
            'busy'   => (bool)($state['busy'] ?? false),
        ]);
    }

    $job = art_get_job($jobId);
    if (!is_array($job)) {
        art_json_response(404, ['ok' => false, 'error' => 'job_not_found']);
    }

    // Ownership check — prevent IDOR
    $keyId = art_current_key_id();
    if (($job['key_id'] ?? '') !== $keyId) {
        art_json_response(404, ['ok' => false, 'error' => 'job_not_found']);
    }

    $st = (string)($job['status'] ?? '');

    // Still in progress
    if ($st === 'queued' || $st === 'running') {
        art_json_response(200, ['ok' => true, 'status' => $st]);
    }

    // Error
    if ($st === 'error') {
        art_json_response(200, [
            'ok'     => true,
            'status' => 'error',
            'error'  => $job['error_message'] ?? null,
        ]);
    }

    // Done
    art_json_response(200, [
        'ok'      => true,
        'status'  => 'done',
        'display' => $job['display'] ?? [],
        'actor'   => $job['reply_actor'] ?? 'artifact',
    ]);
} catch (Throwable $e) {
    error_log('status.php: ' . $e->getMessage());
    art_json_response(500, ['ok' => false, 'error' => 'internal_error']);
}
