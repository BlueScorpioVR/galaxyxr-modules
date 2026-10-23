package local.gxr.curvature;

/** Temporary menu prototype session; owns only one previously verified task node. */
public final class CurvatureSession implements AutoCloseable {
    private final int taskId;
    private final CurvatureLease lease;
    private final LeaseWatchdog watchdog;
    private final CurvatureRange range;
    private final CpmTransaction transaction;
    private float preferredStrength = .5f;

    /** Caller verifies task identity, Home Space, flat baseline and native hashes. */
    public CurvatureSession(int taskId, Object node, int durationMs) throws Exception {
        this(taskId, node, durationMs, false);
    }

    public static CurvatureSession supervised(int taskId, Object node) throws Exception {
        return new CurvatureSession(taskId, node, 3000, true);
    }

    private CurvatureSession(int taskId, Object node, int durationMs, boolean supervised) throws Exception {
        if (taskId <= 0 || (!supervised && (durationMs < 1000 || durationMs > 60000))) {
            throw new IllegalArgumentException("Invalid task or trial duration");
        }
        this.taskId = taskId;
        final long origin = System.nanoTime();
        transaction = CpmTransaction.owned(node, CurvatureRange.MAXIMUM);
        range = new CurvatureRange(transaction);
        CurvatureLease.Clock clock = () -> (System.nanoTime() - origin) / 1000000;
        lease = supervised ? CurvatureLease.supervised(range, clock, 3000)
                : new CurvatureLease(range, clock, Math.min(3000, durationMs), durationMs);
        // No set() call is reachable until the independent watchdog is armed.
        try {
            watchdog = new LeaseWatchdog(lease, transaction);
        } catch (Exception failure) {
            try { transaction.close(); }
            catch (Exception cleanup) { failure.addSuppressed(cleanup); }
            throw failure;
        }
    }

    public synchronized void toggle() throws Exception {
        set(lease.getValue() == 0 ? preferredStrength : 0);
    }

    public synchronized void set(float strength) throws Exception {
        lease.set(strength);
        if (strength > 0) preferredStrength = strength;
    }

    /** Only the native agent driver calls this, never a menu click/slider. */
    public synchronized boolean heartbeat() throws Exception {
        if (!lease.heartbeat()) return false;
        try {
            float strength = lease.getValue();
            if (strength > 0 && range.getApplied() > strength * range.maximum()) lease.set(strength);
            return true;
        } catch (Exception error) {
            try { lease.close(); }
            catch (Exception cleanup) { error.addSuppressed(cleanup); }
            throw error;
        }
    }

    public synchronized void configureWidth(CurvatureRange.WidthSource source) throws Exception {
        range.configure(source);
    }

    public float getAppliedCurvature() { return range.getApplied(); }

    public float getMaximumCurvature() { return range.getCeiling(); }

    public int getTaskId() { return taskId; }

    public float getValue() { return lease.getValue(); }

    public String getStatus() { return lease.getStatus(); }

    public String getWatchdogError() { return watchdog.getLastError(); }

    @Override
    public void close() throws Exception { watchdog.close(); }
}
