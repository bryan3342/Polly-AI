import { useId } from 'react';

/**
 * The Polly parrot mark.
 *
 * Inline SVG rather than an <img>: it inherits sizing from CSS, stays crisp at
 * every density, and costs no extra request. Gradient ids are namespaced per
 * instance so several marks can render on one page without colliding.
 */
export default function PollyMark({ size = 24, className = '', title = 'Polly AI' }) {
    const id = useId().replace(/:/g, '');
    const head = `${id}-head`;
    const crest = `${id}-crest`;
    const beak = `${id}-beak`;

    return (
        <svg
            className={className}
            width={size}
            height={size}
            viewBox="0 0 64 64"
            role="img"
            aria-label={title}
            xmlns="http://www.w3.org/2000/svg"
        >
            <defs>
                <linearGradient id={head} x1="16" y1="16" x2="46" y2="52" gradientUnits="userSpaceOnUse">
                    <stop offset="0" stopColor="#9db4f0" />
                    <stop offset="1" stopColor="#4f62b6" />
                </linearGradient>
                <linearGradient id={crest} x1="6" y1="4" x2="34" y2="26" gradientUnits="userSpaceOnUse">
                    <stop offset="0" stopColor="#a8bcf5" />
                    <stop offset="1" stopColor="#6a86d8" />
                </linearGradient>
                <linearGradient id={beak} x1="38" y1="22" x2="56" y2="50" gradientUnits="userSpaceOnUse">
                    <stop offset="0" stopColor="#f9c065" />
                    <stop offset="1" stopColor="#dd8619" />
                </linearGradient>
            </defs>

            {/* crest: three tapered plumes swept up and back */}
            <path d="M24 27 C14 24 8 17 6 9 C13 12 21 16 28 21 Z" fill={`url(#${crest})`} />
            <path d="M28 22 C20.5 17 15.5 11 14.5 4 C20 8.5 27 13 33 18 Z" fill={`url(#${crest})`} />
            <path d="M33 19 C30.5 14.5 29 10 29.5 5.5 C33 10 36 13.5 38 17 Z" fill={`url(#${crest})`} opacity=".85" />

            {/* head */}
            <path d="M31 17 C41 17 47 24 47 33 C47 44 40 51 30 51 C20 51 14 44 14 34 C14 24 21 17 31 17 Z" fill={`url(#${head})`} />

            {/* hooked beak — the parrot cue */}
            <path d="M39 24 C48 22 56 28 57 36 C57.5 43 52 48.5 45 48 C49.5 43.5 51 36.5 47.5 31 C45.5 27.5 42.5 25 39 24 Z" fill={`url(#${beak})`} />
            <path d="M41 42 C45 45.5 50 46.5 53.5 45 C51.5 49 47 51 43 49.5 C42.5 47 42 44.5 41 42 Z" fill="#c9761a" />

            {/* eye */}
            <ellipse cx="33" cy="30" rx="7.2" ry="6.8" fill="#e2e9fc" opacity=".95" />
            <circle cx="33.4" cy="30" r="4" fill="#111a33" />
            <circle cx="34.9" cy="28.5" r="1.45" fill="#fff" />
        </svg>
    );
}
