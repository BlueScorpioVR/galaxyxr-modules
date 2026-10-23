package local.gxr.curvature;

import android.os.Handler;
import android.graphics.Rect;
import android.os.Looper;
import android.view.View;
import android.view.ViewGroup;
import android.widget.Button;
import java.lang.reflect.Field;
import java.lang.reflect.Method;

/** One menu opening. Its expiry cleanup also works after injector detachment. */
public final class MenuAttachment implements AutoCloseable {
    private final Object menu;
    private final Object pill;
    private final CurvatureSession session;
    private final int oldHeight;
    private final Handler handler = new Handler(ownerLooper());
    private final ViewGroup parent;
    private final CurvatureControls controls;
    private final View root;
    private volatile boolean closed;
    private volatile String lastError;
    private volatile String layoutSummary = "awaiting layout";
    private int cleanupRetries;
    private static Looper ownerLooper() {
        Looper looper = Looper.myLooper();
        if (looper == null) throw new IllegalStateException("Menu requires an owning looper");
        return looper;
    }
    private final Runnable reap = new Runnable() {
        @Override public void run() {
            if (closed) return;
            Rect visible = new Rect();
            StringBuilder bounds = new StringBuilder("visible=")
                    .append(controls.getGlobalVisibleRect(visible)).append(':').append(visible);
            View current = controls;
            for (int i = 0; i < 12; i++) {
                bounds.append(" | ").append(current.getClass().getSimpleName())
                        .append(':').append(current.getWidth()).append('x').append(current.getHeight())
                        .append("@(").append(current.getLeft()).append(',').append(current.getTop()).append(')')
                        .append(" vis=").append(current.getVisibility()).append(" alpha=").append(current.getAlpha());
                if (!(current.getParent() instanceof View)) break;
                current = (View) current.getParent();
            }
            layoutSummary = bounds.toString();
            String status = session.getStatus();
            if (root.getWindowToken() == null || "restored".equals(status) || "restore-pending".equals(status)) {
                try { close(); }
                catch (Exception error) {
                    lastError = error.toString();
                    if (++cleanupRetries < 3) handler.postDelayed(this, 250);
                }
            } else handler.postDelayed(this, 250);
        }
    };

    private static Object field(Object object, String name) throws Exception {
        for (Class<?> cls = object.getClass(); cls != null; cls = cls.getSuperclass()) {
            try {
                Field member = cls.getDeclaredField(name);
                member.setAccessible(true);
                return member.get(object);
            } catch (NoSuchFieldException ignored) { /* Try superclass. */ }
        }
        throw new NoSuchFieldException(name);
    }

    private static Object call(Object object, String name, Class<?>[] types, Object... args) throws Exception {
        for (Class<?> cls = object.getClass(); cls != null; cls = cls.getSuperclass()) {
            try {
                Method method = cls.getDeclaredMethod(name, types);
                method.setAccessible(true);
                return method.invoke(object, args);
            } catch (NoSuchMethodException ignored) { /* Try superclass. */ }
        }
        throw new NoSuchMethodException(name);
    }

    public static int getMenuTaskId(Object menu) throws Exception {
        return (Integer) field(field(field(menu, "parentDecor"), "mTaskInfo"), "taskId");
    }

    public static View getMenuRoot(Object menu) throws Exception {
        return (View) call(field(menu, "moreActionsPill"), "getView", new Class<?>[0]);
    }

    public static String getMenuPackage(Object menu) throws Exception {
        Object info = field(field(menu, "parentDecor"), "mTaskInfo");
        Object component = field(info, "topActivity");
        if (component == null) throw new IllegalStateException("Task has no top activity");
        return (String) call(component, "getPackageName", new Class<?>[0]);
    }

    public MenuAttachment(Object menu, CurvatureSession session) throws Exception {
        this.menu = menu;
        this.session = session;
        session.configureWidth(new TaskWidth(menu, session.getTaskId()));
        Object decor = field(menu, "parentDecor");
        Object task = field(decor, "mTaskInfo");
        if (((Integer) field(task, "taskId")) != session.getTaskId()) {
            throw new IllegalArgumentException("Menu belongs to another task");
        }
        pill = field(menu, "moreActionsPill");
        oldHeight = (Integer) call(pill, "getHeight", new Class<?>[0]);
        root = (View) call(pill, "getView", new Class<?>[0]);
        int listId = root.getResources().getIdentifier("more_actions_list", "id", "com.android.systemui");
        int buttonId = root.getResources().getIdentifier("app_info_button", "id", "com.android.systemui");
        View list = root.findViewById(listId);
        View template = root.findViewById(buttonId);
        if (!(list instanceof ViewGroup) || !(template instanceof Button)) {
            throw new IllegalStateException("Stock menu layout does not match");
        }
        parent = (ViewGroup) list;
        controls = new CurvatureControls(root.getContext(), (Button) template, session);
        try {
            parent.addView(controls, new ViewGroup.LayoutParams(
                    ViewGroup.LayoutParams.MATCH_PARENT, controls.getRequiredHeight()));
            int expanded = oldHeight + controls.getRequiredHeight();
            call(pill, "setHeight", new Class<?>[] {int.class}, expanded);
            Object window = field(pill, "window");
            Object host = field(window, "mWindowViewHost");
            int width = (Integer) field(menu, "menuWidth");
            // addWindow() installs a separate SurfaceControl container crop.
            // Resizing the view host alone leaves appended rows clipped away.
            Object surface = field(window, "mWindowSurface");
            MenuSurfaceResize.apply(host, surface, width, expanded);
            call(menu, "updateCaptionMenuPillPositions", new Class<?>[0]);
            call(menu, "repositionMenuNodes", new Class<?>[0]);
            handler.post(reap);
        } catch (Exception failure) {
            try { close(); }
            catch (Exception cleanup) { failure.addSuppressed(cleanup); }
            throw failure;
        }
    }

    public String getLastError() { return lastError; }

    public String getLayoutSummary() { return layoutSummary; }

    public boolean isClosed() { return closed; }

    @Override
    public void close() throws Exception {
        if (closed) return;
        if (Looper.myLooper() != handler.getLooper()) {
            handler.post(() -> {
                try { close(); }
                catch (Exception error) {
                    lastError = error.toString();
                    if (++cleanupRetries < 3) handler.postDelayed(reap, 250);
                }
            });
            return;
        }
        handler.removeCallbacks(reap);
        controls.close();
        parent.removeView(controls);
        call(pill, "setHeight", new Class<?>[] {int.class}, oldHeight);
        // Destroy the enlarged backing window rather than leave stale bounds.
        if (field(menu, "moreActionsPill") == pill && root.getWindowToken() != null) {
            call(menu, "close", new Class<?>[0]);
        }
        closed = true;
    }
}
