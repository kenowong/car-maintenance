package com.kenowong.carcare;

import android.annotation.SuppressLint;
import android.app.Activity;
import android.content.Intent;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.os.Parcelable;
import android.provider.MediaStore;
import android.util.Log;
import android.view.KeyEvent;
import android.webkit.ValueCallback;
import android.webkit.WebChromeClient;
import android.webkit.WebResourceRequest;
import android.webkit.WebResourceResponse;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;

import androidx.core.content.FileProvider;
import androidx.webkit.WebViewAssetLoader;

import java.io.File;
import java.io.IOException;
import java.text.SimpleDateFormat;
import java.util.Date;
import java.util.Locale;

/**
 * 完全离线自包含版车管家：
 * 网页资源打包在 APK assets 内，通过 WebViewAssetLoader 以
 * https://appassets.androidplatform.net/assets/ 提供（正常 https origin，
 * localStorage 持久化可靠），不依赖任何网络与外部服务器。
 *
 * v7 修复：网页 <input type="file">（收据/发票凭证）点击无反应 ——
 * WebView 默认不处理文件选择，必须实现 WebChromeClient.onShowFileChooser，
 * 并在 onActivityResult 里把结果回传给网页；同时支持直接调起系统相机拍照。
 */
public class MainActivity extends Activity {

    private static final String TAG = "CarCare";
    private static final String START_URL =
            "https://appassets.androidplatform.net/assets/index.html";
    private static final String LOCAL_HOST = "appassets.androidplatform.net";
    private static final int FILE_CHOOSER_REQUEST = 1001;

    private WebView web;
    private WebViewAssetLoader assetLoader;

    /** 当前挂起的网页文件选择回调（WebView 要求用完必须回调，否则网页控件卡死） */
    private ValueCallback<Uri[]> pendingFileCallback;
    /** 本轮拍照临时文件的输出地址（FileProvider Uri） */
    private Uri pendingCameraUri;

    @SuppressLint("SetJavaScriptEnabled")
    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        // 崩溃日志落盘（App 专属外部目录，无需存储权限，USB 连电脑可见），
        // 便于远程排障；写完仍走系统默认崩溃流程
        final Thread.UncaughtExceptionHandler prev = Thread.getDefaultUncaughtExceptionHandler();
        Thread.setDefaultUncaughtExceptionHandler((t, e) -> {
            try {
                java.io.File dir = getExternalFilesDir("crash");
                if (dir != null) {
                    java.io.PrintWriter w = new java.io.PrintWriter(
                            new java.io.File(dir, "crash.txt"), "UTF-8");
                    e.printStackTrace(w);
                    w.close();
                }
            } catch (Exception ignored) {
            }
            if (prev != null) prev.uncaughtException(t, e);
        });
        setContentView(R.layout.activity_main);
        web = (WebView) findViewById(R.id.web);

        assetLoader = new WebViewAssetLoader.Builder()
                .addPathHandler("/assets/", new WebViewAssetLoader.AssetsPathHandler(this))
                .build();

        web.setWebViewClient(new WebViewClient() {
            @Override
            public WebResourceResponse shouldInterceptRequest(WebView view,
                                                              WebResourceRequest request) {
                return assetLoader.shouldInterceptRequest(request.getUrl());
            }

            @Override
            public boolean shouldOverrideUrlLoading(WebView view, WebResourceRequest request) {
                Uri url = request.getUrl();
                if (LOCAL_HOST.equals(url.getHost())) {
                    return false; // 本地资源由 WebView 正常加载
                }
                // 极少数外部链接交给系统浏览器，不困在 App 里
                try {
                    startActivity(new Intent(Intent.ACTION_VIEW, url));
                } catch (Exception ignored) {
                }
                return true;
            }
        });

        // 关键修复：没有 WebChromeClient 处理 onShowFileChooser，
        // 网页里所有 <input type="file"> 点击都毫无反应
        web.setWebChromeClient(new WebChromeClient() {
            @Override
            public boolean onShowFileChooser(WebView webView,
                                             ValueCallback<Uri[]> callback,
                                             FileChooserParams params) {
                // 上一次的回调必须先作废，否则 WebView 会直接忽略新请求
                if (pendingFileCallback != null) {
                    pendingFileCallback.onReceiveValue(null);
                }
                pendingFileCallback = callback;

                try {
                    Intent chooser = buildFileChooserIntent(params);
                    startActivityForResult(chooser, FILE_CHOOSER_REQUEST);
                } catch (Exception e) {
                    Log.w(TAG, "start file chooser failed", e);
                    pendingFileCallback = null;
                    callback.onReceiveValue(null);
                    return true;
                }
                return true;
            }
        });

        WebSettings s = web.getSettings();
        s.setJavaScriptEnabled(true);
        s.setDomStorageEnabled(true);   // localStorage 持久化（数据存本机）
        s.setDatabaseEnabled(true);
        s.setTextZoom(100);
        s.setSupportZoom(false);
        // NAS 同步：页面 origin 是 https(appassets)，要允许它访问局域网 http://NAS 的
        // 明文服务，必须放行混合内容（否则 fetch http://192.168.x.x 会被 WebView 拦截）
        s.setMixedContentMode(WebSettings.MIXED_CONTENT_ALWAYS_ALLOW);
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
            // 关闭系统强制深色，保持页面原配色
            //noinspection deprecation
            s.setForceDark(WebSettings.FORCE_DARK_OFF);
        }

        if (savedInstanceState != null) {
            web.restoreState(savedInstanceState);
        } else {
            web.loadUrl(START_URL);
        }
    }

    /**
     * 构建文件选择 Intent：
     * - accept 含 image 时以图片为主，并附加「拍照」入口（系统相机，临时文件走 FileProvider）
     * - 其余走通用文档选择器（如导入备份 .json 的场景不受影响）
     */
    private Intent buildFileChooserIntent(WebChromeClient.FileChooserParams params) {
        String accept = params.getAcceptTypes() != null && params.getAcceptTypes().length > 0
                ? params.getAcceptTypes()[0] : "";
        boolean isImage = accept != null && accept.contains("image");

        Intent content = new Intent(Intent.ACTION_GET_CONTENT);
        content.addCategory(Intent.CATEGORY_OPENABLE);
        content.setType(isImage ? "image/*" : "*/*");

        if (!isImage) {
            return Intent.createChooser(content, "选择文件");
        }

        // 图片场景：相册/文件为主选择器，拍照作为快捷入口
        Intent chooser = Intent.createChooser(content, "选择图片或拍照");
        Intent camera = buildCameraIntent();
        if (camera != null) {
            chooser.putExtra(Intent.EXTRA_INITIAL_INTENTS, new Parcelable[]{camera});
        }
        return chooser;
    }

    /** 构建「用系统相机拍一张照片」的 Intent，输出到 cache/carcare/ 下的临时文件 */
    private Intent buildCameraIntent() {
        try {
            File dir = new File(getCacheDir(), "carcare");
            if (!dir.exists() && !dir.mkdirs()) {
                return null;
            }
            String name = new SimpleDateFormat("yyyyMMdd_HHmmss", Locale.US)
                    .format(new Date()) + ".jpg";
            File photo = new File(dir, name);
            pendingCameraUri = FileProvider.getUriForFile(this,
                    getPackageName() + ".fileprovider", photo);

            Intent camera = new Intent(MediaStore.ACTION_IMAGE_CAPTURE);
            camera.putExtra(MediaStore.EXTRA_OUTPUT, pendingCameraUri);
            camera.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION
                    | Intent.FLAG_GRANT_WRITE_URI_PERMISSION);
            if (camera.resolveActivity(getPackageManager()) == null) {
                return null; // 设备没有任何相机应用
            }
            return camera;
        } catch (Exception e) {
            Log.w(TAG, "build camera intent failed", e);
            return null;
        }
    }

    @Override
    protected void onActivityResult(int requestCode, int resultCode, Intent data) {
        if (requestCode != FILE_CHOOSER_REQUEST) {
            super.onActivityResult(requestCode, resultCode, data);
            return;
        }
        ValueCallback<Uri[]> callback = pendingFileCallback;
        pendingFileCallback = null;
        if (callback == null) {
            return;
        }

        // 情况一：用户走了「拍照」入口
        if (resultCode == RESULT_OK && data == null && pendingCameraUri != null) {
            callback.onReceiveValue(new Uri[]{pendingCameraUri});
            pendingCameraUri = null;
            return;
        }
        pendingCameraUri = null;

        // 情况二：用户取消
        if (resultCode != RESULT_OK || data == null) {
            callback.onReceiveValue(null);
            return;
        }

        // 情况三：用户从相册/文件选择器选了东西
        Uri[] result = WebChromeClient.FileChooserParams.parseResult(resultCode, data);
        if (result == null && data.getData() != null) {
            result = new Uri[]{data.getData()};
        }
        callback.onReceiveValue(result);
    }

    @Override
    protected void onSaveInstanceState(Bundle outState) {
        super.onSaveInstanceState(outState);
        web.saveState(outState);
    }

    @Override
    public boolean onKeyDown(int keyCode, KeyEvent event) {
        if (keyCode == KeyEvent.KEYCODE_BACK && web != null && web.canGoBack()) {
            web.goBack();
            return true;
        }
        return super.onKeyDown(keyCode, event);
    }
}
