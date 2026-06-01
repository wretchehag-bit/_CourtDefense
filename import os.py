import os
import glob
import zipfile
import tempfile
import shutil
from faster_whisper import WhisperModel

# 1. Автоопределение рабочих папок
current_dir = os.path.dirname(os.path.abspath(__file__))
if os.path.basename(current_dir) == "нарезки":
    folder = os.path.dirname(current_dir)
else:
    folder = current_dir

print(f"=== ИИ-Комбайн Судебной Стенограммы ===")
print(f"Сканирование директории: {folder}\n")

AUDIO_EXTENSIONS = ('.mp3', '.m4a', '.wav', '.flac', '.wma', '.ogg', '.aac')
all_items = []

# 2. Поиск обычных аудиофайлов
for ext in AUDIO_EXTENSIONS:
    for file_path in glob.glob(os.path.join(folder, f"*{ext}")) + glob.glob(os.path.join(folder, f"*{ext.upper()}")):
        if file_path not in [item['path'] for item in all_items if item['type'] == 'local']:
            all_items.append({
                'type': 'local',
                'name': os.path.basename(file_path),
                'path': file_path,
                'size': os.path.getsize(file_path)
            })

# 3. Поиск аудио внутри ZIP-архивов
zip_files = glob.glob(os.path.join(folder, "*.zip")) + glob.glob(os.path.join(folder, "*.ZIP"))
temp_dir_to_clean = None

for z_path in zip_files:
    try:
        with zipfile.ZipFile(z_path, 'r') as z_file:
            for z_info in z_file.infolist():
                if z_info.filename.lower().endswith(AUDIO_EXTENSIONS):
                    all_items.append({
                        'type': 'zip',
                        'name': f"📦 [{os.path.basename(z_path)}] -> {z_info.filename}",
                        'zip_path': z_path,
                        'internal_name': z_info.filename,
                        'size': z_info.file_size
                    })
    except Exception as e:
        print(f"⚠️ Ошибка чтения архива {os.path.basename(z_path)}: {e}")

if not all_items:
    print("❌ Аудиофайлы или ZIP-архивы не найдены!")
    exit()

# 4. Интерактивное меню выбора
print("Доступные медиа-файлы:")
for index, item in enumerate(all_items, start=1):
    print(f"[{index}] {item['name']} ({item['size'] / (1024*1024):.1f} MB)")
print("-" * 65)

while True:
    user_input = input(f"Выберите номер файла для обработки (1-{len(all_items)}): ").strip()
    if user_input.isdigit() and 1 <= int(user_input) <= len(all_items):
        selected_item = all_items[int(user_input) - 1]
        break
    print("❌ Неверный ввод.")

# Распаковка, если выбран файл из ZIP
if selected_item['type'] == 'zip':
    print("\n📦 Извлекаем файл из архива...")
    temp_dir_to_clean = tempfile.mkdtemp()
    with zipfile.ZipFile(selected_item['zip_path'], 'r') as z_file:
        input_path = z_file.extract(selected_item['internal_name'], temp_dir_to_clean)
else:
    input_path = selected_item['path']

base_name, ext = os.path.splitext(os.path.basename(input_path))
output_folder = os.path.join(current_dir, "готовые_нарезки")
os.makedirs(output_folder, exist_ok=True)

# 5. Инициализация ИИ-модели Whisper
print("\n🤖 Загрузка ИИ-модели Whisper 'medium'...")
print("Поскольку у вас мощная система, модель 'medium' обеспечит идеальный баланс")
print("между скоростью и распознаванием суржика/сложных фраз.")
# На вашей системе с RTX модель отработает очень быстро.
# Используем cpu/int8 для универсальности, при желании можно переключить на cuda.
model = WhisperModel("medium", device="cpu", compute_type="int8")

# 6. Нарезка на куски
print(f"\n🚀 Нарезаем аудио на 5 частей...")
with open(input_path, "rb") as f:
    data = f.read()

total_bytes = len(data)
parts = 5
chunk_size = total_bytes // parts

for i in range(parts):
    start_byte = i * chunk_size
    end_byte = (i + 1) * chunk_size if i < parts - 1 else total_bytes

    output_audio_name = f"part_{i+1}_chunk{ext.lower()}"
    output_audio_path = os.path.join(output_folder, output_audio_name)

    with open(output_audio_path, "wb") as out_f:
        out_f.write(data[start_byte:end_byte])
    print(f"\n[Часть {i+1}/{parts}] Создан аудиофайл: {output_audio_name}")

    # 7. Запуск транскрипции «слово в слово»
    print(f"       🎙️ ИИ начинает посекундное распознавание речи...")
    txt_output_name = f"part_{i+1}_transcript.txt"
    txt_output_path = os.path.join(output_folder, txt_output_name)

    # vad_filter=True убирает длинные паузы и тишину из стенограммы
    segments, info = model.transcribe(output_audio_path, beam_size=5, vad_filter=True)

    with open(txt_output_path, "w", encoding="utf-8") as txt_f:
        txt_f.write(f"=== СУДЕБНАЯ СТЕНОГРАММА ДЛЯ ЧАСТИ {i+1} ===\n")
        txt_f.write(f"Исходный файл фрагмента: {output_audio_name}\n")
        txt_f.write(f"Распознанный основной язык: {info.language.upper()} (вероятность: {info.language_probability:.2f})\n")
        txt_f.write("-" * 60 + "\n\n")

        for segment in segments:
            # Превращаем секунды в красивый тайм-код [ЧЧ:ММ:СС]
            start_time = f"{int(segment.start // 3600):02d}:{int((segment.start % 3600) // 60):02d}:{int(segment.start % 60):02d}"
            end_time = f"{int(segment.end // 3600):02d}:{int((segment.end % 3600) // 60):02d}:{int(segment.end % 60):02d}"

            # Пишем разборчивую строку
            line = f"[{start_time} -> {end_time}] Голос: {segment.text.strip()}\n"
            txt_f.write(line)
            # Дублируем в консоль, чтобы вы видели процесс в реальном времени
            print(f"       {line.strip()}")

    print(f"📄 Стенограмма сохранена в файл: {txt_output_name}")

# Уборка временных файлов
if temp_dir_to_clean and os.path.exists(temp_dir_to_clean):
    shutil.rmtree(temp_dir_to_clean)

print(f"\n🎉 ВСЕ ПРОЦЕССЫ УСПЕШНО ЗАВЕРШЕНЫ!")
print(f"📁 Нарезки звука и текстовые стенограммы лежат здесь: {output_folder}")
