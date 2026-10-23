package local.gxr.curvature;

import android.content.Context;
import android.graphics.drawable.Drawable;
import android.os.Handler;
import android.os.Looper;
import android.util.TypedValue;
import android.view.View;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.SeekBar;
import android.widget.TextView;

/** Java-owned temporary controls: no click listener calls back into Frida. */
public final class CurvatureControls extends LinearLayout implements AutoCloseable {
    private final CurvatureSession session;
    private final Handler handler = new Handler(ownerLooper());
    private final Button toggle;
    private final TextView label;
    private final SeekBar strength;
    private boolean stopped;
    private boolean tracking;
    private static Looper ownerLooper() {
        Looper looper = Looper.myLooper();
        if (looper == null) throw new IllegalStateException("Controls require an owning looper");
        return looper;
    }
    private final Runnable refresh = new Runnable() {
        @Override public void run() {
            if (stopped) return;
            if ("restored".equals(session.getStatus())
                    || "restore-pending".equals(session.getStatus())) {
                disable("restored".equals(session.getStatus())
                        ? "Controls stopped - window flat" : "Restoration pending");
                return;
            }
            if (!tracking) update();
            handler.postDelayed(this, 250);
        }
    };

    public CurvatureControls(Context context, Button template, CurvatureSession session) {
        super(context);
        if (template == null || session == null) throw new IllegalArgumentException("Missing controls input");
        this.session = session;
        setOrientation(VERTICAL);
        toggle = new Button(context);
        toggle.setTypeface(template.getTypeface());
        toggle.setTextSize(TypedValue.COMPLEX_UNIT_PX, template.getTextSize());
        toggle.setTextColor(template.getTextColors());
        toggle.setGravity(template.getGravity());
        toggle.setPadding(template.getPaddingLeft(), template.getPaddingTop(),
                template.getPaddingRight(), template.getPaddingBottom());
        Drawable background = template.getBackground();
        if (background != null && background.getConstantState() != null) {
            toggle.setBackground(background.getConstantState().newDrawable(getResources()).mutate());
        }
        addView(toggle, new LayoutParams(LayoutParams.MATCH_PARENT, dp(56)));
        label = new TextView(context);
        label.setTextColor(template.getTextColors());
        label.setTextSize(TypedValue.COMPLEX_UNIT_SP, 14);
        label.setPadding(dp(16), 0, dp(16), 0);
        addView(label, new LayoutParams(LayoutParams.MATCH_PARENT, dp(24)));
        strength = new SeekBar(context);
        strength.setMax(100);
        strength.setPadding(dp(24), 0, dp(24), 0);
        strength.setContentDescription("Window curvature strength; zero is flat");
        addView(strength, new LayoutParams(LayoutParams.MATCH_PARENT, dp(48)));
        toggle.setOnClickListener(view -> {
            try { session.toggle(); update(); }
            catch (Exception error) { fail(); }
        });
        strength.setOnSeekBarChangeListener(new SeekBar.OnSeekBarChangeListener() {
            @Override public void onStartTrackingTouch(SeekBar bar) { tracking = true; }
            @Override public void onProgressChanged(SeekBar bar, int progress, boolean fromUser) {
                if (!fromUser || stopped) return;
                label.setText("Curvature: " + progress + "%");
                if (!tracking) applyStrength(progress);
            }
            @Override public void onStopTrackingTouch(SeekBar bar) {
                tracking = false;
                if (!stopped) applyStrength(bar.getProgress());
            }
        });
        update();
        handler.post(refresh);
    }

    private int dp(int value) {
        return Math.round(value * getResources().getDisplayMetrics().density);
    }

    public int getRequiredHeight() { return dp(128); }

    private void applyStrength(int progress) {
        try { session.set(progress / 100f); update(); }
        catch (Exception error) { fail(); }
    }

    private void update() {
        int progress = Math.round(session.getValue() * 100);
        toggle.setText(progress == 0 ? "Curve window" : "Flatten window");
        toggle.setContentDescription(toggle.getText());
        strength.setProgress(progress);
        label.setText("Curvature: " + progress + "%" + (progress == 0 ? " (flat)" : ""));
    }

    private void disable(String message) {
        stopped = true;
        handler.removeCallbacks(refresh);
        toggle.setEnabled(false);
        strength.setEnabled(false);
        label.setText(message);
    }

    private void fail() {
        try { session.close(); }
        catch (Exception ignored) { /* Independent watchdog keeps retrying. */ }
        disable("restored".equals(session.getStatus())
                ? "Control failed - window flat" : "Control failed - restoration pending");
    }

    /** Caller removes this view on its owning looper after closing the session. */
    @Override public void close() {
        disable("Controls stopped");
        toggle.setOnClickListener(null);
        strength.setOnSeekBarChangeListener(null);
        setVisibility(View.GONE);
    }
}
