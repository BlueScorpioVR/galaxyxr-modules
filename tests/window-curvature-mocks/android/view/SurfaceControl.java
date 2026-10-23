package android.view;

/** Host-only fake for the independent compositor crop. */
public final class SurfaceControl {
    public int width;
    public int height;
    public static boolean failApply;
    public static int closed;
    public static final class Transaction {
        private SurfaceControl surface;
        private int width;
        private int height;
        public Transaction setWindowCrop(SurfaceControl target, int width, int height) {
            surface = target;
            this.width = width;
            this.height = height;
            return this;
        }
        public void apply() {
            if (failApply) throw new IllegalStateException("crop commit failed");
            surface.width = width;
            surface.height = height;
        }
        public void close() { closed++; }
    }
}
