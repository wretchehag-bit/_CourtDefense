package ai.courtdefense.standalone;

import android.content.*;
import android.os.*;
import android.widget.*;
import androidx.appcompat.app.AppCompatActivity;
import java.io.*;
import java.text.SimpleDateFormat;
import java.util.*;

public class ResultActivity extends AppCompatActivity {

    private String resultText;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_result);

        if (getSupportActionBar() != null) {
            getSupportActionBar().setDisplayHomeAsUpEnabled(true);
            getSupportActionBar().setTitle("Analysis Result");
        }

        resultText = getIntent().getStringExtra("result");
        if (resultText == null) resultText = "";

        TextView tvResult = findViewById(R.id.tv_result);
        tvResult.setText(resultText);

        findViewById(R.id.btn_copy).setOnClickListener(v -> {
            ClipboardManager cm = (ClipboardManager) getSystemService(CLIPBOARD_SERVICE);
            cm.setPrimaryClip(ClipData.newPlainText("Court Defense Analysis", resultText));
            Toast.makeText(this, "Copied to clipboard", Toast.LENGTH_SHORT).show();
        });

        findViewById(R.id.btn_share).setOnClickListener(v -> {
            Intent share = new Intent(Intent.ACTION_SEND);
            share.setType("text/plain");
            share.putExtra(Intent.EXTRA_TEXT, resultText);
            share.putExtra(Intent.EXTRA_SUBJECT, "Court Defense Analysis");
            startActivity(Intent.createChooser(share, "Share via"));
        });

        findViewById(R.id.btn_save).setOnClickListener(v -> saveToFile());
    }

    private void saveToFile() {
        try {
            String ts   = new SimpleDateFormat("yyyyMMdd_HHmmss", Locale.US).format(new Date());
            File   dir  = new File(getExternalFilesDir(null), "CourtDefense");
            dir.mkdirs();
            File   file = new File(dir, "analysis_" + ts + ".txt");
            try (FileWriter fw = new FileWriter(file)) { fw.write(resultText); }
            Toast.makeText(this, "Saved: " + file.getAbsolutePath(), Toast.LENGTH_LONG).show();
        } catch (Exception e) {
            Toast.makeText(this, "Save failed: " + e.getMessage(), Toast.LENGTH_LONG).show();
        }
    }

    @Override public boolean onSupportNavigateUp() { finish(); return true; }
}
