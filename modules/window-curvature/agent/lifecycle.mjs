/** Attempt every owned cleanup, even when one task/menu restore fails. */
export function cleanupEntry(entry) {
    entry.deadline = -Infinity;
    let failure = null;
    try { entry.session.close(); } catch (error) { failure = error; }
    for (const attachment of entry.attachments) {
        try { attachment.ticket.close(); } catch (error) { failure ??= error; }
    }
    if (failure !== null) throw failure;
}
