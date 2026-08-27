// Behaviour for landing.html.
//
// A separate file rather than an inline <script> so the page needs no
// 'unsafe-inline' in script-src. A policy that allows inline scripts allows
// injected ones too, which is most of what CSP is for.
// Swap the placeholder for the real thing only once the file is known to
// exist, so the page never shows a broken player while the demo is pending.
//
// The content type is checked, not just the status: a dev server with an
// SPA fallback answers a missing file with 200 and an HTML body, which
// would otherwise pass for a video and leave an empty player on the page.
fetch('/demo.mp4', { method: 'HEAD' })
    .then((response) => {
        const type = response.headers.get('content-type') || '';
        if (!response.ok || !type.startsWith('video/')) return;
        document.getElementById('frame').innerHTML =
            '<video controls playsinline preload="metadata" src="/demo.mp4"></video>';
    })
    .catch(() => { /* no demo yet; the placeholder already says so */ });
