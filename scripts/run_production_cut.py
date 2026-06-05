import sys
from pathlib import Path
# Імпортуємо модуль напряму
from court_defense.core import audio_cutter

# Додаємо src в шлях
sys.path.append(str(Path(__file__).parent.parent / "src"))

def run_production_cut():
    import os
    _default = Path(__file__).resolve().parents[1] / "case_data"
    target_dir = Path(os.environ.get("CASE_FOLDER", str(_default)))
    phrases_file = target_dir / "phrases.txt"

    print(f"🔍 Сканування папки: {target_dir}")

    # Викликаємо функцію нарізки напряму з модуля
    # У списку dir() я бачив функцію 'cut_audio_by_timestamps'
    # або, якщо є batch-процесинг, використовуй його:

    # Якщо в тебе немає функції batch_process_folder,
    # давай використаємо те, що є в dir():
    print("Використовуємо функцію: cut_audio_by_timestamps")

    # ... тут логіка виклику функції, яка відповідає за нарізку ...
    # Оскільки ти раніше згадував batch_process, перевір,
    # чи немає його в модулі (якщо немає — ми його допишемо)

if __name__ == "__main__":
    run_production_cut()
