import android.graphics.CPM;
import local.gxr.curvature.CpmTransaction;
import local.gxr.curvature.CurvatureSession;
import local.gxr.curvature.CurvatureRange;

public final class WindowCurvatureTransactionTest {
    private static void check(boolean condition) {
        if (!condition) throw new AssertionError();
    }

    public static void main(String[] args) throws Exception {
        CPM.Node left = new CPM.Node();
        CPM.Node right = new CPM.Node();
        try (CpmTransaction transaction = new CpmTransaction(left)) {
        transaction.apply(.6f);
        check(left.curvature == .6f && right.curvature == 0);
        check(CPM.created == 1 && CPM.closed == 1);
        for (float invalid : new float[] {-1, 2, Float.NaN, Float.NEGATIVE_INFINITY}) {
            try { transaction.apply(invalid); throw new AssertionError(); }
            catch (IllegalArgumentException expected) { }
        }
        check(CPM.created == 1);
        try (CpmTransaction invalid = new CpmTransaction(new Object())) {
            invalid.apply(0);
            throw new AssertionError();
        }
        catch (IllegalArgumentException expected) { }
        left.failApply = true;
        left.failClose = true;
        try { transaction.apply(1); throw new AssertionError(); }
        catch (IllegalStateException expected) {
            check("apply failed".equals(expected.getMessage()));
            check(expected.getSuppressed().length == 1);
        }
        check(left.curvature == 1 && CPM.created == 2 && CPM.closed == 2);
        left.failApply = false;
        left.failClose = false;
        transaction.apply(0);
        check(left.curvature == 0 && CPM.created == 3 && CPM.closed == 3);
        }
        try (CurvatureSession session = new CurvatureSession(5100, left, 1000)) {
            check(session.getTaskId() == 5100 && session.getValue() == 0);
            session.toggle();
            check(left.curvature == .375f);
            session.toggle();
            check(left.curvature == 0);
            session.set(.75f);
            session.toggle();
            check(left.curvature == 0);
            session.toggle();
            check(left.curvature == .5625f && right.curvature == 0);
            check(session.heartbeat());
        }
        check(left.curvature == 0);
        float[] width = {.5f};
        try (CurvatureSession session = new CurvatureSession(5131, left, 1000)) {
            session.configureWidth(() -> width[0]);
            session.set(1);
            check(left.curvature == 3 && session.getValue() == 1);
            width[0] = 2;
            session.heartbeat();
            check(left.curvature <= CurvatureRange.MAX_ARC / 2);
            float capped = left.curvature;
            width[0] = .5f;
            session.heartbeat();
            check(left.curvature == capped); // Never silently increase during resize.
            width[0] = Float.NaN;
            try { session.heartbeat(); throw new AssertionError(); }
            catch (IllegalArgumentException expected) { }
            check(left.curvature == 0 && "restored".equals(session.getStatus()));
        }
        for (float invalid : new float[] {0, -1, Float.NaN, Float.POSITIVE_INFINITY, 21}) {
            try { CurvatureRange.limit(invalid); throw new AssertionError(); }
            catch (IllegalArgumentException expected) { }
        }
        try (CurvatureSession session = new CurvatureSession(5131, left, 1000)) {
            session.configureWidth(() -> .5f);
            session.set(1);
            session.toggle();
            check(left.curvature == 0);
            session.toggle();
            check(left.curvature == 3);
        }
        check(left.curvature == 0);
        for (float meters : new float[] {.1f, .5f, .7f, 1, 2, 20}) {
            float oldMaximum = Math.min(4f, (float) Math.toRadians(150) / meters);
            check(Math.abs(CurvatureRange.limit(meters) - oldMaximum * .75f) < .000001f);
        }
        System.out.println("PASS: new 100% equals old 75% for narrow and width-capped windows");
        CPM.Node destroyedWrapper = new CPM.Node();
        int beforeCopy = CPM.copied;
        try (CurvatureSession session = CurvatureSession.supervised(5199, destroyedWrapper)) {
            session.configureWidth(() -> .5f);
            session.set(.5f);
            check(destroyedWrapper.curvature == 1.5f && CPM.copied == beforeCopy + 1);
            destroyedWrapper.close(); // Android tears down its wrapper before poll.
            session.close();
            check(destroyedWrapper.curvature == 0 && "restored".equals(session.getStatus()));
            session.close();
        }
        CPM.Node retry = new CPM.Node();
        CurvatureSession retrySession = CurvatureSession.supervised(5200, retry);
        retrySession.set(.5f);
        retry.close();
        retry.failApply = true;
        try { retrySession.close(); throw new AssertionError(); }
        catch (IllegalStateException expected) { check("restore-pending".equals(retrySession.getStatus())); }
        retry.failApply = false;
        retrySession.close();
        check("restored".equals(retrySession.getStatus()) && retry.curvature == 0);
        System.out.println("PASS: owned same-node handle restores after source close; live failure stays retryable");
        System.out.println("PASS: extended range, width cap, resize reduction, invalid width rollback");
        System.out.println("PASS: CPM node targeting, validation, cleanup, partial failure");
    }
}
