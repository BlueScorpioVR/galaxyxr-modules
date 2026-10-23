package local.gxr.curvature;

import java.util.concurrent.CountDownLatch;
import java.util.concurrent.TimeUnit;

/** Java-owned rollback loop; never depends on injector callbacks or timers. */
public final class LeaseWatchdog implements AutoCloseable {
    private final CurvatureLease lease;
    private final Thread thread;
    private volatile String lastError;
    private final AutoCloseable resource;

    public LeaseWatchdog(CurvatureLease lease) throws Exception {
        this(lease, null);
    }

    public LeaseWatchdog(CurvatureLease lease, AutoCloseable resource) throws Exception {
        if (lease == null) throw new IllegalArgumentException("Missing lease");
        this.lease = lease;
        this.resource = resource;
        CountDownLatch armed = new CountDownLatch(1);
        thread = new Thread(() -> {
            armed.countDown();
            // Expiry is at most 100 ms late under normal scheduling. A failed
            // restore remains dirty and retryable; do not silently stop on it.
            while (true) {
                try {
                    lease.tick();
                    if ("restored".equals(lease.getStatus())) {
                        release();
                        return;
                    }
                } catch (Exception error) {
                    lastError = error.toString();
                }
                try {
                    Thread.sleep(100);
                } catch (InterruptedException interrupted) {
                    try { lease.close(); }
                    catch (Exception error) { lastError = error.toString(); }
                }
            }
        }, "GxrCurvatureLeaseWatchdog");
        thread.setDaemon(true);
        thread.start();
        if (!armed.await(1000, TimeUnit.MILLISECONDS)) {
            try { lease.close(); }
            finally { thread.interrupt(); }
            throw new IllegalStateException("Watchdog failed to arm");
        }
    }

    public String getLastError() { return lastError; }

    public boolean isAlive() { return thread.isAlive(); }

    private void release() throws Exception {
        if (resource != null) resource.close();
    }

    @Override
    public void close() throws Exception {
        try {
            lease.close();
            release();
        }
        finally { thread.interrupt(); }
    }
}
