export function taskFromName(name) {
    const match = /^(?:window-task-|Caption node of Task=)([1-9][0-9]*)$/.exec(name || '');
    if (match === null) return null;
    const id = Number(match[1]);
    return Number.isSafeInteger(id) && id <= 2147483647 ? id : null;
}

export function eligibleFrame(entry, curvature, now) {
    return entry !== undefined && entry !== null && Number.isFinite(now) &&
        now >= entry.started && now < entry.deadline && Number.isFinite(curvature) &&
        curvature > 0 && curvature < 4.1;
}

export function overrideVisibility(kind, original, caller, active, directShown) {
    if (!active) return original;
    if (kind === 'direct' && caller === '0x4d712d0' && original === false) return true;
    if (kind === 'combined' && caller === '0x4d712e4' && original === true && directShown > 0) return false;
    return original;
}
