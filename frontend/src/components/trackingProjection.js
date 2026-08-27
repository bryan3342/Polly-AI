/**
 * Mapping between the frame the server measured and the pixels on screen.
 *
 * Three things have to line up for an indicator to sit on the body part it
 * claims to be tracking, and getting any of them wrong is silently wrong, * the box still draws, just not where the face is:
 *
 * 1. The video is rendered with `object-fit: cover`, so it is scaled to fill
 *    and then cropped. The visible region is not the whole frame.
 * 2. The capture resolution is whatever the webcam gave us, not the display
 *    size, and the two rarely match.
 * 3. The video is mirrored for display (`transform: scaleX(-1)`) so the speaker
 *    sees themselves as in a mirror, but the frame *sent* to the server is
 *    drawn from the raw video, unmirrored. Coordinates come back in that
 *    unmirrored space. The overlay canvas carries the same CSS mirror, so the
 *    maths here stays in frame space and the browser flips both together.
 *
 * Kept as plain functions so this is testable without a canvas or a camera.
 */

/** Scale and offset that map frame coordinates onto a `cover`-fitted box. */
export function coverTransform(frameWidth, frameHeight, displayWidth, displayHeight) {
    if (!frameWidth || !frameHeight || !displayWidth || !displayHeight) return null;
    // `cover` picks the larger scale, so the frame overflows the box on one
    // axis; the overflow is split evenly, which is where the offsets come from.
    const scale = Math.max(displayWidth / frameWidth, displayHeight / frameHeight);
    return {
        scale,
        offsetX: (displayWidth - frameWidth * scale) / 2,
        offsetY: (displayHeight - frameHeight * scale) / 2,
    };
}

/** A pixel-space box `[x, y, w, h]` from the server, in display coordinates. */
export function projectBox(box, transform) {
    if (!box || !transform) return null;
    const [x, y, w, h] = box;
    const { scale, offsetX, offsetY } = transform;
    return {
        x: offsetX + x * scale,
        y: offsetY + y * scale,
        width: w * scale,
        height: h * scale,
    };
}

/** A normalised 0-1 landmark in display coordinates. */
export function projectPoint(point, transform, frameWidth, frameHeight) {
    if (!point || !transform) return null;
    const { scale, offsetX, offsetY } = transform;
    return {
        x: offsetX + point[0] * frameWidth * scale,
        y: offsetY + point[1] * frameHeight * scale,
    };
}
