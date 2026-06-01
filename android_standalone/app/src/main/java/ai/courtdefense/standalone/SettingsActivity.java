package ai.courtdefense.standalone;

import android.content.SharedPreferences;
import android.os.Bundle;
import android.widget.*;
import androidx.appcompat.app.AppCompatActivity;

public class SettingsActivity extends AppCompatActivity {

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_settings);

        if (getSupportActionBar() != null) {
            getSupportActionBar().setDisplayHomeAsUpEnabled(true);
            getSupportActionBar().setTitle("Settings");
        }

        SharedPreferences prefs = getSharedPreferences("cd_prefs", MODE_PRIVATE);

        EditText etAnthropic = findViewById(R.id.et_anthropic_key);
        EditText etOpenai    = findViewById(R.id.et_openai_key);
        Button   btnSave     = findViewById(R.id.btn_save);

        etAnthropic.setText(prefs.getString("anthropic_key", ""));
        etOpenai.setText(prefs.getString("openai_key", ""));

        btnSave.setOnClickListener(v -> {
            String ak = etAnthropic.getText().toString().trim();
            String ok = etOpenai.getText().toString().trim();
            prefs.edit()
                 .putString("anthropic_key", ak)
                 .putString("openai_key",    ok)
                 .apply();
            Toast.makeText(this, "Saved ✓", Toast.LENGTH_SHORT).show();
            finish();
        });
    }

    @Override
    public boolean onSupportNavigateUp() { finish(); return true; }
}
