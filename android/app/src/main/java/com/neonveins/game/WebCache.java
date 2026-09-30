package com.neonveins.game;

import android.content.Context;
import android.webkit.WebResourceRequest;
import android.webkit.WebResourceResponse;

import java.io.ByteArrayOutputStream;
import java.io.File;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.io.InputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.security.MessageDigest;
import java.util.Arrays;
import java.util.HashMap;
import java.util.HashSet;
import java.util.Map;
import java.util.Set;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

/**
 * Offline support for everything the game pulls from CDNs (Babylon.js, materials, PeerJS, fonts, WebGPU shader tools).
 * Order: a copy refreshed from the network (files/webcache) → the copy bundled in the APK (assets/vendor) → live network (then saved).
 * Cached files are refreshed in the background at most once a day, so the game keeps working with no connection.
 */
final class WebCache {
    private static final Set<String> HOSTS = new HashSet<>(Arrays.asList("cdn.babylonjs.com", "cdn.jsdelivr.net", "fonts.googleapis.com", "fonts.gstatic.com", "unpkg.com"));
    private static final Map<String, String> BUNDLED = new HashMap<>();
    static {
        BUNDLED.put("https://cdn.babylonjs.com/babylon.js", "vendor/babylon.js");
        BUNDLED.put("https://cdn.babylonjs.com/materialsLibrary/babylonjs.materials.min.js", "vendor/babylonjs.materials.min.js");
        BUNDLED.put("https://cdn.jsdelivr.net/npm/peerjs@1.5.4/dist/peerjs.min.js", "vendor/peerjs.min.js");
    }
    private static final long DAY = 24L * 3600 * 1000;
    private static final ExecutorService BG = Executors.newSingleThreadExecutor();

    static WebResourceResponse serve(Context ctx, WebResourceRequest req) {
        if (!"GET".equalsIgnoreCase(req.getMethod()) || req.getUrl().getHost() == null || !HOSTS.contains(req.getUrl().getHost())) return null;
        final String url = req.getUrl().toString();
        final String ua = req.getRequestHeaders() != null ? req.getRequestHeaders().get("User-Agent") : null;
        final Context app = ctx.getApplicationContext();
        final File f = file(app, url);
        String asset = BUNDLED.get(url);
        try {
            if (f.exists()) {
                if (System.currentTimeMillis() - f.lastModified() > DAY) BG.execute(new Runnable() { @Override public void run() { fetch(app, url, ua, f); } });
                return response(new FileInputStream(f), mimeOf(f, url));
            }
            if (asset != null) {
                BG.execute(new Runnable() { @Override public void run() { fetch(app, url, ua, f); } }); // pick up a newer build for next launch
                return response(app.getAssets().open(asset), mime(url));
            }
            if (fetch(app, url, ua, f)) return response(new FileInputStream(f), mimeOf(f, url));
        } catch (Exception ignored) { }
        return null; // let the WebView try (and fail gracefully) on its own
    }

    /** Downloads url into f (atomically). Returns true on success. */
    static synchronized boolean fetch(Context ctx, String url, String ua, File f) {
        HttpURLConnection c = null;
        try {
            c = (HttpURLConnection) new URL(url).openConnection();
            c.setConnectTimeout(6000);
            c.setReadTimeout(20000);
            if (ua != null) c.setRequestProperty("User-Agent", ua); // Google Fonts serves woff2 CSS by user agent
            if (c.getResponseCode() != 200) return false;
            byte[] body = readAll(c.getInputStream());
            File tmp = new File(f.getPath() + ".tmp");
            FileOutputStream o = new FileOutputStream(tmp);
            o.write(body);
            o.close();
            String type = c.getContentType();
            FileOutputStream m = new FileOutputStream(f.getPath() + ".mime");
            m.write((type != null ? type.split(";")[0].trim() : mime(url)).getBytes("UTF-8"));
            m.close();
            return tmp.renameTo(f);
        } catch (Exception e) {
            return false;
        } finally {
            if (c != null) c.disconnect();
        }
    }

    static byte[] readAll(InputStream in) throws java.io.IOException {
        ByteArrayOutputStream b = new ByteArrayOutputStream();
        byte[] buf = new byte[65536];
        int n;
        while ((n = in.read(buf)) > 0) b.write(buf, 0, n);
        in.close();
        return b.toByteArray();
    }

    private static WebResourceResponse response(InputStream in, String mime) {
        WebResourceResponse r = new WebResourceResponse(mime, "utf-8", in);
        Map<String, String> h = new HashMap<>();
        h.put("Access-Control-Allow-Origin", "*"); // fonts and fetch() need CORS
        h.put("Cache-Control", "no-cache");
        r.setResponseHeaders(h);
        return r;
    }

    private static File file(Context ctx, String url) {
        File dir = new File(ctx.getFilesDir(), "webcache");
        dir.mkdirs();
        return new File(dir, sha1(url));
    }

    private static String mimeOf(File f, String url) {
        try {
            File m = new File(f.getPath() + ".mime");
            if (m.exists()) return new String(readAll(new FileInputStream(m)), "UTF-8");
        } catch (Exception ignored) { }
        return mime(url);
    }

    static String mime(String u) {
        String p = u.split("\\?")[0];
        if (p.endsWith(".js")) return "application/javascript";
        if (p.endsWith(".css") || u.contains("fonts.googleapis.com/css")) return "text/css";
        if (p.endsWith(".woff2")) return "font/woff2";
        if (p.endsWith(".woff")) return "font/woff";
        if (p.endsWith(".ttf")) return "font/ttf";
        if (p.endsWith(".wasm")) return "application/wasm";
        if (p.endsWith(".json")) return "application/json";
        if (p.endsWith(".html")) return "text/html";
        return "application/octet-stream";
    }

    static String sha1(String s) {
        try {
            byte[] d = MessageDigest.getInstance("SHA-1").digest(s.getBytes("UTF-8"));
            return hex(d);
        } catch (Exception e) {
            return Integer.toHexString(s.hashCode());
        }
    }

    static String hex(byte[] d) {
        StringBuilder sb = new StringBuilder();
        for (byte b : d) sb.append(String.format("%02x", b));
        return sb.toString();
    }
}
