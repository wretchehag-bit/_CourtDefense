package ai.courtdefense.app;

import android.annotation.SuppressLint;
import android.app.Activity;
import android.content.Intent;
import android.content.SharedPreferences;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.view.Menu;
import android.view.MenuItem;
import android.view.View;
import android.webkit.*;
import android.widget.ProgressBar;
import androidx.activity.result.ActivityResultLauncher;
import androidx.activity.result.contract.ActivityResultContracts;
import androidx.appcompat.app.AppCompatActivity;

public class MainActivity extends AppCompatActivity {

    private WebView webView;
    private ProgressBar progressBar;
    private ValueCallback<Uri[]> filePathCallback;
    private String serverUrl;

    private final ActivityResultLauncher<Intent> filePicker =
        registerForActivityResult(new ActivityResultContracts.StartActivityForResult(), result -> {
            if (filePathCallback == null) return;
            Uri[] results = null;
            if (result.getResultCode() == Activity.RESULT_OK && result.getData() != null) {
                results = WebChromeClient.FileChooserParams.parseResult(
                    result.getResultCode(), result.getData());
            }
            filePathCallback.onReceiveValue(results);
            filePathCallback = null;
        });

    @SuppressLint("SetJavaScriptEnabled")
    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_main);

        SharedPreferences prefs = getSharedPreferences("cd_prefs", MODE_PRIVATE);
        serverUrl = prefs.getString("server_url", "http://localhost:8000");

        progressBar = findViewById(R.id.progress_bar);
        webView = findViewById(R.id.webview);

        // WebView settings
        WebSettings ws = webView.getSettings();
        ws.setJavaScriptEnabled(true);
        ws.setDomStorageEnabled(true);
        ws.setAllowFileAccess(true);
        ws.setAllowContentAccess(true);
        ws.setLoadWithOverviewMode(true);
        ws.setUseWideViewPort(true);
        ws.setBuiltInZoomControls(true);
        ws.setDisplayZoomControls(false);
        ws.setCacheMode(WebSettings.LOAD_DEFAULT);
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            ws.setSafeBrowsingEnabled(false);
        }

        // File chooser (for audio/PDF uploads)
        webView.setWebChromeClient(new WebChromeClient() {
            @Override
            public boolean onShowFileChooser(WebView view,
                    ValueCallback<Uri[]> callback,
                    FileChooserParams params) {
                filePathCallback = callback;
                Intent intent = params.createIntent();
                intent.putExtra(Intent.EXTRA_ALLOW_MULTIPLE, true);
                try {
                    filePicker.launch(intent);
                } catch (Exception e) {
                    filePathCallback = null;
                    return false;
                }
                return true;
            }

            @Override
            public void onProgressChanged(WebView view, int newProgress) {
                progressBar.setProgress(newProgress);
                progressBar.setVisibility(newProgress == 100 ? View.GONE : View.VISIBLE);
            }
        });

        webView.setWebViewClient(new WebViewClient() {
            @Override
            public void onReceivedError(WebView view, WebResourceRequest request,
                    WebResourceError error) {
                if (request.isForMainFrame()) {
                    view.loadDataWithBaseURL(null, buildErrorPage(), "text/html", "utf-8", null);
                }
            }

            @Override
            public boolean shouldOverrideUrlLoading(WebView view, WebResourceRequest request) {
                // Keep all navigation inside the WebView
                return false;
            }
        });

        webView.loadUrl(serverUrl);
    }

    @Override
    public void onBackPressed() {
        if (webView != null && webView.canGoBack()) {
            webView.goBack();
        } else {
            super.onBackPressed();
        }
    }

    @Override
    public boolean onCreateOptionsMenu(Menu menu) {
        menu.add(0, 1, 0, "⟳  Reload");
        menu.add(0, 2, 0, "⚙  Change server");
        return true;
    }

    @Override
    public boolean onOptionsItemSelected(MenuItem item) {
        if (item.getItemId() == 1) {
            webView.reload();
            return true;
        }
        if (item.getItemId() == 2) {
            startActivity(new Intent(this, SetupActivity.class));
            return true;
        }
        return super.onOptionsItemSelected(item);
    }

    private String buildErrorPage() {
        return "<!DOCTYPE html><html><head>"
            + "<meta name='viewport' content='width=device-width,initial-scale=1'>"
            + "<style>"
            + "body{background:#0f1117;color:#e2e8f0;font-family:sans-serif;"
            + "display:flex;flex-direction:column;align-items:center;"
            + "justify-content:center;min-height:100vh;margin:0;padding:24px;text-align:center}"
            + "h2{color:#f59e0b;margin-bottom:16px}"
            + "p{color:#94a3b8;line-height:1.6;max-width:320px}"
            + "code{background:#1a1d27;padding:4px 8px;border-radius:4px;"
            + "color:#4f8ef7;font-size:13px;word-break:break-all}"
            + ".btn{display:inline-block;margin-top:24px;padding:12px 28px;"
            + "background:#4f8ef7;color:#fff;border:none;border-radius:8px;"
            + "font-size:15px;font-weight:600;cursor:pointer;text-decoration:none}"
            + ".hint{margin-top:32px;font-size:12px;color:#64748b}"
            + "</style></head><body>"
            + "<h2>⚠️ Server not reachable</h2>"
            + "<p>Could not connect to:<br><code>" + serverUrl + "</code></p>"
            + "<p>Make sure <b>CourtDefense.exe</b> is running on your PC "
            + "and both devices are on the same Wi-Fi network.</p>"
            + "<button class='btn' onclick='location.reload()'>Try again</button>"
            + "<p class='hint'>Tap ⋮ → Change server to update the address</p>"
            + "</body></html>";
    }
}
