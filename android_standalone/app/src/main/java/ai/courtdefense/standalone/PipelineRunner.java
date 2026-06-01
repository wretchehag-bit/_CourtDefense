package ai.courtdefense.standalone;

import android.content.Context;
import android.net.Uri;
import java.util.*;

/**
 * Core pipeline: files → transcribe/extract → Claude analysis → result text.
 * Runs on a background thread. Reports progress via Callback.
 */
public class PipelineRunner {

    public interface Callback {
        void onProgress(String message);
        void onDone(String result);
        void onError(String error);
    }

    private static final String SYSTEM_PROMPT =
        "Ти — досвідчений адвокат захисту з 15-річним стажем у судах України.\n" +
        "Тобі надані матеріали справи: аудіотранскрипції та/або документи.\n" +
        "Мова матеріалів — суміш українська + російська, аналізуй обидві.\n\n" +
        "Підготуй структурований пакет захисту:\n\n" +
        "=== 1. КЛАСИФІКАЦІЯ МАТЕРІАЛІВ ===\n" +
        "Для кожного аудіо/документа: СИЛЬНИЙ / ДОПОМІЖНИЙ / НЕЙТРАЛЬНИЙ / РИЗИКОВИЙ\n\n" +
        "=== 2. ЗАГАЛЬНА КАРТИНА СПРАВИ ===\n\n" +
        "=== 3. СИЛЬНІ ПОЗИЦІЇ ЗАХИСТУ ===\n" +
        "Конкретні факти та цитати що допомагають.\n\n" +
        "=== 4. СЛАБКІ МІСЦЯ / РИЗИКИ ===\n\n" +
        "=== 5. СТРАТЕГІЯ ЗАХИСТУ ===\n" +
        "Конкретний план дій.\n\n" +
        "=== 6. КЛЮЧОВІ АРГУМЕНТИ ===\n" +
        "Готові формулювання для виголошення.\n\n" +
        "=== 7. ПИТАННЯ ДО СВІДКІВ ===\n\n" +
        "=== 8. ШПАРГАЛКА ДО СУДУ ===\n" +
        "Одна сторінка найважливішого.";

    private final Context       ctx;
    private final List<Uri>     uris;
    private final String        anthropicKey;
    private final String        openaiKey;   // may be null/empty
    private final Callback      cb;

    public PipelineRunner(Context ctx, List<Uri> uris,
                          String anthropicKey, String openaiKey,
                          Callback cb) {
        this.ctx          = ctx;
        this.uris         = uris;
        this.anthropicKey = anthropicKey;
        this.openaiKey    = openaiKey;
        this.cb           = cb;
    }

    public void run() {
        new Thread(() -> {
            try {
                execute();
            } catch (Exception e) {
                cb.onError(e.getMessage() != null ? e.getMessage() : e.toString());
            }
        }).start();
    }

    private void execute() throws Exception {
        AnthropicClient claude  = new AnthropicClient(anthropicKey);
        WhisperClient   whisper = openaiKey != null && !openaiKey.isEmpty()
                                  ? new WhisperClient(openaiKey) : null;

        List<Map<String,Object>> contentBlocks = new ArrayList<>();
        List<String>             uploadedFileIds = new ArrayList<>();

        int total = uris.size();
        for (int i = 0; i < total; i++) {
            Uri    uri      = uris.get(i);
            String filename = FileHelper.getFilename(ctx, uri);
            cb.onProgress(String.format("[%d/%d] Обробляю: %s", i+1, total, filename));

            byte[] bytes = FileHelper.readBytes(ctx, uri);

            // ── Audio → Whisper ───────────────────────────────────────────
            if (FileHelper.isAudio(filename)) {
                if (whisper == null) {
                    cb.onProgress("  ⚠ OpenAI key не вказано — пропускаю аудіо: " + filename);
                    continue;
                }
                if (bytes.length > WhisperClient.MAX_BYTES) {
                    cb.onProgress("  ⚠ Файл > 25 MB — пропускаю: " + filename);
                    continue;
                }
                cb.onProgress("  Транскрибую через Whisper API…");
                String mime = FileHelper.mimeFromName(filename);
                String transcript = whisper.transcribe(bytes, filename, mime);
                cb.onProgress("  ✓ " + filename + ": " + transcript.length() + " символів");

                Map<String,Object> block = new HashMap<>();
                block.put("type", "text");
                block.put("text", "=== АУДІОЗАПИС: " + filename + " ===\n" + transcript);
                contentBlocks.add(block);
            }

            // ── PDF → Anthropic Files API (Claude читає напряму) ──────────
            else if (FileHelper.isPdf(filename)) {
                cb.onProgress("  Завантажую PDF у Anthropic Files API…");
                String fileId = claude.uploadPdf(bytes, filename);
                uploadedFileIds.add(fileId);
                cb.onProgress("  ✓ PDF прийнято: " + filename);

                Map<String,Object> block = new HashMap<>();
                block.put("type",    "pdf_file");
                block.put("file_id", fileId);
                contentBlocks.add(block);
            }

            // ── DOCX → extract XML text ───────────────────────────────────
            else if (FileHelper.isDocx(filename)) {
                cb.onProgress("  Читаю DOCX…");
                String text = FileHelper.extractDocxText(bytes);
                if (text.isEmpty()) {
                    cb.onProgress("  ⚠ Не вдалося витягнути текст з: " + filename);
                    continue;
                }
                cb.onProgress("  ✓ " + filename + ": " + text.length() + " символів");

                Map<String,Object> block = new HashMap<>();
                block.put("type", "text");
                block.put("text", "=== ДОКУМЕНТ: " + filename + " ===\n" + text);
                contentBlocks.add(block);
            }

            // ── TXT → plain text ──────────────────────────────────────────
            else if (FileHelper.isTxt(filename)) {
                String text = new String(bytes, "UTF-8");
                cb.onProgress("  ✓ TXT: " + filename + ": " + text.length() + " символів");

                Map<String,Object> block = new HashMap<>();
                block.put("type", "text");
                block.put("text", "=== ДОКУМЕНТ: " + filename + " ===\n" + text);
                contentBlocks.add(block);
            }
        }

        if (contentBlocks.isEmpty()) {
            cb.onError("Не вдалося обробити жоден файл. " +
                       (whisper == null ? "Для аудіо вкажи OpenAI API key." : "Перевір файли."));
            return;
        }

        cb.onProgress("\nНадсилаю " + contentBlocks.size() + " блок(ів) до Claude…");
        String result = claude.analyze(SYSTEM_PROMPT, contentBlocks);

        // Cleanup uploaded files from Anthropic servers
        for (String fid : uploadedFileIds) {
            claude.deleteFile(fid);
        }

        cb.onDone(result);
    }
}
