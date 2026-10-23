import Java from 'frida-java-bridge';
import {taskFromName, eligibleFrame, overrideVisibility} from './policy.mjs';
import {cleanupEntry} from './lifecycle.mjs';
import {DEX_BASE64} from './helper-dex.js';

// Loaded by the pinned standalone frida-inject, never a network server.
const tasks = new Map();
const observed = new Map();
const frames = new Map();
const pending = new Set();
const hooks = [];
const clockBuffer = Memory.alloc(16);
const clockGettime = new NativeFunction(Process.getModuleByName('libc.so').getExportByName('clock_gettime'),
    'int', ['int', 'pointer']);
let lastSupervisor = -Infinity;
let stopped = false;
let initialized = false;
let timer = null;
let observer = null;
let repository = null;
let Session = null;
let Ticket = null;
let System = null;
let Task = null;
let Menu = null;
let tickBusy = false;
let sequence = 0;
let stopReason = '';

function nowMs() {
    if (clockGettime(1, clockBuffer) !== 0) throw new Error('Monotonic clock unavailable');
    return clockBuffer.readS64().toNumber() * 1000 + clockBuffer.add(8).readS64().toNumber() / 1e6;
}

function log(kind, data = {}) { console.log('GXR_CURVATURE_' + kind + ' ' + JSON.stringify(data)); }

function nodeName(node) {
    const text = node.add(0xf0);
    const tag = text.readU8();
    const length = tag & 1 ? text.add(8).readU64().toNumber() : tag >>> 1;
    if (length < 1 || length > 256) return null;
    return (tag & 1 ? text.add(16).readPointer() : text.add(1)).readUtf8String(length);
}

function homeSpace() {
    return observer !== null && observer.getCurrentlyRenderingOpenXrTaskId().getValue() === null;
}

function permitted() { return !stopped && nowMs() - lastSupervisor < 2500 && homeSpace(); }

function taskEligible(task) {
    return String(task.isAttached().getValue()) === 'true' &&
        String(task.is2DRenderingEnabled().getValue()) === 'true';
}

function closeEntry(entry) {
    cleanupEntry(entry);
}

function currentNode(entry) {
    // Android may close its wrapper before the next poll. The session owns a
    // separate SAME-node handle and can still flatten it; never reuse this task.
    try {
        return String(entry.task.getCpmWindowNode().getNativeHandle()) === entry.handle;
    } catch (error) {
        entry.retireReason = String(error);
        return false;
    }
}

function releaseEntry(entry) {
    for (const attachment of entry.attachments) attachment.ticket.$dispose();
    entry.session.$dispose();
    entry.task.$dispose();
}

function stop(reason) {
    if (stopped) return;
    stopped = true;
    stopReason = reason;
    log('STOPPING', {reason});
    // Leave paired native hooks installed until Java has flattened every task.
    // Their deadlines are immediately revoked; ordinary renderer selection resumes.
    for (const entry of tasks.values()) entry.deadline = -Infinity;
}

// Implemented after helper factory creation; never retain a menu beyond its view.
let enqueue = null;

function fail(error) {
    if (!stopped) log('FATAL', {error: String(error.stack || error)});
    stop('agent failure');
}

function installNative() {
    const lib = Process.getModuleByName('libspaceflinger_jni_vulkan.so');
    if (lib.path !== '/system_ext/lib64/libspaceflinger_jni_vulkan.so') throw new Error('Unexpected renderer mapping');
    const update = lib.getExportByName('_ZN12spaceflinger21PanelRenderController6UpdateERKN3imp9FrameTimeE');
    if (!update.equals(lib.base.add(0x4d6faac))) throw new Error('Renderer symbol/offset mismatch');
    hooks.push(Interceptor.attach(update, {
        onEnter(args) {
            try {
                const node = args[0].add(0x18).readPointer();
                const name = nodeName(node);
                const id = taskFromName(name);
                if (id === null) return;
                const now = nowMs();
                const curvature = node.add(0x1004).readFloat();
                if (name === `window-task-${id}` && (observed.has(id) || observed.size < 128)) {
                    observed.set(id, {curvature, now});
                }
                const entry = tasks.get(id);
                frames.set(this.threadId, {active: !stopped && eligibleFrame(entry, curvature, now), direct: 0});
            } catch (_) { frames.delete(this.threadId); }
        },
        onLeave() { frames.delete(this.threadId); },
    }));
    hooks.push(Interceptor.attach(lib.getExportByName('_ZN12spaceflinger22SurfaceRendererAdapter10SetVisibleEb'), {
        onEnter(args) {
            const frame = frames.get(this.threadId);
            if (!frame?.active) return;
            try {
                const surface = args[0].add(0xa8).readPointer();
                if (!(surface.add(0x68).readFloat() > 0)) return;
                const original = !!(args[1].toInt32() & 1);
                const visible = overrideVisibility('direct', original, String(this.returnAddress.sub(lib.base)), true, frame.direct);
                if (visible !== original) { args[1] = ptr(1); frame.direct++; }
            } catch (_) { frame.active = false; }
        },
    }));
    hooks.push(Interceptor.attach(lib.getExportByName('_ZN12spaceflinger20MultiSurfaceRenderer10SetVisibleEb'), {
        onEnter(args) {
            const frame = frames.get(this.threadId);
            if (!frame?.active) return;
            const original = !!(args[1].toInt32() & 1);
            const visible = overrideVisibility('combined', original, String(this.returnAddress.sub(lib.base)), true, frame.direct);
            if (visible !== original) args[1] = ptr(0);
        },
    }));
}

function poll() {
    if (tickBusy) return;
    tickBusy = true;
    Java.perform(() => {
        try {
            const now = nowMs();
            if (!stopped && now - lastSupervisor >= 2500) stop('supervisor pulse expired');
            const home = !stopped && homeSpace();
            for (const [id, entry] of tasks) {
                try {
                if (stopped || !home || !taskEligible(entry.task) ||
                    !currentNode(entry) ||
                    ['restored', 'restore-pending'].includes(String(entry.session.getStatus()))) {
                    closeEntry(entry);
                    releaseEntry(entry);
                    tasks.delete(id);
                    log('TASK_REMOVED', {taskId: id, reason: entry.retireReason || 'ineligible or stopped'});
                    continue;
                }
                if (!entry.session.heartbeat()) throw new Error('Task heartbeat failed');
                entry.deadline = now + 2000;
                const retained = [];
                for (const attachment of entry.attachments) {
                    const error = attachment.ticket.getLastError();
                    if (error !== null) throw new Error('Menu attachment: ' + error);
                    if (attachment.ticket.isClosed()) attachment.ticket.$dispose();
                    else retained.push(attachment);
                }
                entry.attachments = retained;
                } catch (error) {
                    // A bad task cannot starve the remaining tasks' rollback.
                    entry.deadline = -Infinity;
                    fail(error);
                    if (entry.lastCleanupLog === undefined || now - entry.lastCleanupLog >= 10000) {
                        log('CLEANUP_PENDING', {taskId: id, error: String(error)});
                        entry.lastCleanupLog = now;
                    }
                }
            }
            if (stopped && tasks.size === 0) {
                clearInterval(timer);
                for (const hook of hooks) hook.detach();
                hooks.length = 0;
                if (Menu !== null) Menu.show.overload().implementation = null;
                log('STOPPED', {reason: stopReason, allTasksFlat: true});
                return;
            }
            if (++sequence % 10 === 0) {
                log('STATE', {homeSpace: home, tasks: Array.from(tasks, ([id, entry]) => ({
                    taskId: id, strength: entry.session.getValue(), curvature: entry.session.getAppliedCurvature(),
                    maximum: entry.session.getMaximumCurvature(), menus: entry.attachments.length,
                }))});
            }
            for (const [id, seen] of observed) if (now - seen.now > 10000) observed.delete(id);
        } catch (error) { fail(error); }
        finally { tickBusy = false; }
    });
}

rpc.exports = {
    init() {
        if (initialized) throw new Error('Already initialized');
        initialized = true;
        lastSupervisor = nowMs();
        return new Promise((resolve, reject) => Java.perform(() => {
            try {
                const bytes = Java.use('android.util.Base64').decode(DEX_BASE64, 0);
                const loader = Java.use('dalvik.system.InMemoryDexClassLoader').$new(
                    Java.use('java.nio.ByteBuffer').wrap(bytes), Java.use('java.lang.ClassLoader').getSystemClassLoader());
                const factory = Java.ClassFactory.get(loader);
                Session = factory.use('local.gxr.curvature.CurvatureSession');
                Ticket = factory.use('local.gxr.curvature.MenuAttachmentTicket');
                const Attachment = factory.use('local.gxr.curvature.MenuAttachment');
                System = Java.use('java.lang.System');
                Task = Java.use('com.android.systemui.xr.spatial.impl.TaskSubspaceImpl');
                Menu = Java.use('com.android.wm.shell.windowdecor.XrCaptionMenu');
                Java.choose('com.android.systemui.xr.wm.shell.mixedreality.MixedRealityStateObserver', {
                    onMatch(value) {
                        if (observer !== null) throw new Error('Ambiguous Home Space observer');
                        observer = Java.retain(value);
                    },
                    onComplete() {
                        Java.choose('com.android.systemui.xr.wm.shell.subspace.TaskSubspaceRepositoryImpl', {
                            onMatch(value) {
                                if (repository !== null) throw new Error('Ambiguous task repository');
                                repository = Java.retain(value);
                            },
                            onComplete() {
                        try {
                            if (observer === null) throw new Error('No Home Space observer');
                            if (repository === null) throw new Error('No task repository');
                            installNative();
                            enqueue = (menu, fromShow = false) => {
                                if (!permitted()) return;
                                // show() precedes first layout. View.post() in the Java ticket
                                // waits for the owning view; isShown() here rejects new menus.
                                if (!fromShow && !Ticket.isOpen(menu)) return;
                                const id = Ticket.getMenuTaskId(menu);
                                const packageName = String(Attachment.getMenuPackage(menu));
                                if (['android', 'com.android.systemui', 'com.samsung.android.app.xr.home'].includes(packageName)) return;
                                const root = Attachment.getMenuRoot(menu);
                                const rootId = System.identityHashCode(root);
                                const key = id + ':' + rootId;
                                log('MENU_REQUEST', {taskId: id, fromShow});
                                let entry = tasks.get(id);
                                if (pending.has(key) || entry?.attachments.some(a => a.key === key)) return;
                                if ((entry === undefined && tasks.size >= 32) || pending.size >= 32) {
                                    log('SKIP', {taskId: id, reason: 'Task limit reached'});
                                    return;
                                }
                                const retainedMenu = Java.retain(menu);
                                pending.add(key);
                                let found = null;
                                        try {
                                            const candidate = repository.getTaskSubspace(id);
                                            if (candidate === null) {
                                                log('SKIP', {taskId: id, reason: 'No task in repository'});
                                                return;
                                            }
                                            found = Java.retain(Java.cast(candidate, Task));
                                            const details = {taskId: id, attached: String(found.isAttached().getValue()),
                                                rendering2D: String(found.is2DRenderingEnabled().getValue()),
                                                packageName,
                                                pulseAgeMs: nowMs() - lastSupervisor};
                                            if (!permitted() || !taskEligible(found) ||
                                                System.identityHashCode(Attachment.getMenuRoot(retainedMenu)) !== rootId) {
                                                log('SKIP', {...details, reason: 'Task/menu not eligible'});
                                                return;
                                            }
                                            entry = tasks.get(id);
                                            const handle = String(found.getCpmWindowNode().getNativeHandle());
                                            if (entry !== undefined && entry.handle !== handle) throw new Error('Task node replaced');
                                            if (entry === undefined) {
                                                const baseline = observed.get(id);
                                                if (!baseline || nowMs() - baseline.now > 2000 || baseline.curvature !== 0) {
                                                    log('SKIP', {taskId: id, reason: 'No recent flat renderer baseline'});
                                                    return;
                                                }
                                                const session = Java.retain(Session.supervised(id, found.getCpmWindowNode()));
                                                entry = {task: found, handle, session, attachments: [],
                                                    started: nowMs(), deadline: nowMs() + 2000};
                                                found = null;
                                                tasks.set(id, entry);
                                            }
                                            if (entry.attachments.length >= 8) throw new Error('Menu limit reached');
                                            const ticket = Java.retain(Ticket.$new(retainedMenu, entry.session));
                                            entry.attachments.push({key, ticket});
                                            log('MENU', {taskId: id});
                                        } catch (error) { fail(error); }
                                        finally {
                                            pending.delete(key);
                                            retainedMenu.$dispose();
                                            if (found !== null) found.$dispose();
                                        }
                            };
                            const show = Menu.show.overload();
                            show.implementation = function () {
                                const result = show.call(this);
                                try { enqueue(this, true); } catch (error) { fail(error); }
                                return result;
                            };
                            // Heap enumeration is initialization-only: doing it after arming
                            // timers can block pulse dispatch long enough to fail closed.
                            // Module boot normally has no open menu; close/reopen an existing one.
                            lastSupervisor = nowMs();
                            timer = setInterval(poll, 500);
                            log('READY', {pid: Process.id, lifetime: 'externally-supervised', maxTasks: 32});
                            resolve(true);
                        } catch (error) { fail(error); reject(String(error)); }
                            },
                        });
                    },
                });
            } catch (error) { fail(error); reject(String(error)); }
        }));
    },
    onFridaStdin(line) {
        const command = line.trim();
        if (command === 'pulse' && !stopped) lastSupervisor = nowMs();
        else if (command === 'stop') stop('module disabled or supervisor stopped');
    },
};
