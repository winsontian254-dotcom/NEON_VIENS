package com.neonveins.game;

import android.app.Activity;
import android.app.PendingIntent;
import android.content.Context;
import android.content.Intent;
import android.content.SharedPreferences;
import android.content.pm.PackageInstaller;
import android.net.Uri;
import android.os.Build;
import android.provider.Settings;
import android.util.Base64;

import org.json.JSONObject;

import java.io.File;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.io.InputStream;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.security.MessageDigest;

/**
 * Keeps the app current from GitHub (public repo, no login):
 *  - the game (index.html) updates silently: the newest commit's file is downloaded, verified against GitHub's blob hash and used next launch;
 *  - native app changes (android/version.json versionCode goes up) offer a one-tap install of android/NeonVeins.apk from that commit.
 * Offline, everything keeps running from the last good copy.
 */
final class Updater {
    static final String OWNER = "winsontian254-dotcom", REPO = "NEON_VIENS", BRANCH = "claude/festive-faraday-4v0m9s";
    private static final String API = "https://api.github.com/repos/" + OWNER + "/" + REPO;
    private static final String RAW = "https://raw.githubusercontent.com/" + OWNER + "/" + REPO + "/";
    static final String ACTION_INSTALL = "com.neonveins.game.INSTALL_STATUS";

    interface Listener {
        void status(String text);
        void appUpdate(int versionCode, String versionName, String notes, String sha);
    }

    // ---------- which copy of the game to run: bundled in the APK, or a newer one downloaded from GitHub ----------
    static File downloadedGame(Context c) { return new File(c.getFilesDir(), "game/index.html"); }

    static JSONObject bundledInfo(Context c) {
        try { return new JSONObject(new String(WebCache.readAll(c.getAssets().open("build.json")), "UTF-8")); } catch (Exception e) { return new JSONObject(); }
    }

    /** true when the downloaded game is newer than the one bundled in this APK */
    static boolean useDownloaded(Context c) {
        SharedPreferences p = prefs(c);
        if (!downloadedGame(c).exists()) return false;
        String latest = p.getString("latestBlob", ""), got = p.getString("gameBlob", "");
        if (!latest.isEmpty()) return got.equals(latest) && !latest.equals(bundledInfo(c).optString("blob", "")); // GitHub's newest file wins
        return p.getString("gameDate", "").compareTo(bundledInfo(c).optString("date", "")) > 0;
    }

    // a check in flight: the game waits for it so it always opens the newest version
    static volatile boolean running = false;
    static volatile long lastDone = 0;
    private static final java.util.List<Runnable> waiters = new java.util.ArrayList<>();
    static void whenIdle(final Activity a, final Runnable r, long timeoutMs) {
        synchronized (waiters) { if (!running) { a.runOnUiThread(r); return; } waiters.add(r); }
        new android.os.Handler(android.os.Looper.getMainLooper()).postDelayed(new Runnable() { @Override public void run() { boolean mine; synchronized (waiters) { mine = waiters.remove(r); } if (mine) r.run(); } }, timeoutMs);
    }
    private static void finish(Activity a) {
        java.util.List<Runnable> rs; synchronized (waiters) { running = false; lastDone = System.currentTimeMillis(); rs = new java.util.ArrayList<>(waiters); waiters.clear(); }
        for (Runnable r : rs) a.runOnUiThread(r);
    }

    static String activeBlob(Context c) { return useDownloaded(c) ? prefs(c).getString("gameBlob", "") : bundledInfo(c).optString("blob", ""); }

    static InputStream openGame(Context c) throws java.io.IOException {
        return useDownloaded(c) ? new FileInputStream(downloadedGame(c)) : c.getAssets().open("index.html");
    }

    // ---------- the check ----------
    static void check(final Activity a, final Listener l) {
        synchronized (waiters) { if (running) return; running = true; }
        new Thread(new Runnable() {
            @Override public void run() {
                try {
                    JSONObject commit = new JSONObject(get(API + "/commits/" + Uri.encode(BRANCH, "/")));
                    String sha = commit.getString("sha");
                    JSONObject info = commit.getJSONObject("commit");
                    String msg = info.getString("message").split("\n")[0];
                    String date = info.getJSONObject("committer").getString("date");
                    // 1. game content
                    String blob = new JSONObject(get(API + "/contents/index.html?ref=" + sha)).getString("sha");
                    prefs(a).edit().putString("latestBlob", blob).apply();
                    String note;
                    if (!blob.equals(activeBlob(a))) {
                        post(a, l, "Downloading game update: " + msg + " …");
                        byte[] html = bytes(RAW + sha + "/index.html");
                        if (!gitBlobSha(html).equals(blob)) throw new Exception("download corrupted");
                        File f = downloadedGame(a);
                        f.getParentFile().mkdirs();
                        File tmp = new File(f.getPath() + ".tmp");
                        FileOutputStream o = new FileOutputStream(tmp);
                        o.write(html);
                        o.close();
                        if (f.exists()) f.delete();
                        if (!tmp.renameTo(f)) throw new Exception("could not save update");
                        prefs(a).edit().putString("gameBlob", blob).putString("gameDate", date).putString("gameMsg", msg).apply();
                        note = "Game updated ✓  " + msg;
                    } else note = "Up to date ✓  " + msg;
                    post(a, l, note + "  ·  " + date.replace('T', ' ').replace("Z", " UTC"));
                    // 2. native app
                    JSONObject v = new JSONObject(new String(Base64.decode(new JSONObject(get(API + "/contents/android/version.json?ref=" + sha)).getString("content"), Base64.DEFAULT), "UTF-8"));
                    final int code = v.getInt("versionCode");
                    if (code > installedVersion(a)) {
                        final String name = v.optString("versionName", String.valueOf(code)), notes = v.optString("notes", ""), s = sha;
                        a.runOnUiThread(new Runnable() { @Override public void run() { l.appUpdate(code, name, notes, s); } });
                    }
                } catch (java.net.UnknownHostException e) {
                    post(a, l, "Offline — playing the installed version. Updates are checked when you're back online.");
                } catch (Exception e) {
                    post(a, l, "Couldn't check for updates (" + e.getMessage() + "). The installed version still works.");
                } finally { finish(a); }
            }
        }).start();
    }

    // ---------- installing a newer APK ----------
    static void installApk(final Activity a, final String sha, final Listener l) {
        if (Build.VERSION.SDK_INT >= 26 && !a.getPackageManager().canRequestPackageInstalls()) {
            l.status("Allow \"Install unknown apps\" for Neon Veins, then tap Install again.");
            a.startActivity(new Intent(Settings.ACTION_MANAGE_UNKNOWN_APP_SOURCES, Uri.parse("package:" + a.getPackageName())));
            return;
        }
        new Thread(new Runnable() {
            @Override public void run() {
                try {
                    post(a, l, "Downloading the app update …");
                    byte[] apk = bytes(RAW + sha + "/android/NeonVeins.apk");
                    PackageInstaller pi = a.getPackageManager().getPackageInstaller();
                    int id = pi.createSession(new PackageInstaller.SessionParams(PackageInstaller.SessionParams.MODE_FULL_INSTALL));
                    PackageInstaller.Session s = pi.openSession(id);
                    OutputStream o = s.openWrite("NeonVeins.apk", 0, apk.length);
                    o.write(apk);
                    s.fsync(o);
                    o.close();
                    Intent i = new Intent(a, LauncherActivity.class).setAction(ACTION_INSTALL);
                    int flags = PendingIntent.FLAG_UPDATE_CURRENT | (Build.VERSION.SDK_INT >= 31 ? 0x02000000 /* FLAG_MUTABLE */ : 0);
                    s.commit(PendingIntent.getActivity(a, 7, i, flags).getIntentSender());
                    s.close();
                    post(a, l, "Installing …");
                } catch (Exception e) {
                    post(a, l, "App update failed: " + e.getMessage());
                }
            }
        }).start();
    }

    /** Called with the installer's status intent (LauncherActivity.onNewIntent). */
    static void onInstallStatus(Activity a, Intent intent, Listener l) {
        int st = intent.getIntExtra(PackageInstaller.EXTRA_STATUS, -999);
        if (st == PackageInstaller.STATUS_PENDING_USER_ACTION) {
            Intent confirm = intent.getParcelableExtra(Intent.EXTRA_INTENT);
            if (confirm != null) a.startActivity(confirm.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK));
        } else if (st == PackageInstaller.STATUS_SUCCESS) l.status("App updated ✓");
        else if (st != -999) l.status("Install cancelled or failed: " + intent.getStringExtra(PackageInstaller.EXTRA_STATUS_MESSAGE));
    }

    // ---------- helpers ----------
    static int installedVersion(Context c) {
        try { return c.getPackageManager().getPackageInfo(c.getPackageName(), 0).versionCode; } catch (Exception e) { return 0; }
    }

    private static SharedPreferences prefs(Context c) { return c.getSharedPreferences(LauncherActivity.PREFS, Context.MODE_PRIVATE); }

    private static void post(Activity a, final Listener l, final String s) {
        a.runOnUiThread(new Runnable() { @Override public void run() { l.status(s); } });
    }

    private static String get(String url) throws Exception { return new String(bytes(url), "UTF-8"); }

    private static byte[] bytes(String url) throws Exception {
        HttpURLConnection c = (HttpURLConnection) new URL(url).openConnection();
        c.setConnectTimeout(8000);
        c.setReadTimeout(30000);
        c.setRequestProperty("Accept", "application/vnd.github+json");
        c.setRequestProperty("User-Agent", "NeonVeins-Android");
        c.setUseCaches(false); c.setRequestProperty("Cache-Control", "no-cache");
        try {
            if (c.getResponseCode() != 200) throw new Exception("HTTP " + c.getResponseCode());
            return WebCache.readAll(c.getInputStream());
        } finally {
            c.disconnect();
        }
    }

    /** git's blob id: sha1("blob <len>\0" + content) — lets us verify the download against GitHub's hash */
    static String gitBlobSha(byte[] data) throws Exception {
        MessageDigest md = MessageDigest.getInstance("SHA-1");
        md.update(("blob " + data.length + "\0").getBytes("UTF-8"));
        md.update(data);
        return WebCache.hex(md.digest());
    }
}
