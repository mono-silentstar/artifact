<?php
declare(strict_types=1);

/*
 * Default configuration. Override in config.local.php (same format, gitignored).
 * Environment variables take priority for secrets:
 *   ARTIFACT_API_KEY_SALT
 */

$defaults = [
    'session_cookie_name'   => 'artifact_session',
    'bridge_online_ttl_sec' => 90,
    'job_stale_sec'         => 600,
    'data_dir'              => 'data',
    'keys_db'               => 'data/keys.sqlite',
    'timezone'              => 'UTC',
];

// Load local overrides
$localPath = __DIR__ . '/config.local.php';
if (is_file($localPath)) {
    $local = require $localPath;
    if (is_array($local)) {
        $defaults = array_merge($defaults, $local);
    }
}

return $defaults;
