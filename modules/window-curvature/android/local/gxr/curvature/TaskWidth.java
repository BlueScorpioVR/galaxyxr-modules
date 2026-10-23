package local.gxr.curvature;

import java.lang.reflect.Field;
import java.lang.reflect.Method;

/** Same bounds/px-to-meters conversion used by this firmware's task repository. */
public final class TaskWidth implements CurvatureRange.WidthSource {
    private final Object decor;
    private final int taskId;

    public TaskWidth(Object menu, int taskId) throws Exception {
        decor = field(menu, "parentDecor");
        this.taskId = taskId;
    }

    private static Object field(Object object, String name) throws Exception {
        for (Class<?> cls = object.getClass(); cls != null; cls = cls.getSuperclass()) {
            try {
                Field member = cls.getDeclaredField(name);
                member.setAccessible(true);
                return member.get(object);
            } catch (NoSuchFieldException ignored) { }
        }
        throw new NoSuchFieldException(name);
    }

    @Override public float meters() throws Exception {
        Object info = field(decor, "mTaskInfo");
        if (((Integer) field(info, "taskId")) != taskId) throw new IllegalStateException("Task changed");
        Object configuration = field(info, "configuration");
        Object windowConfiguration = field(configuration, "windowConfiguration");
        Object bounds = windowConfiguration.getClass().getMethod("getBounds").invoke(windowConfiguration);
        int pixels = (Integer) bounds.getClass().getMethod("width").invoke(bounds);
        Class<?> metrics = Class.forName("com.android.systemui.xr.ui.DisplayMetrics",
                true, decor.getClass().getClassLoader());
        Object instance = metrics.getField("INSTANCE").get(null);
        Method convert = metrics.getMethod("getPxToMeters", int.class);
        return (Float) convert.invoke(instance, pixels);
    }
}
