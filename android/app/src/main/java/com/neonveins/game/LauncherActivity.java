package com.neonveins.game;

import android.app.Activity;
import android.content.Intent;
import android.content.SharedPreferences;
import android.graphics.Color;
import android.graphics.Typeface;
import android.graphics.drawable.GradientDrawable;
import android.os.Bundle;
import android.view.Gravity;
import android.view.View;
import android.view.Window;
import android.view.WindowManager;
import android.widget.LinearLayout;
import android.widget.TextView;

/** Start screen: pick Normal or Google Cardboard VR. The choice can also be switched in-game (pause menu, settings, story VR button). */
public class LauncherActivity extends Activity implements Updater.Listener {
    static final String PREFS = "neonveins";
    static final String KEY_MODE = "mode";

    private LinearLayout normalBtn, vrBtn;
    private TextView status, updateBtn;
    private String updateSha;
    private long lastCheck;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        setTheme(android.R.style.Theme_Black_NoTitleBar_Fullscreen);
        super.onCreate(savedInstanceState);
        requestWindowFeature(Window.FEATURE_NO_TITLE);
        getWindow().addFlags(WindowManager.LayoutParams.FLAG_FULLSCREEN);

        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setGravity(Gravity.CENTER);
        root.setBackgroundColor(Color.rgb(5, 3, 12));
        int pad = dp(24);
        root.setPadding(pad, pad, pad, pad);

        TextView title = text("NEON VEINS", 40, Color.rgb(255, 43, 214), true);
        title.setLetterSpacing(0.3f);
        root.addView(title);
        TextView sub = text("NEW AVALON · 2098", 13, Color.rgb(138, 132, 179), false);
        sub.setLetterSpacing(0.3f);
        sub.setPadding(0, dp(4), 0, dp(28));
        root.addView(sub);

        LinearLayout row = new LinearLayout(this);
        row.setOrientation(LinearLayout.HORIZONTAL);
        row.setGravity(Gravity.CENTER);
        normalBtn = card("NORMAL MODE", "Touch controls · full screen", Color.rgb(25, 240, 255));
        vrBtn = card("GOOGLE CARDBOARD VR", "Split screen · head tracking\nTap = fire / use · hold = walk", Color.rgb(61, 255, 168));
        LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(dp(260), LinearLayout.LayoutParams.WRAP_CONTENT);
        lp.setMargins(dp(12), 0, dp(12), 0);
        row.addView(normalBtn, lp);
        row.addView(vrBtn, lp);
        root.addView(row);

        TextView hint = text("Switch any time from the pause menu (Back button) → Switch to VR / Normal Mode. Works offline.", 12, Color.rgb(138, 132, 179), false);
        hint.setPadding(0, dp(22), 0, 0);
        root.addView(hint);

        status = text("Checking GitHub for updates …", 11, Color.rgb(25, 240, 255), false);
        status.setPadding(0, dp(10), 0, 0);
        status.setOnClickListener(new View.OnClickListener() { @Override public void onClick(View v) { checkNow(); } });
        root.addView(status);
        updateBtn = text("", 14, Color.rgb(5, 3, 12), true);
        GradientDrawable ub = new GradientDrawable();
        ub.setColor(Color.rgb(255, 210, 61));
        updateBtn.setBackground(ub);
        updateBtn.setPadding(dp(16), dp(8), dp(16), dp(8));
        updateBtn.setVisibility(View.GONE);
        updateBtn.setOnClickListener(new View.OnClickListener() { @Override public void onClick(View v) { if (updateSha != null) Updater.installApk(LauncherActivity.this, updateSha, LauncherActivity.this); } });
        LinearLayout.LayoutParams ulp = new LinearLayout.LayoutParams(LinearLayout.LayoutParams.WRAP_CONTENT, LinearLayout.LayoutParams.WRAP_CONTENT);
        ulp.topMargin = dp(8);
        root.addView(updateBtn, ulp);

        normalBtn.setOnClickListener(new View.OnClickListener() { @Override public void onClick(View v) { launch("normal"); } });
        vrBtn.setOnClickListener(new View.OnClickListener() { @Override public void onClick(View v) { launch("cardboard"); } });
        setContentView(root);
        highlight();
    }

    @Override
    protected void onResume() {
        super.onResume();
        highlight(); // the mode may have been switched in-game
        if (System.currentTimeMillis() - lastCheck > 10 * 60 * 1000) checkNow();
        getWindow().getDecorView().setSystemUiVisibility(View.SYSTEM_UI_FLAG_FULLSCREEN | View.SYSTEM_UI_FLAG_HIDE_NAVIGATION | View.SYSTEM_UI_FLAG_IMMERSIVE_STICKY | View.SYSTEM_UI_FLAG_LAYOUT_STABLE);
    }

    private void checkNow() { lastCheck = System.currentTimeMillis(); status.setText("Checking GitHub for updates …"); Updater.check(this, this); }

    @Override public void status(String text) { status.setText(text); }

    @Override public void appUpdate(int versionCode, String versionName, String notes, String sha) {
        updateSha = sha;
        updateBtn.setText("INSTALL APP UPDATE v" + versionName + (notes.isEmpty() ? "" : " — " + notes));
        updateBtn.setVisibility(View.VISIBLE);
    }

    @Override
    protected void onNewIntent(Intent intent) {
        super.onNewIntent(intent);
        if (Updater.ACTION_INSTALL.equals(intent.getAction())) Updater.onInstallStatus(this, intent, this);
    }

    private void launch(String mode) {
        prefs().edit().putString(KEY_MODE, mode).apply();
        Intent i = new Intent(this, GameActivity.class);
        i.putExtra(KEY_MODE, mode);
        startActivity(i);
    }

    private void highlight() {
        boolean vr = "cardboard".equals(prefs().getString(KEY_MODE, "normal"));
        normalBtn.setAlpha(vr ? 0.6f : 1f);
        vrBtn.setAlpha(vr ? 1f : 0.6f);
    }

    private SharedPreferences prefs() { return getSharedPreferences(PREFS, MODE_PRIVATE); }

    private LinearLayout card(String head, String body, int color) {
        LinearLayout c = new LinearLayout(this);
        c.setOrientation(LinearLayout.VERTICAL);
        c.setGravity(Gravity.CENTER);
        c.setPadding(dp(18), dp(22), dp(18), dp(22));
        GradientDrawable bg = new GradientDrawable();
        bg.setColor(Color.argb(200, 12, 9, 28));
        bg.setStroke(dp(2), color);
        c.setBackground(bg);
        c.setClickable(true);
        c.setFocusable(true);
        c.addView(text(head, 18, color, true));
        TextView b = text(body, 12, Color.rgb(232, 230, 255), false);
        b.setPadding(0, dp(8), 0, 0);
        c.addView(b);
        return c;
    }

    private TextView text(String s, int sp, int color, boolean bold) {
        TextView t = new TextView(this);
        t.setText(s);
        t.setTextSize(sp);
        t.setTextColor(color);
        t.setGravity(Gravity.CENTER);
        t.setTypeface(Typeface.MONOSPACE, bold ? Typeface.BOLD : Typeface.NORMAL);
        return t;
    }

    private int dp(int v) { return Math.round(v * getResources().getDisplayMetrics().density); }
}
