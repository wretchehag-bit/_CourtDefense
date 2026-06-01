import os
import glob
import shutil
import sys
import zipfile
import re
import tempfile  # Вот он, виновник сбоя!

# Автоопределение рабочих директорий
current_dir = os.path.dirname(os.path.abspath(__file__))
if os.path.basename(current_dir) == "нарезки":
    root_folder = os.path.dirname(current_dir)
else:
    root_folder = current_dir

ready_chunks_dir = os.path.join(current_dir, "готовые_нарезки")
target_main_dir = os.path.join(current_dir, "Отсортированные_данные_для_суда")
os.makedirs(target_main_dir, exist_ok=True)

print(f"=== Усиленный конвейер умной сортировки и архивации ===")
print(f"📁 Поиск исходников: {root_folder}")
print(f"📁 Поиск нарезок:    {ready_chunks_dir}")
print(f"🎯 Финальный архив:   {target_main_dir}")
print("-" * 70)

if not os.path.exists(ready_chunks_dir):
    print("❌ Папка 'готовые_нарезки' не найдена!")
    input("\nНажмите Enter для выхода...")
    sys.exit()

def clean_string(s):
    """Очищает строку для нечувствительного к спецсимволам сравнения."""
    return re.sub(r'[^a-zA-Z0-9а-яА-ЯёЁіІїЇєЄ]', '', s).lower()

def extract_date_prefix(s):
    """Ищет паттерн даты и времени вида 20260527_161146 в имени файла."""
    match = re.search(r'\d{8}_\d{6}', s)
    return match.group(0) if match else None

# 1. Индексируем абсолютно все файлы в корне папки
AUDIO_EXTENSIONS = ('.mp3', '.m4a', '.wav', '.flac', '.wma', '.ogg', '.aac')
all_local_files = []
for ext in AUDIO_EXTENSIONS + ('.zip',):
    for f_path in glob.glob(os.path.join(root_folder, f"*{ext}")) + glob.glob(os.path.join(root_folder, f"*{ext.upper()}")):
        all_local_files.append(os.path.abspath(f_path))

# 2. Получаем список обработанных папок в готовых нарезках
subfolders = [d for d in os.listdir(ready_chunks_dir) if os.path.isdir(os.path.join(ready_chunks_dir, d))]

print(f"🔍 Найдено наборов для проверки и глубокого анализа: {len(subfolders)}")
print("⏳ Наведение идеального порядка в файлах...")

for subfolder in subfolders:
    # Очищаем имя папки от таймстемпа нарезки (например, "15-30-22_имя")
    parts_name = subfolder.split("_", 1)
    if len(parts_name) > 1 and parts_name[0].replace("-", "").isdigit() and len(parts_name[0]) == 6:
        clean_name = parts_name[1]
    else:
        clean_name = subfolder

    print(f"\n📁 Анализ папки: {clean_name}")

    case_folder = os.path.join(target_main_dir, clean_name)
    chunks_dest_folder = os.path.join(case_folder, "папка_с_нарезками")
    transcripts_dest_folder = os.path.join(case_folder, "папка_с_транскрипцией")

    os.makedirs(case_folder, exist_ok=True)
    os.makedirs(chunks_dest_folder, exist_ok=True)
    os.makedirs(transcripts_dest_folder, exist_ok=True)

    # Стратегия умного поиска оригинала
    matched_source_path = None
    source_is_inside_zip = False
    zip_archive_path = None
    internal_file_name = None

    folder_date_prefix = extract_date_prefix(clean_name)
    clean_folder_target = clean_string(clean_name)

    # Ищем среди локальных файлов в корне
    for f_path in all_local_files:
        f_name = os.path.basename(f_path)
        file_base, file_ext = os.path.splitext(f_name)

        # Если это ZIP — заглядываем внутрь без распаковки
        if file_ext.lower() == '.zip':
            try:
                with zipfile.ZipFile(f_path, 'r') as z:
                    for z_info in z.infolist():
                        if z_info.filename.lower().endswith(AUDIO_EXTENSIONS):
                            z_base = os.path.splitext(os.path.basename(z_info.filename))[0]
                            z_date = extract_date_prefix(z_base)

                            # Проверяем совпадение внутри ZIP по дате или имени
                            if (z_date and folder_date_prefix and z_date == folder_date_prefix) or (clean_string(z_base) in clean_folder_target or clean_folder_target in clean_string(z_base)):
                                matched_source_path = f_path
                                source_is_inside_zip = True
                                zip_archive_path = f_path
                                internal_file_name = z_info.filename
                                break
            except Exception:
                pass
        else:
            # Сравнение обычных файлов по префиксу даты или схожести имен
            file_date = extract_date_prefix(file_base)
            if (file_date and folder_date_prefix and file_date == folder_date_prefix) or (clean_string(file_base) in clean_folder_target or clean_folder_target in clean_string(file_base)):
                matched_source_path = f_path
                break
        if matched_source_path:
            break

    # Копирование или извлечение оригинала
    dest_source_name = os.path.basename(internal_file_name if source_is_inside_zip else matched_source_path) if matched_source_path else ""
    dest_source_path = os.path.join(case_folder, dest_source_name) if dest_source_name else None

    if matched_source_path and dest_source_path and not os.path.exists(dest_source_path):
        if source_is_inside_zip:
            print(f"  📦 Извлекаем оригинал из архива {os.path.basename(zip_archive_path)} -> {dest_source_name}")
            try:
                with zipfile.ZipFile(zip_archive_path, 'r') as z:
                    # Извлекаем во временную директорию и перемещаем в дело
                    with tempfile.TemporaryDirectory() as tmpdir:
                        extracted_tmp = z.extract(internal_file_name, tmpdir)
                        shutil.move(extracted_tmp, dest_source_path)
            except Exception as e:
                print(f"  ❌ Ошибка извлечения из ZIP: {e}")
        else:
            print(f"  ➡️ Копируем локальный оригинал: {os.path.basename(matched_source_path)}")
            shutil.copy2(matched_source_path, dest_source_path)
    elif dest_source_path and os.path.exists(dest_source_path):
        print(f"  ℹ️ Оригинальный файл уже присутствует в досье.")
    else:
        print(f"  ⚠️ Исходный аудиофайл не найден (возможно, удален из корня).")

    # Перенос чанков и транскриптов
    subfolder_path = os.path.join(ready_chunks_dir, subfolder)
    for item in os.listdir(subfolder_path):
        item_path = os.path.join(subfolder_path, item)
        if os.path.isdir(item_path):
            continue

        if item.endswith('.txt'):
            dest_txt = os.path.join(transcripts_dest_folder, item)
            if not os.path.exists(dest_txt):
                shutil.copy2(item_path, dest_txt)
        elif item.lower().endswith(AUDIO_EXTENSIONS):
            dest_audio = os.path.join(chunks_dest_folder, item)
            if not os.path.exists(dest_audio):
                shutil.copy2(item_path, dest_audio)

    print(f"  ✅ Все связанные фрагменты и текстовые аудиты синхронизированы.")

print("\n============================================================")
print(f"🎉 Идеальный судебный архив полностью сформирован!")
print(f"📁 Путь к данным: {target_main_dir}")
print("============================================================")
input("\nНажмите Enter для завершения...")
