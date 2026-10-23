import android.view.SurfaceControl;
import java.lang.reflect.InvocationTargetException;
import local.gxr.curvature.MenuSurfaceResize;

public final class WindowCurvatureMenuBoundsTest {
    public static final class Host {
        int width;
        int height;
        public void relayout(int width, int height) { this.width = width; this.height = height; }
    }

    private static void check(boolean condition) {
        if (!condition) throw new AssertionError();
    }

    public static void main(String[] args) throws Exception {
        Host host = new Host();
        SurfaceControl surface = new SurfaceControl();
        MenuSurfaceResize.apply(host, surface, 320, 536);
        check(host.width == 320 && host.height == 536);
        check(surface.width == 320 && surface.height == 536 && SurfaceControl.closed == 1);
        for (int invalid : new int[] {-1, 0, 16385, Integer.MAX_VALUE}) {
            try { MenuSurfaceResize.apply(host, surface, 320, invalid); throw new AssertionError(); }
            catch (IllegalArgumentException expected) { }
        }
        check(SurfaceControl.closed == 1);
        SurfaceControl.failApply = true;
        try { MenuSurfaceResize.apply(host, surface, 320, 600); throw new AssertionError(); }
        catch (InvocationTargetException expected) {
            check(expected.getCause() instanceof IllegalStateException);
        }
        check(SurfaceControl.closed == 2);
        System.out.println("PASS: menu host/crop bounds, invalid sizes, failed-commit cleanup");
    }
}
