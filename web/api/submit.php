<?php
declare(strict_types=1);

require_once __DIR__ . '/../lib/auth.php';
require_once __DIR__ . '/../lib/jobs.php';

try {
    art_require_method('POST');
    art_require_login();
    art_init_storage();

    $keyId = art_current_key_id();

    // Check budget
    if (art_budget_exhausted($keyId)) {
        art_json_response(402, [
            'ok'    => false,
            'error' => 'budget_exhausted',
            'message' => 'Your token budget has been used up. Thanks for exploring Artifact!',
        ]);
    }

    $body = art_read_json_body();
    $message = trim((string)($body['message'] ?? ''));
    $tone = trim((string)($body['tone'] ?? 'casual'));

    if ($message === '') {
        art_json_response(400, ['ok' => false, 'error' => 'empty_message']);
    }

    if (strlen($message) > 4000) {
        art_json_response(400, ['ok' => false, 'error' => 'message_too_long']);
    }

    // Validate tone
    $validTones = ['casual', 'technical', 'creative'];
    if (!in_array($tone, $validTones, true)) {
        $tone = 'casual';
    }

    $jobId = art_random_id(12);

    $job = art_with_lock('jobs', static function () use (
        $message, $tone, $jobId, $keyId
    ): array {
        art_cleanup_stale_jobs();

        $active = art_find_active_job();
        if (is_array($active)) {
            throw new RuntimeException('bridge_busy');
        }

        $now = art_now_iso();
        $job = [
            'id'            => $jobId,
            'status'        => 'queued',
            'message'       => $message,
            'tone'          => $tone,
            'key_id'        => $keyId,
            'actor'         => 'visitor',
            'tags'          => [],
            'created_at'    => $now,
            'updated_at'    => $now,
            'claimed_at'    => null,
            'completed_at'  => null,
            'reply_text'    => null,
            'display'       => null,
            'reply_actor'   => null,
            'error_message' => null,
            'turn_id'       => null,
        ];
        art_write_json_atomic(art_job_file($jobId), $job);
        return $job;
    });

    // Signal the cron worker to wake up immediately
    @touch(art_state_dir() . '/trigger');

    art_json_response(200, [
        'ok'     => true,
        'job_id' => $job['id'],
    ]);
} catch (Throwable $e) {
    if ($e->getMessage() === 'bridge_busy') {
        art_json_response(409, ['ok' => false, 'error' => 'bridge_busy']);
    }
    error_log('submit.php: ' . $e->getMessage());
    art_json_response(500, ['ok' => false, 'error' => 'internal_error']);
}
