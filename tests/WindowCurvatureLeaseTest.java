import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.TimeUnit;
import local.gxr.curvature.CurvatureLease;
import local.gxr.curvature.LeaseWatchdog;
import local.gxr.curvature.CurvatureRange;

public final class WindowCurvatureLeaseTest {
    private static final class Fake implements CurvatureLease.Clock, CurvatureLease.Sink {
        long now = 100;
        int failures;
        final List<Float> writes = new ArrayList<>();
        public long milliseconds() { return now; }
        public void apply(float value) throws Exception {
            writes.add(value);
            if (failures > 0) {
                failures--;
                throw new Exception("simulated transaction failure");
            }
        }
        CurvatureLease lease() { return new CurvatureLease(this, this, 1000, 5000); }
    }

    private static void check(boolean value) {
        if (!value) throw new AssertionError();
    }

    public static void main(String[] args) throws Exception {
        Fake f = new Fake();
        CurvatureLease lease = f.lease();
        lease.set(.5f);
        f.now = 1099;
        lease.tick();
        check(lease.getValue() == .5f);
        f.now = 1100;
        lease.tick();
        check("restored".equals(lease.getStatus()) && lease.getValue() == 0);
        int count = f.writes.size();
        lease.close();
        check(f.writes.size() == count && !lease.heartbeat());
        try { lease.set(1); throw new AssertionError(); }
        catch (IllegalStateException expected) { }

        f = new Fake();
        lease = f.lease();
        for (int i = 0; i < 5; i++) {
            lease.set(1);
            f.now += 999;
            check(lease.heartbeat());
        }
        f.now = 5100;
        check(!lease.heartbeat() && lease.getValue() == 0);

        f = new Fake();
        lease = f.lease();
        for (float invalid : new float[] {-1, 1.01f, Float.NaN, Float.POSITIVE_INFINITY}) {
            try { lease.set(invalid); throw new AssertionError(); }
            catch (IllegalArgumentException expected) { }
        }
        check(f.writes.isEmpty());
        f.failures = 2;
        try { lease.set(1); throw new AssertionError(); }
        catch (Exception expected) { check(expected.getSuppressed().length == 1); }
        check("restore-pending".equals(lease.getStatus()));
        lease.tick();
        check("restored".equals(lease.getStatus()) && f.writes.size() == 3);

        f = new Fake();
        lease = f.lease();
        f.now = 1100;
        lease.tick();
        check(f.writes.isEmpty());
        f = new Fake();
        lease = f.lease();
        lease.set(.4f);
        f.now = 99;
        check(!lease.heartbeat() && lease.getValue() == 0);
        f.now = 101;
        check(!lease.heartbeat());
        try (CurvatureLease invalid = new CurvatureLease(f, f, 0, 5000)) {
            throw new AssertionError(invalid.getStatus());
        }
        catch (IllegalArgumentException expected) { }
        Fake left = new Fake();
        Fake right = new Fake();
        CurvatureLease leftLease = left.lease();
        CurvatureLease rightLease = right.lease();
        leftLease.set(.2f);
        rightLease.set(.9f);
        leftLease.set(0);
        check(leftLease.getValue() == 0 && rightLease.getValue() == .9f);
        leftLease.close();
        rightLease.set(.7f);
        check(rightLease.getValue() == .7f);
        rightLease.close();
        Fake extended = new Fake();
        float[] width = {.5f};
        CurvatureRange range = new CurvatureRange(extended);
        range.configure(() -> width[0]);
        CurvatureLease extendedLease = new CurvatureLease(range, extended, 1000, 5000);
        extendedLease.set(1);
        check(extended.writes.get(0) == 3);
        width[0] = Float.NaN; // A destroyed/unreadable task must not block expiry rollback.
        extended.now = 1100;
        extendedLease.tick();
        check("restored".equals(extendedLease.getStatus()) && range.getApplied() == 0);
        check(extended.writes.get(1) == 0);
        extendedLease.close();
        Fake supervised = new Fake();
        try (CurvatureLease running = CurvatureLease.supervised(supervised, supervised, 1000)) {
            running.set(.5f);
            for (int i = 0; i < 120; i++) {
                supervised.now += 999;
                check(running.heartbeat());
            }
            check(running.getValue() == .5f); // Beyond the old 60-second trial limit.
            supervised.now += 1000;
            check(!running.heartbeat() && running.getValue() == 0);
        }
        CountDownLatch restored = new CountDownLatch(1);
        final long origin = System.nanoTime();
        CurvatureLease real = new CurvatureLease(value -> {
            if (value == 0) restored.countDown();
        }, () -> (System.nanoTime() - origin) / 1000000, 200, 1000);
        try (LeaseWatchdog watchdog = new LeaseWatchdog(real)) {
            check(watchdog.isAlive());
            real.set(.75f);
            check(restored.await(3, TimeUnit.SECONDS));
            check("restored".equals(real.getStatus()) && watchdog.getLastError() == null);
        }
        System.out.println("PASS: expiry, hard deadline, validation, rollback retry, idempotency");
    }
}
