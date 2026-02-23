<?php
declare(strict_types=1);

require_once __DIR__ . '/bootstrap.php';

/* --- Tag validation --- */

define('ART_KNOWLEDGE_TAGS', ['plan', 'pin']);

function art_normalize_tags(mixed $input): array
{
    if (!is_array($input)) return [];
    $out = [];
    foreach ($input as $raw) {
        $t = strtolower(trim((string)$raw));
        if ($t !== '' && in_array($t, ART_KNOWLEDGE_TAGS, true) && !in_array($t, $out, true)) {
            $out[] = $t;
        }
    }
    return $out;
}

/* --- Bridge state --- */

function art_bridge_state_file(): string
{
    return art_state_dir() . '/bridge.json';
}

function art_get_bridge_state(): array
{
    art_init_storage();
    $state = art_read_json_file(art_bridge_state_file());
    if (!is_array($state)) {
        return ['last_seen_at' => null, 'busy' => false, 'worker' => null];
    }
    return [
        'last_seen_at' => $state['last_seen_at'] ?? null,
        'busy'         => (bool)($state['busy'] ?? false),
        'worker'       => $state['worker'] ?? null,
    ];
}

function art_bridge_is_online(?array $state = null): bool
{
    $state = $state ?? art_get_bridge_state();
    $lastSeen = (string)($state['last_seen_at'] ?? '');
    if ($lastSeen === '') return false;
    $ts = strtotime($lastSeen);
    if ($ts === false) return false;
    $ttl = max(1, (int)art_cfg('bridge_online_ttl_sec', 90));
    return (time() - $ts) <= $ttl;
}

/* --- Job CRUD --- */

function art_job_file(string $jobId): string
{
    return art_jobs_dir() . '/' . $jobId . '.json';
}

function art_get_job(string $jobId): ?array
{
    if (preg_match('/^[a-f0-9]{16,64}$/', $jobId) !== 1) return null;
    return art_read_json_file(art_job_file($jobId));
}

function art_list_jobs(): array
{
    art_init_storage();
    $paths = glob(art_jobs_dir() . '/*.json');
    if (!is_array($paths)) return [];
    sort($paths, SORT_STRING);

    $jobs = [];
    foreach ($paths as $path) {
        $job = art_read_json_file($path);
        if (is_array($job) && isset($job['id'])) {
            $jobs[] = $job;
        }
    }
    usort($jobs, static fn(array $a, array $b) =>
        strcmp((string)($a['created_at'] ?? ''), (string)($b['created_at'] ?? ''))
    );
    return $jobs;
}

function art_update_job(string $jobId, callable $mutator): ?array
{
    $path = art_job_file($jobId);
    $job = art_read_json_file($path);
    if (!is_array($job)) return null;
    $updated = $mutator($job);
    if (!is_array($updated)) return null;
    $updated['id'] = $jobId;
    $updated['updated_at'] = art_now_iso();
    art_write_json_atomic($path, $updated);
    return $updated;
}

function art_find_active_job(): ?array
{
    foreach (art_list_jobs() as $job) {
        $st = (string)($job['status'] ?? '');
        if ($st === 'queued' || $st === 'running') return $job;
    }
    return null;
}

function art_cleanup_stale_jobs(): int
{
    $ttl = max(30, (int)art_cfg('job_stale_sec', 600));
    $count = 0;
    foreach (art_list_jobs() as $job) {
        $st = (string)($job['status'] ?? '');
        if ($st !== 'queued' && $st !== 'running') continue;
        $anchor = (string)($job['claimed_at'] ?? $job['created_at'] ?? '');
        if ($anchor === '') continue;
        $ts = strtotime($anchor);
        if ($ts === false || (time() - $ts) < $ttl) continue;

        $jobId = (string)($job['id'] ?? '');
        if ($jobId === '') continue;
        $updated = art_update_job($jobId, static function (array $row): array {
            $row['status'] = 'error';
            $row['error_message'] = 'stale job expired';
            $row['completed_at'] = art_now_iso();
            return $row;
        });
        if (is_array($updated)) $count++;
    }
    return $count;
}
