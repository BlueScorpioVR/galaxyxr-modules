package local.gxr.curvature;

/** Experimental geometric guard, not a guarantee of renderer/input correctness. */
public final class CurvatureRange implements CurvatureLease.Sink {
    public interface WidthSource { float meters() throws Exception; }
    // Scale BOTH caps: new 100% equals v0.1.0's 75% at every window width.
    public static final float STRENGTH_SCALE = .75f;
    public static final float MAXIMUM = 4f * STRENGTH_SCALE;
    public static final float MAX_ARC = (float) Math.toRadians(150) * STRENGTH_SCALE;
    private final CurvatureLease.Sink output;
    private WidthSource width;
    private float applied;
    private float ceiling = STRENGTH_SCALE;

    public CurvatureRange(CurvatureLease.Sink output) { this.output = output; }

    public synchronized void configure(WidthSource source) throws Exception {
        if (source == null) throw new IllegalArgumentException("Missing task width");
        float limit = limit(source.meters());
        width = source;
        ceiling = applied == 0 ? limit : Math.min(ceiling, limit);
    }

    public static float limit(float meters) {
        if (!Float.isFinite(meters) || meters <= 0 || meters > 20) {
            throw new IllegalArgumentException("Invalid task width in meters");
        }
        return Math.min(MAXIMUM, MAX_ARC / meters);
    }

    public synchronized float maximum() throws Exception {
        if (width != null) ceiling = Math.min(ceiling, limit(width.meters()));
        return ceiling;
    }

    @Override public synchronized void apply(float normalized) throws Exception {
        if (!Float.isFinite(normalized) || normalized < 0 || normalized > 1) {
            throw new IllegalArgumentException("Strength must be 0..1");
        }
        // Flat restoration must never depend on a still-readable task object.
        float value = normalized == 0 ? 0 : normalized * maximum();
        output.apply(value);
        applied = value;
    }

    public synchronized float getApplied() { return applied; }

    public synchronized float getCeiling() { return ceiling; }
}
