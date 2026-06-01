package ai.courtdefense.standalone;

import android.content.Context;
import android.net.Uri;
import android.view.*;
import android.widget.*;
import androidx.annotation.NonNull;
import androidx.recyclerview.widget.RecyclerView;
import java.util.List;

public class FileAdapter extends RecyclerView.Adapter<FileAdapter.VH> {

    private final List<Uri> uris;
    private final Context   ctx;

    public FileAdapter(Context ctx, List<Uri> uris) {
        this.ctx  = ctx;
        this.uris = uris;
    }

    @NonNull @Override
    public VH onCreateViewHolder(@NonNull ViewGroup parent, int viewType) {
        View v = LayoutInflater.from(parent.getContext())
                               .inflate(R.layout.item_file, parent, false);
        return new VH(v);
    }

    @Override
    public void onBindViewHolder(@NonNull VH h, int pos) {
        Uri    uri  = uris.get(pos);
        String name = FileHelper.getFilename(ctx, uri);

        String icon;
        if (FileHelper.isAudio(name))     icon = "🎵";
        else if (FileHelper.isPdf(name))  icon = "📄";
        else if (FileHelper.isDocx(name)) icon = "📝";
        else                              icon = "📃";

        h.icon.setText(icon);
        h.name.setText(name);
        h.remove.setOnClickListener(v -> {
            int p = h.getAdapterPosition();
            if (p != RecyclerView.NO_ID) {
                uris.remove(p);
                notifyItemRemoved(p);
            }
        });
    }

    @Override public int getItemCount() { return uris.size(); }

    static class VH extends RecyclerView.ViewHolder {
        TextView icon, name;
        ImageButton remove;
        VH(View v) {
            super(v);
            icon   = v.findViewById(R.id.file_icon);
            name   = v.findViewById(R.id.file_name);
            remove = v.findViewById(R.id.file_remove);
        }
    }
}
