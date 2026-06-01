package ai.courtdefense.standalone;

import android.content.Intent;
import android.content.SharedPreferences;
import android.net.Uri;
import android.os.*;
import android.view.Menu;
import android.view.MenuItem;
import android.view.View;
import android.widget.*;
import androidx.activity.result.*;
import androidx.activity.result.contract.*;
import androidx.appcompat.app.AppCompatActivity;
import androidx.recyclerview.widget.LinearLayoutManager;
import androidx.recyclerview.widget.RecyclerView;
import java.util.ArrayList;
import java.util.List;

public class MainActivity extends AppCompatActivity {

    private final List<Uri> selectedUris = new ArrayList<>();
    private FileAdapter     adapter;
    private Button          btnAnalyze;
    private TextView        tvStatus;
    private ProgressBar     progressBar;
    private ScrollView      logScroll;
    private TextView        tvLog;
    private Handler         uiHandler;

    private final ActivityResultLauncher<Intent> filePicker =
        registerForActivityResult(new ActivityResultContracts.StartActivityForResult(), result -> {
            if (result.getResultCode() == RESULT_OK && result.getData() != null) {
                Intent data = result.getData();
                if (data.getClipData() != null) {
                    int count = data.getClipData().getItemCount();
                    for (int i = 0; i < count; i++) {
                        selectedUris.add(data.getClipData().getItemAt(i).getUri());
                    }
                } else if (data.getData() != null) {
                    selectedUris.add(data.getData());
                }
                adapter.notifyDataSetChanged();
                updateAnalyzeButton();
            }
        });

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_main);
        uiHandler = new Handler(Looper.getMainLooper());

        RecyclerView rv = findViewById(R.id.rv_files);
        adapter = new FileAdapter(this, selectedUris);
        rv.setLayoutManager(new LinearLayoutManager(this));
        rv.setAdapter(adapter);

        btnAnalyze  = findViewById(R.id.btn_analyze);
        tvStatus    = findViewById(R.id.tv_status);
        progressBar = findViewById(R.id.progress_bar);
        logScroll   = findViewById(R.id.log_scroll);
        tvLog       = findViewById(R.id.tv_log);

        findViewById(R.id.btn_add_files).setOnClickListener(v -> pickFiles());
        btnAnalyze.setOnClickListener(v -> startAnalysis());
        updateAnalyzeButton();
    }

    public void onSettingsClick(android.view.View v) {
        startActivity(new Intent(this, SettingsActivity.class));
    }

    @Override
    public boolean onCreateOptionsMenu(Menu menu) {
        getMenuInflater().inflate(R.menu.main_menu, menu);
        return true;
    }

    @Override
    public boolean onOptionsItemSelected(MenuItem item) {
        if (item.getItemId() == R.id.action_settings) {
            startActivity(new Intent(this, SettingsActivity.class));
            return true;
        }
        return super.onOptionsItemSelected(item);
    }

    private void pickFiles() {
        Intent intent = new Intent(Intent.ACTION_GET_CONTENT);
        intent.setType("*/*");
        intent.putExtra(Intent.EXTRA_ALLOW_MULTIPLE, true);
        intent.putExtra(Intent.EXTRA_MIME_TYPES, new String[]{
            "audio/*", "application/pdf",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "text/plain"
        });
        filePicker.launch(Intent.createChooser(intent, "Select files"));
    }

    private void updateAnalyzeButton() {
        btnAnalyze.setEnabled(!selectedUris.isEmpty());
        tvStatus.setText(selectedUris.isEmpty()
            ? "Add audio or documents to begin"
            : selectedUris.size() + " file(s) selected");
    }

    private void startAnalysis() {
        SharedPreferences prefs = getSharedPreferences("cd_prefs", MODE_PRIVATE);
        String anthropicKey = prefs.getString("anthropic_key", "").trim();
        String openaiKey    = prefs.getString("openai_key",    "").trim();

        if (anthropicKey.isEmpty()) {
            Toast.makeText(this, "Set Anthropic API key in Settings ⚙", Toast.LENGTH_LONG).show();
            startActivity(new Intent(this, SettingsActivity.class));
            return;
        }

        setUiRunning(true);
        tvLog.setText("");
        logScroll.setVisibility(View.VISIBLE);

        List<Uri> urisCopy = new ArrayList<>(selectedUris);

        new PipelineRunner(this, urisCopy, anthropicKey,
                openaiKey.isEmpty() ? null : openaiKey,
                new PipelineRunner.Callback() {
                    @Override public void onProgress(String msg) {
                        uiHandler.post(() -> appendLog(msg));
                    }
                    @Override public void onDone(String result) {
                        uiHandler.post(() -> {
                            setUiRunning(false);
                            appendLog("✅ Аналіз завершено!");
                            Intent intent = new Intent(MainActivity.this, ResultActivity.class);
                            intent.putExtra("result", result);
                            startActivity(intent);
                        });
                    }
                    @Override public void onError(String error) {
                        uiHandler.post(() -> {
                            setUiRunning(false);
                            appendLog("❌ Помилка: " + error);
                            Toast.makeText(MainActivity.this, error, Toast.LENGTH_LONG).show();
                        });
                    }
                }).run();
    }

    private void appendLog(String line) {
        tvLog.append(line + "\n");
        logScroll.post(() -> logScroll.fullScroll(View.FOCUS_DOWN));
    }

    private void setUiRunning(boolean running) {
        btnAnalyze.setEnabled(!running);
        progressBar.setVisibility(running ? View.VISIBLE : View.GONE);
        tvStatus.setText(running ? "Аналіз виконується…" : selectedUris.size() + " file(s) selected");
        findViewById(R.id.btn_add_files).setEnabled(!running);
    }
}
