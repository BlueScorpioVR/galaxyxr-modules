package local.gxr.curvature;

import android.view.View;

/** Schedules attachment on the actual view owner, including an already-open menu. */
public final class MenuAttachmentTicket implements AutoCloseable {
    private final View root;
    private volatile MenuAttachment attachment;
    private volatile boolean closed;
    private volatile String error;
    private final Runnable create;

    public static int getMenuTaskId(Object menu) throws Exception {
        return MenuAttachment.getMenuTaskId(menu);
    }

    public static boolean isOpen(Object menu) {
        try {
            View view = MenuAttachment.getMenuRoot(menu);
            return view != null && view.getWindowToken() != null && view.isShown();
        } catch (Exception ignored) { return false; }
    }

    public MenuAttachmentTicket(Object menu, CurvatureSession session) throws Exception {
        if (getMenuTaskId(menu) != session.getTaskId()) throw new IllegalArgumentException("Wrong task menu");
        root = MenuAttachment.getMenuRoot(menu);
        if (root == null) throw new IllegalStateException("Menu has no view");
        create = () -> {
            if (closed || "restored".equals(session.getStatus())
                    || "restore-pending".equals(session.getStatus())) return;
            try {
                if (root.getWindowToken() == null) throw new IllegalStateException("Menu closed before attachment");
                attachment = new MenuAttachment(menu, session);
                if (closed) attachment.close();
            } catch (Exception failure) { error = failure.toString(); }
        };
        if (!root.post(create)) throw new IllegalStateException("Could not post to menu owner");
    }

    public boolean isAttached() { return attachment != null; }

    public boolean isClosed() {
        MenuAttachment value = attachment;
        return closed || (value != null && value.isClosed());
    }

    public String getLayoutSummary() {
        MenuAttachment value = attachment;
        return value == null ? "awaiting menu-owner attachment" : value.getLayoutSummary();
    }

    public String getLastError() {
        MenuAttachment value = attachment;
        return error != null ? error : value == null ? null : value.getLastError();
    }

    @Override public void close() throws Exception {
        closed = true;
        root.removeCallbacks(create);
        MenuAttachment value = attachment;
        if (value != null) value.close();
    }
}
