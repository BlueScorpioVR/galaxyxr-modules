package local.gxr.curvature;

import java.lang.reflect.InvocationTargetException;
import java.lang.reflect.Method;

/** Reflection adapter for the verified firmware's hidden CPM transaction API. */
public final class CpmTransaction implements CurvatureLease.Sink, AutoCloseable {
    private final Object node;
    private final Class<?> updatesClass;
    private final Method setCurvature;
    private final Method apply;
    private final Method close;
    private final float maximum;
    private final Method closeNode;
    private boolean released;

    /** Node selection, flat-baseline verification and lifetime belong to caller. */
    public CpmTransaction(Object node) throws Exception {
        this(node, 1);
    }

    public CpmTransaction(Object node, float maximum) throws Exception {
        this(node, maximum, false);
    }

    /** Own a second reference to the SAME node, never the caller's wrapper. */
    public static CpmTransaction owned(Object source, float maximum) throws Exception {
        Class<?> type = Class.forName("android.graphics.CPM$Node");
        if (!type.isInstance(source)) throw new IllegalArgumentException("Not a CPM node");
        // Firmware deepCopy calls nativeCopyHandle; it does not clone the scene.
        // Called on the menu's owner thread, before task teardown can close source.
        invoke(type.getMethod("getNativeHandle"), source);
        Object copy = invoke(type.getMethod("deepCopy"), source);
        try {
            invoke(type.getMethod("getNativeHandle"), copy);
            if (copy == source || !source.equals(copy)) {
                throw new IllegalStateException("Copied handle does not identify the original node");
            }
            return new CpmTransaction(copy, maximum, true);
        } catch (Exception | Error failure) {
            if (copy != source && copy != null) {
                try { invoke(type.getMethod("close"), copy); }
                catch (Exception cleanup) { failure.addSuppressed(cleanup); }
            }
            throw failure;
        }
    }

    private CpmTransaction(Object node, float maximum, boolean ownsNode) throws Exception {
        if (!Float.isFinite(maximum) || maximum <= 0 || maximum > CurvatureRange.MAXIMUM) {
            throw new IllegalArgumentException("Invalid curvature maximum");
        }
        this.maximum = maximum;
        Class<?> nodeClass = Class.forName("android.graphics.CPM$Node");
        if (!nodeClass.isInstance(node)) throw new IllegalArgumentException("Not a CPM node");
        this.node = node;
        closeNode = ownsNode ? nodeClass.getMethod("close") : null;
        updatesClass = Class.forName("android.graphics.CPM$NodeUpdates");
        setCurvature = updatesClass.getMethod("setCurvature", nodeClass, float.class);
        apply = updatesClass.getMethod("apply");
        close = updatesClass.getMethod("close");
        updatesClass.getConstructor();
    }

    private static Object invoke(Method method, Object target, Object... args) throws Exception {
        try {
            return method.invoke(target, args);
        } catch (InvocationTargetException wrapped) {
            Throwable cause = wrapped.getCause();
            if (cause instanceof Exception) throw (Exception) cause;
            if (cause instanceof Error) throw (Error) cause;
            throw wrapped;
        }
    }

    @Override
    public synchronized void apply(float curvature) throws Exception {
        if (released) throw new IllegalStateException("Owned node handle released");
        if (!Float.isFinite(curvature) || curvature < 0 || curvature > maximum) {
            throw new IllegalArgumentException("Curvature outside configured range");
        }
        final Object updates = updatesClass.getConstructor().newInstance();
        Throwable primary = null;
        try {
            invoke(setCurvature, updates, node, curvature);
            invoke(apply, updates);
        } catch (Exception | Error error) {
            primary = error;
            throw error;
        } finally {
            try {
                invoke(close, updates);
            } catch (Exception | Error closeError) {
                if (primary != null) primary.addSuppressed(closeError);
                else throw closeError;
            }
        }
    }

    /** Only after the lease has successfully restored flat. Never close source. */
    @Override
    public synchronized void close() throws Exception {
        if (released) return;
        if (closeNode != null) invoke(closeNode, node);
        released = true;
    }
}
