import {strict as assert} from 'node:assert';
import {test} from 'node:test';
import {taskFromName, eligibleFrame, overrideVisibility} from '../modules/window-curvature/agent/policy.mjs';
import {cleanupEntry} from '../modules/window-curvature/agent/lifecycle.mjs';

test('ordinary exact window and caption names only', () => {
    assert.equal(taskFromName('window-task-5131'), 5131);
    assert.equal(taskFromName('Caption node of Task=5131'), 5131);
    for (const value of [null, 'window-task-0', 'window-task-01', 'window-task-5131-extra',
        'space-root-task-5131', 'window-task-999999999999999999999']) assert.equal(taskFromName(value), null);
});
test('per-task deadlines, finite curvature and extended range', () => {
    const first = {started: 100, deadline: 200};
    const second = {started: 100, deadline: 120};
    for (const value of [1, 1.1, 1.135, 3.58, 4, 4.02]) assert(eligibleFrame(first, value, 150));
    for (const value of [-1, 0, 4.1, 5, NaN, Infinity]) assert(!eligibleFrame(first, value, 150));
    assert(!eligibleFrame(second, 1, 150));
    for (const now of [99, 200, Infinity, NaN]) assert(!eligibleFrame(first, 1, now));
    assert(!eligibleFrame(undefined, 1, 150));
});
test('paired exact callsites only', () => {
    assert(overrideVisibility('direct', false, '0x4d712d0', true, 0));
    assert(!overrideVisibility('combined', true, '0x4d712e4', true, 1));
    assert(overrideVisibility('combined', true, '0x4d712e4', true, 0));
    assert(!overrideVisibility('direct', false, '0x4d712d1', true, 0));
    assert(!overrideVisibility('direct', false, '0x4d712d0', false, 0));
});

test('failed restore does not skip menu cleanup or another task', () => {
    const calls = [];
    const broken = {deadline: 100, session: {close() { calls.push('broken'); throw Error('live restore failed'); }},
        attachments: [{ticket: {close() { calls.push('menu'); }}}]};
    const good = {deadline: 100, session: {close() { calls.push('good'); }}, attachments: []};
    const pending = [];
    for (const entry of [broken, good]) {
        try { cleanupEntry(entry); } catch (error) { pending.push(error.message); }
    }
    assert.deepEqual(calls, ['broken', 'menu', 'good']);
    assert.deepEqual(pending, ['live restore failed']);
    assert.equal(broken.deadline, -Infinity);
    assert.equal(good.deadline, -Infinity);
});
