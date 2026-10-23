package local.gxr.curvature;

/** Task-local controller. All entry points, including watchdog ticks, serialize. */
public final class CurvatureLease implements AutoCloseable {
    public interface Clock {
        long milliseconds();
    }

    public interface Sink {
        void apply(float curvature) throws Exception;
    }

    private final Sink sink;
    private final Clock clock;
    private final long leaseMs;
    private final long hardDeadline;
    private long deadline;
    private long lastTime;
    private boolean closed;
    private boolean dirty;
    private float value;
    private String status = "ready";

    /** Caller must verify a flat baseline and arm an independent watchdog first. */
    public CurvatureLease(Sink sink, Clock clock, long leaseMs, long maximumMs) {
        this(sink, clock, leaseMs, maximumMs, false);
    }

    /** No trial cap; still expires unless an external supervisor renews it. */
    public static CurvatureLease supervised(Sink sink, Clock clock, long leaseMs) {
        return new CurvatureLease(sink, clock, leaseMs, 0, true);
    }

    private CurvatureLease(Sink sink, Clock clock, long leaseMs, long maximumMs, boolean supervised) {
        if (sink == null || clock == null || leaseMs < 100 || leaseMs > 5000
                || (!supervised && (maximumMs < leaseMs || maximumMs > 60000))) {
            throw new IllegalArgumentException("Invalid lease parameters");
        }
        this.sink = sink;
        this.clock = clock;
        this.leaseMs = leaseMs;
        long now = clock.milliseconds();
        if (now < 0 || now > Long.MAX_VALUE - maximumMs) {
            throw new IllegalArgumentException("Invalid monotonic time");
        }
        hardDeadline = supervised ? Long.MAX_VALUE : now + maximumMs;
        deadline = now + leaseMs;
        lastTime = now;
    }

    private long readTime() {
        long now = clock.milliseconds();
        if (now < lastTime) return -1;
        lastTime = now;
        return now;
    }

    private boolean expired(long now) {
        return now < 0 || now >= deadline || now >= hardDeadline;
    }

    /** Only the injector heartbeat renews this lease; UI interaction never does. */
    public synchronized boolean heartbeat() throws Exception {
        long now = readTime();
        if (closed || expired(now)) {
            close();
            return false;
        }
        deadline = Math.min(hardDeadline, now + leaseMs);
        return true;
    }

    public synchronized void set(float curvature) throws Exception {
        if (!Float.isFinite(curvature) || curvature < 0 || curvature > 1) {
            throw new IllegalArgumentException("Curvature must be 0..1");
        }
        if (closed || expired(readTime())) {
            close();
            throw new IllegalStateException("Curvature lease expired");
        }
        // A transaction may apply and then throw: mark dirty before submitting.
        dirty = true;
        try {
            sink.apply(curvature);
            value = curvature;
            dirty = curvature != 0;
            status = curvature == 0 ? "flat" : "curved";
        } catch (Exception error) {
            try {
                close();
            } catch (Exception rollbackError) {
                error.addSuppressed(rollbackError);
            }
            throw error;
        }
    }

    /** Called by a Java-owned watchdog, independent of Frida callbacks/ADB. */
    public synchronized void tick() throws Exception {
        if (closed || expired(readTime())) close();
    }

    /** Retryable: a failed restore never claims that the task is flat. */
    @Override
    public synchronized void close() throws Exception {
        closed = true;
        if (dirty) {
            status = "restore-pending";
            sink.apply(0);
            dirty = false;
            value = 0;
        }
        status = "restored";
    }

    public synchronized float getValue() { return value; }
    public synchronized String getStatus() { return status; }
}
