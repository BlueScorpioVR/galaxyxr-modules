package android.graphics;

/** Host-only fake: never include tests/ in an Android payload. */
public final class CPM {
    public static int created;
    public static int closed;
    public static int copied;
    public static int nodeClosed;
    public static final class Node {
        private final Node original;
        private boolean released;
        public float curvature;
        public boolean failApply;
        public boolean failClose;
        public Node() { original = this; }
        private Node(Node original) { this.original = original; }
        public long getNativeHandle() {
            if (released) throw new IllegalStateException("Attempt to use CPM.Node after close.");
            return 1;
        }
        public Node deepCopy() {
            getNativeHandle();
            copied++;
            return new Node(original);
        }
        public void close() {
            if (!released) { released = true; nodeClosed++; }
        }
        @Override public boolean equals(Object other) {
            return other instanceof Node && ((Node) other).original == original;
        }
        @Override public int hashCode() { return System.identityHashCode(original); }
    }

    public static final class NodeUpdates {
        private Node node;
        private float value;
        public NodeUpdates() { created++; }
        public NodeUpdates setCurvature(Node node, float curvature) {
            node.getNativeHandle();
            this.node = node.original;
            value = curvature;
            return this;
        }
        public void apply() {
            // Model partial success: the transaction takes effect before error.
            node.curvature = value;
            if (node.failApply) throw new IllegalStateException("apply failed");
        }
        public void close() {
            closed++;
            if (node.failClose) throw new IllegalStateException("close failed");
        }
    }
}
