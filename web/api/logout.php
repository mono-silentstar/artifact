<?php
declare(strict_types=1);

require_once __DIR__ . '/../lib/auth.php';

art_require_method('POST');
art_logout();
art_json_response(200, ['ok' => true]);
