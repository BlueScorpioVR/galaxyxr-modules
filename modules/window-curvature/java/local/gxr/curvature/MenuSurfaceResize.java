package local.gxr.curvature;

import java.lang.reflect.Method;

/** Resize both independent bounds created by WindowDecoration.addWindow(). */
public final class MenuSurfaceResize {
    private MenuSurfaceResize() { }

    public static void apply(Object host, Object surface, int width, int height) throws Exception {
        if (host == null || surface == null || width <= 0 || height <= 0
                || width > 16384 || height > 16384) {
            throw new IllegalArgumentException("Invalid menu bounds");
        }
        Class<?> surfaceClass = Class.forName("android.view.SurfaceControl");
        if (!surfaceClass.isInstance(surface)) throw new IllegalArgumentException("Not a SurfaceControl");
        Class<?> transactionClass = Class.forName("android.view.SurfaceControl$Transaction");
        Method relayout = host.getClass().getMethod("relayout", int.class, int.class);
        Method crop = transactionClass.getMethod("setWindowCrop", surfaceClass, int.class, int.class);
        Method commit = transactionClass.getMethod("apply");
        Method close = transactionClass.getMethod("close");
        Object transaction = transactionClass.getConstructor().newInstance();
        Exception primary = null;
        try {
            relayout.invoke(host, width, height);
            crop.invoke(transaction, surface, width, height);
            commit.invoke(transaction);
        } catch (Exception error) {
            primary = error;
            throw error;
        } finally {
            try { close.invoke(transaction); }
            catch (Exception closeError) {
                if (primary != null) primary.addSuppressed(closeError);
                else throw closeError;
            }
        }
    }
}
