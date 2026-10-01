package com.neonveins.game;

import android.annotation.SuppressLint;
import android.app.Activity;
import android.content.SharedPreferences;
import android.os.Bundle;
import android.view.KeyEvent;
import android.view.View;
import android.view.Window;
import android.view.WindowManager;
import android.webkit.ConsoleMessage;
import android.webkit.JavascriptInterface;
import android.webkit.ValueCallback;
import android.webkit.WebChromeClient;
import android.webkit.WebResourceRequest;
import android.webkit.WebResourceResponse;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;

import java.io.InputStream;

/**
 * Hosts the single-file game (assets/index.html) in a full-screen WebView.
 * The page is served from https://appassets.androidplatform.net so it runs in a secure context
 * (needed for gyroscope head tracking, storage and WebGPU/WebGL2). CDN files come from WebCache, so it plays offline.
 * JS bridge "NVAndroid" lets the game read/persist the Normal/Cardboard mode and handle the Back button.
 */
public class GameActivity extends Activity {
    private static final String HOST = "appassets.androidplatform.net";
    private WebView web;
    private String mode = "normal";

    @SuppressLint({"SetJavaScriptEnabled", "AddJavascriptInterface"})
    @Override
    protected void onCreate(Bundle savedInstanceState) {
        setTheme(android.R.style.Theme_Black_NoTitleBar_Fullscreen);
        super.onCreate(savedInstanceState);
        requestWindowFeature(Window.FEATURE_NO_TITLE);
        getWindow().addFlags(WindowManager.LayoutParams.FLAG_FULLSCREEN | WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);

        String m = getIntent().getStringExtra(LauncherActivity.KEY_MODE);
        mode = m != null ? m : prefs().getString(LauncherActivity.KEY_MODE, "normal");

        WebView.setWebContentsDebuggingEnabled(true);
        web = new WebView(this);
        web.setBackgroundColor(0xff05030c);
        WebSettings s = web.getSettings();
        s.setJavaScriptEnabled(true);
        s.setDomStorageEnabled(true);
        s.setDatabaseEnabled(true);
        s.setMediaPlaybackRequiresUserGesture(false);
        s.setAllowFileAccess(false);
        s.setCacheMode(WebSettings.LOAD_DEFAULT);
        s.setMixedContentMode(WebSettings.MIXED_CONTENT_NEVER_ALLOW);

        web.addJavascriptInterface(new Bridge(), "NVAndroid");
        web.setWebChromeClient(new WebChromeClient() {
            @Override public boolean onConsoleMessage(ConsoleMessage c) { android.util.Log.d("NeonVeins", c.message() + " @" + c.lineNumber()); return true; }
        });
        web.setWebViewClient(new WebViewClient() {
            @Override
            public WebResourceResponse shouldInterceptRequest(WebView view, WebResourceRequest req) {
                if (!HOST.equals(req.getUrl().getHost())) return WebCache.serve(GameActivity.this, req); // CDN files: bundled / cached for offline play
                String path = req.getUrl().getPath();
                if (path == null || path.equals("/") || path.isEmpty()) path = "/index.html";
                try {
                    InputStream in = path.equals("/index.html") ? Updater.openGame(GameActivity.this) : getAssets().open(path.substring(1)); // newest game: GitHub download or bundled
                    return new WebResourceResponse(mime(path), "utf-8", in);
                } catch (Exception e) {
                    return new WebResourceResponse("text/plain", "utf-8", 404, "Not Found", null, null);
                }
            }
            @Override
            public boolean shouldOverrideUrlLoading(WebView view, WebResourceRequest req) { return !HOST.equals(req.getUrl().getHost()); }
        });
        setContentView(web);
        if (savedInstanceState != null) web.restoreState(savedInstanceState);
        else {
            // make sure the newest game from GitHub is in place before loading it (gives up after 8 s, e.g. offline)
            web.loadData("<body style='background:#05030c;color:#19f0ff;font:16px monospace;display:flex;align-items:center;justify-content:center;height:100vh;margin:0'>CHECKING FOR UPDATES…</body>", "text/html", "utf-8");
            if (!Updater.running && System.currentTimeMillis() - Updater.lastDone > 60000) Updater.check(this, new Updater.Listener() { public void status(String t) { } public void appUpdate(int c, String n, String no, String s) { } });
            Updater.whenIdle(this, new Runnable() { @Override public void run() { web.loadUrl("https://" + HOST + "/index.html"); } }, 8000);
        }
    }

    private static String mime(String p) {
        if (p.endsWith(".html")) return "text/html";
        if (p.endsWith(".js")) return "application/javascript";
        if (p.endsWith(".css")) return "text/css";
        if (p.endsWith(".png")) return "image/png";
        if (p.endsWith(".json")) return "application/json";
        return "application/octet-stream";
    }

    private SharedPreferences prefs() { return getSharedPreferences(LauncherActivity.PREFS, MODE_PRIVATE); }

    /** Exposed to the page as window.NVAndroid */
    class Bridge {
        @JavascriptInterface public String getMode() { return mode; }
        @JavascriptInterface public void setMode(String m) { mode = "cardboard".equals(m) ? "cardboard" : "normal"; prefs().edit().putString(LauncherActivity.KEY_MODE, mode).apply(); }
        @JavascriptInterface public void exitToLauncher() { runOnUiThread(new Runnable() { @Override public void run() { finish(); } }); }
        @JavascriptInterface public String version() { return "1.0"; }
    }

    @Override
    public boolean onKeyDown(int keyCode, KeyEvent event) {
        if (keyCode == KeyEvent.KEYCODE_BACK) {
            // Back = pause / close menus in-game; on the title screen it returns to the mode launcher
            web.evaluateJavascript("window.NVAndroidBack ? NVAndroidBack() : 'exit'", new ValueCallback<String>() {
                @Override public void onReceiveValue(String r) { if (r != null && r.contains("exit")) finish(); }
            });
            return true;
        }
        return super.onKeyDown(keyCode, event);
    }

    @Override protected void onResume() { super.onResume(); web.onResume(); immersive(); }
    @Override protected void onPause() { web.onPause(); super.onPause(); }
    @Override protected void onDestroy() { web.destroy(); super.onDestroy(); }
    @Override protected void onSaveInstanceState(Bundle out) { super.onSaveInstanceState(out); web.saveState(out); }
    @Override public void onWindowFocusChanged(boolean f) { super.onWindowFocusChanged(f); if (f) immersive(); }

    private void immersive() {
        getWindow().getDecorView().setSystemUiVisibility(View.SYSTEM_UI_FLAG_FULLSCREEN | View.SYSTEM_UI_FLAG_HIDE_NAVIGATION | View.SYSTEM_UI_FLAG_IMMERSIVE_STICKY
                | View.SYSTEM_UI_FLAG_LAYOUT_STABLE | View.SYSTEM_UI_FLAG_LAYOUT_HIDE_NAVIGATION | View.SYSTEM_UI_FLAG_LAYOUT_FULLSCREEN);
    }
}
