package ai.courtdefense.standalone;

import android.content.Context;
import android.database.Cursor;
import android.net.Uri;
import android.provider.OpenableColumns;
import java.io.*;
import java.util.zip.*;

/** Read file content from URI, extract text from DOCX/TXT. */
public class FileHelper {

    /** Read all bytes from a content URI. */
    public static byte[] readBytes(Context ctx, Uri uri) throws IOException {
        try (InputStream is = ctx.getContentResolver().openInputStream(uri)) {
            ByteArrayOutputStream buf = new ByteArrayOutputStream();
            byte[] tmp = new byte[8192];
            int n;
            while ((n = is.read(tmp)) != -1) buf.write(tmp, 0, n);
            return buf.toByteArray();
        }
    }

    /** Get the display filename from a URI. */
    public static String getFilename(Context ctx, Uri uri) {
        String name = null;
        if ("content".equals(uri.getScheme())) {
            try (Cursor c = ctx.getContentResolver()
                    .query(uri, null, null, null, null)) {
                if (c != null && c.moveToFirst()) {
                    int idx = c.getColumnIndex(OpenableColumns.DISPLAY_NAME);
                    if (idx >= 0) name = c.getString(idx);
                }
            }
        }
        if (name == null) {
            name = uri.getLastPathSegment();
            if (name == null) name = "file";
        }
        return name;
    }

    /** Extract plain text from a .docx file (it's just a ZIP with XML). */
    public static String extractDocxText(byte[] docxBytes) {
        StringBuilder sb = new StringBuilder();
        try (ZipInputStream zis = new ZipInputStream(new ByteArrayInputStream(docxBytes))) {
            ZipEntry entry;
            while ((entry = zis.getNextEntry()) != null) {
                if ("word/document.xml".equals(entry.getName())) {
                    ByteArrayOutputStream buf = new ByteArrayOutputStream();
                    byte[] tmp = new byte[4096];
                    int n;
                    while ((n = zis.read(tmp)) != -1) buf.write(tmp, 0, n);
                    String xml = buf.toString("UTF-8");
                    // Strip XML tags, decode basic entities
                    String text = xml
                        .replaceAll("<w:p[ >][^>]*>|<w:p/>", "\n")
                        .replaceAll("<[^>]+>", "")
                        .replace("&amp;",  "&")
                        .replace("&lt;",   "<")
                        .replace("&gt;",   ">")
                        .replace("&quot;", "\"")
                        .replace("&apos;", "'")
                        .replaceAll("\n{3,}", "\n\n")
                        .trim();
                    sb.append(text);
                    break;
                }
            }
        } catch (Exception ignored) {}
        return sb.toString();
    }

    /** MIME type from filename extension. */
    public static String mimeFromName(String name) {
        String low = name.toLowerCase();
        if (low.endsWith(".mp3"))  return "audio/mpeg";
        if (low.endsWith(".m4a"))  return "audio/mp4";
        if (low.endsWith(".wav"))  return "audio/wav";
        if (low.endsWith(".flac")) return "audio/flac";
        if (low.endsWith(".ogg"))  return "audio/ogg";
        if (low.endsWith(".aac"))  return "audio/aac";
        if (low.endsWith(".wma"))  return "audio/x-ms-wma";
        if (low.endsWith(".pdf"))  return "application/pdf";
        if (low.endsWith(".docx")) return "application/vnd.openxmlformats-officedocument.wordprocessingml.document";
        if (low.endsWith(".txt"))  return "text/plain";
        return "application/octet-stream";
    }

    public static boolean isAudio(String name) {
        String low = name.toLowerCase();
        return low.endsWith(".mp3") || low.endsWith(".m4a") || low.endsWith(".wav")
            || low.endsWith(".flac") || low.endsWith(".ogg") || low.endsWith(".aac")
            || low.endsWith(".wma");
    }

    public static boolean isPdf(String name) {
        return name.toLowerCase().endsWith(".pdf");
    }

    public static boolean isDocx(String name) {
        return name.toLowerCase().endsWith(".docx");
    }

    public static boolean isTxt(String name) {
        return name.toLowerCase().endsWith(".txt");
    }
}
