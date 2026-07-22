/* Formats seconds as m:ss; returns null for missing/invalid input. */
function fmtDuration(s) {
    if (typeof s !== 'number' || !isFinite(s)) return null;
    const m = Math.floor(s / 60);
    const sec = Math.round(s % 60);
    return `${m}:${String(sec).padStart(2, '0')}`;
}

/* Renders a number with fixed digits, or an em dash when the backend omitted it. */
function num(v, digits = 0) {
    return typeof v === 'number' && isFinite(v) ? v.toFixed(digits) : '—';
}

/**
 * Post-session report card rendered inline in the chat flow.
 * Consumes the `analysis_complete` results object from the backend
 * (transcript, speech/voice analysis, emotion summary, AI feedback).
 * Every field is optional — mock STT or a failed analysis may omit any of them.
 */
export default function ReportCard({ results }) {
    if (!results) return null;

    const speech = results.speech_analysis ?? {};
    const voice = results.voice_analysis ?? {};
    const emotion = results.emotion_summary?.emotion_summary ?? {};
    const transcript = (results.transcript ?? '').trim();
    const duration = fmtDuration(results.duration);

    const stats = [
        { label: 'Pace', value: num(speech.words_per_minute), unit: 'wpm' },
        { label: 'Words', value: num(speech.word_count) },
        {
            label: 'Fillers',
            value: num(speech.filler_word_count),
            unit: typeof speech.filler_percentage === 'number' ? `${num(speech.filler_percentage, 1)}%` : null,
        },
        { label: 'Confidence', value: num(voice.confidence_score), unit: '/100' },
        { label: 'Emotion', value: emotion.dominant ?? '—', cap: true },
    ];

    return (
        <div className="report-card">
            <div className="report-head">
                <span className="report-title">Performance Report</span>
                {duration && <span className="report-duration">{duration}</span>}
            </div>

            <div className="report-stats">
                {stats.map(s => (
                    <div key={s.label} className="report-stat">
                        <div className="label">{s.label}</div>
                        <div className={`value${s.cap ? ' cap' : ''}`}>
                            {s.value}
                            {s.unit && s.value !== '—' && <span className="unit"> {s.unit}</span>}
                        </div>
                    </div>
                ))}
            </div>

            {results.tone_description && <div className="report-tone">{results.tone_description}</div>}

            {results.feedback && <div className="report-feedback">{results.feedback}</div>}

            <details className="report-transcript">
                <summary>Transcript</summary>
                <p>{transcript || 'No transcript available for this session.'}</p>
            </details>
        </div>
    );
}
