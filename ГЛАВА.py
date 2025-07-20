import subprocess
import shutil
import time
import os
import re
import psutil

def is_process_running(process_name, script_path=None):
    """
    Проверяет, запущен ли процесс с указанным именем.
    Если указан script_path, дополнительно проверяет, запущен ли именно этот скрипт.
    """
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        if proc.info['name'] == process_name:
            if script_path:
                # Проверяем, содержит ли командная строка путь к искомому скрипту
                if proc.info['cmdline'] and any(script_path.lower() in arg.lower() for arg in proc.info['cmdline']):
                    return True, proc.pid
            else:
                return True, proc.pid
    return False, None

def terminate_process_by_pid(pid):
    """
    Завершает процесс по его PID.
    """
    try:
        process = psutil.Process(pid)
        process.terminate()
        print(f"Процесс с PID {pid} завершен.")
        return True
    except psutil.NoSuchProcess:
        print(f"Процесс с PID {pid} не найден.")
        return False
    except Exception as e:
        print(f"Ошибка при завершении процесса с PID {pid}: {e}")
        return False

def wait_for_files(folder_path, *file_patterns, timeout=3600):
    """
    Ожидает появления файлов, соответствующих заданным паттернам, в указанной папке.
    Возвращает список полных путей к найденным файлам в порядке заданных паттернов.
    Возвращает None для каждого паттерна, если файл не найден.
    """
    start_time = time.time()
    found_files = [None] * len(file_patterns)
    found_flags = [False] * len(file_patterns)

    print(f"Ожидание файлов ({', '.join(file_patterns)}) в папке: {folder_path}")

    while time.time() - start_time < timeout:
        current_files = []
        try:
            current_files = os.listdir(folder_path)
        except FileNotFoundError:
            print(f"Папка не найдена: {folder_path}. Ждем ее создания или появления файлов.")
            time.sleep(5)
            continue
        
        all_found = True
        for i, pattern in enumerate(file_patterns):
            if not found_flags[i]:
                for filename in current_files:
                    if re.fullmatch(pattern, filename):
                        found_files[i] = os.path.join(folder_path, filename)
                        found_flags[i] = True
                        print(f"  Найден файл: {filename}")
                        break
            if not found_flags[i]:
                all_found = False

        if all_found:
            print("Все ожидаемые файлы найдены.")
            return found_files
        
        time.sleep(5)  # Проверяем каждые 5 секунд
    
    print("Таймаут ожидания файлов истек. Не все файлы найдены.")
    return found_files # Вернуть то, что удалось найти

def wait_for_any_file_in_folder(folder_path, timeout=600, check_interval=5):
    """
    Ожидает появления хотя бы одного файла в указанной папке.
    Возвращает True, если файлы найдены, иначе False.
    """
    print(f"Ожидание появления любых файлов в папке: {folder_path}...")
    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            if any(os.path.isfile(os.path.join(folder_path, item)) for item in os.listdir(folder_path)):
                print(f"Файлы обнаружены в папке: {folder_path}")
                return True
        except FileNotFoundError:
            print(f"Папка не найдена: {folder_path}. Ждем ее создания или появления файлов.")
        time.sleep(check_interval)
    print(f"Таймаут ({timeout} сек) ожидания файлов в папке {folder_path} истек.")
    return False


def get_telegram_checker_folders(base_path, folder_name_pattern):
    """
    Возвращает список полных путей к папкам 'Telegram Checker [время]' в заданной директории.
    """
    folders = []
    try:
        for item in os.listdir(base_path):
            item_path = os.path.join(base_path, item)
            if os.path.isdir(item_path) and re.fullmatch(folder_name_pattern, item):
                folders.append(item_path)
    except Exception as e:
        print(f"Ошибка при получении списка папок Telegram Checker: {e}")
    return folders

def parse_folder_timestamp(folder_name):
    """
    Извлекает метку времени из имени папки 'Telegram Checker [ЧЧ.ММ.СС]'.
    Возвращает числовое значение времени (ЧЧММСС) или None, если не удалось распарсить.
    """
    match = re.search(r'\[(\d{2}\.\d{2}\.\d{2})\]', folder_name)
    if match:
        time_str = match.group(1)
        try:
            return int(time_str.replace('.', ''))
        except ValueError:
            return None
    return None

def find_latest_new_telegram_checker_folder(base_path, folder_name_pattern, initial_folders, timeout=1800): # Изменено на 30 минут
    """
    Ждет появления новой папки 'Telegram Checker [время]' и возвращает путь к самой последней из них.
    Сравнивает с initial_folders, чтобы найти только вновь созданные.
    """
    start_time = time.time()
    latest_new_folder = None
    latest_timestamp = -1

    print(f"Ожидание самой последней новой папки в: {base_path}")

    while time.time() - start_time < timeout:
        current_folders = get_telegram_checker_folders(base_path, folder_name_pattern)
        new_folders = [f for f in current_folders if f not in initial_folders]

        if new_folders:
            for folder_path in new_folders:
                folder_name = os.path.basename(folder_path)
                timestamp_value = parse_folder_timestamp(folder_name)
                
                if timestamp_value is not None:
                    if timestamp_value > latest_timestamp:
                        latest_timestamp = timestamp_value
                        latest_new_folder = folder_path
            
            if latest_new_folder:
                # Даем немного времени, чтобы убедиться, что папка перестала меняться (записи завершились)
                time.sleep(5) 
                if os.path.exists(latest_new_folder):
                    print(f"Найдена и подтверждена последняя новая папка: {os.path.basename(latest_new_folder)}")
                    return latest_new_folder
                else:
                     print(f"Найдена папка {os.path.basename(latest_new_folder)}, но она пока не подтверждена или отсутствует. Ждем.")
        
        time.sleep(5) 
    
    print("Таймаут ожидания последней новой папки истек.")
    return None


def find_and_move_work_chats(source_folder, destination_folder, filename_to_find="Work_Chats_Statistics.txt"):
    """
    Ищет и перемещает файлы filename_to_find из source_folder (и его подпапок)
    в destination_folder. Возвращает количество перемещенных файлов.
    """
    moved_count = 0
    print(f"Поиск и перемещение '{filename_to_find}' из '{source_folder}' и его подпапок в '{destination_folder}'...")
    try:
        # Убедимся, что папка назначения существует
        os.makedirs(destination_folder, exist_ok=True)

        for root, dirs, files in os.walk(source_folder):
            for file in files:
                if file == filename_to_find:
                    source_path = os.path.join(root, file)
                    destination_path = os.path.join(destination_folder, file)
                    
                    if os.path.exists(destination_path):
                        base, ext = os.path.splitext(file)
                        destination_path = os.path.join(destination_folder, f"{base}_{int(time.time())}{ext}")
                    
                    shutil.move(source_path, destination_path)
                    print(f"Файл '{file}' перемещен из '{root}' в '{destination_folder}'.")
                    moved_count += 1
        return moved_count
    except Exception as e:
        print(f"Ошибка при поиске/перемещении '{filename_to_find}': {e}")
        return 0

def clear_folder(folder_path):
    """
    Удаляет все файлы и подпапки из указанной папки.
    """
    print(f"Очистка папки: {folder_path}...")
    try:
        if not os.path.exists(folder_path):
            print(f"Папка '{folder_path}' не существует, пропуск очистки.")
            return True
            
        for item in os.listdir(folder_path):
            item_path = os.path.join(folder_path, item)
            if os.path.isfile(item_path):
                os.remove(item_path)
                print(f"  Удален файл: {item}")
            elif os.path.isdir(item_path):
                shutil.rmtree(item_path)
                print(f"  Удалена папка: {item}")
        print(f"Папка '{folder_path}' очищена.")
        return True
    except Exception as e:
        print(f"Ошибка при очистке папки '{folder_path}': {e}")
        return False

def move_all_files_from_folder(source_folder, destination_folder):
    """
    Перемещает (вырезает) все файлы из исходной папки в папку назначения.
    """
    print(f"Перемещение всех файлов из '{source_folder}' в '{destination_folder}'...")
    moved_count = 0
    try:
        # Убедимся, что папка назначения существует
        os.makedirs(destination_folder, exist_ok=True)
        
        if not os.path.exists(source_folder):
            print(f"Исходная папка '{source_folder}' не существует. Ничего не перемещено.")
            return 0

        for item in os.listdir(source_folder):
            source_path = os.path.join(source_folder, item)
            # Перемещаем только файлы, пропускаем подпапки (если они есть)
            if os.path.isfile(source_path):
                destination_path = os.path.join(destination_folder, item)
                
                # Добавляем временную метку, если файл с таким именем уже существует
                if os.path.exists(destination_path):
                    base, ext = os.path.splitext(item)
                    destination_path = os.path.join(destination_folder, f"{base}_{int(time.time())}{ext}")
                
                shutil.move(source_path, destination_path)
                print(f"  Перемещен файл: {item}")
                moved_count += 1
        print(f"Перемещено {moved_count} файлов из '{source_folder}'.")
        return moved_count
    except Exception as e:
        print(f"Ошибка при перемещении файлов из '{source_folder}': {e}")
        return 0

def move_all_items_from_folder(source_folder, destination_folder):
    """
    Перемещает (вырезает) все файлы и папки из исходной папки в папку назначения.
    """
    print(f"Перемещение всех элементов из '{source_folder}' в '{destination_folder}'...")
    moved_count = 0
    try:
        os.makedirs(destination_folder, exist_ok=True)
        
        if not os.path.exists(source_folder):
            print(f"Исходная папка '{source_folder}' не существует. Ничего не перемещено.")
            return 0

        for item in os.listdir(source_folder):
            source_path = os.path.join(source_folder, item)
            destination_path = os.path.join(destination_folder, item)

            # Добавляем временную метку, если элемент с таким именем уже существует
            if os.path.exists(destination_path):
                if os.path.isfile(source_path):
                    base, ext = os.path.splitext(item)
                    destination_path = os.path.join(destination_folder, f"{base}_{int(time.time())}{ext}")
                elif os.path.isdir(source_path):
                    destination_path = os.path.join(destination_folder, f"{item}_{int(time.time())}")
            
            shutil.move(source_path, destination_path)
            print(f"  Перемещен: {item}")
            moved_count += 1
        print(f"Перемещено {moved_count} элементов из '{source_folder}'.")
        return moved_count
    except Exception as e:
        print(f"Ошибка при перемещении элементов из '{source_folder}': {e}")
        return 0


# --- Основные пути и настройки ---
# Скрипты
TG_LINK_COLLECTOR_SCRIPT = r"C:\Софт\1TGlinkV1.0\Сбор ссылок на чаты OKSEARCH.py"
ONLINE_CHAT_CHECKER_EXE = r"C:\Софт\2Onlinechat_checker V1.0\Telegram Checker.exe"
FILTER_NOT_BOT_SCRIPT = r"C:\Софт\3FiltrTGV1.0\ФИЛЬТР НЕ БОТ.py"
REPEATED_LINKS_SCRIPT = r"C:\Софт\4POVTORЧЕК\повторные ссылки тг.py"
CHAT_COUNT_SCRIPT = r"C:\Софт\5ChekLinksHUM\Колич.чатов.py"

# Папки
TG_LINK_COLLECTOR_FOLDER = r"C:\Софт\1TGlinkV1.0"
ONLINE_CHAT_CHECKER_FOLDER = r"C:\Софт\2Onlinechat_checker V1.0"
READY_CHATS_FOLDER = r"C:\Софт\ГОТОВЫЕ ЧАТЫ"
UNPROCESSED_FOLDER_3 = r"C:\Софт\3FiltrTGV1.0\НЕ отработанные"
SUCCESS_FOLDER_3 = r"C:\Софт\3FiltrTGV1.0\УСПЕШНО"
READY_CHATS_NOT_FOLDER = r"C:\Софт\ГОТОВЫЕ ЧАТЫ\НЕ" 
UNPROCESSED_FOLDER_4 = r"C:\Софт\4POVTORЧЕК\НЕ отработанные"
RESULTS_FOLDER_4 = r"C:\Софт\4POVTORЧЕК\Результаты"
UNPROCESSED_FOLDER_5 = r"C:\Софт\5ChekLinksHUM\НЕ отработанные"
PACKED_CHATS_FOLDER_5 = r"C:\Софт\5ChekLinksHUM\Чаты по пачкам"
INCOMPLETE_CHATS_COLLECTING_FOLDER_5 = r"C:\Софт\5ChekLinksHUM\НЕ ПОЛНЫЕ СОБИРАЮТСЯ" # Новая папка
ARCHIVE_FOLDER = r"C:\Софт\1TGlinkV1.0\АРХИВ" 

# Паттерны для имен файлов и папок
# ГИБКИЙ КОД (найдет файлы как с (2), так и без)
PRIVATE_CHAT_FILE_PATTERN = r"[а-яА-ЯёЁa-zA-Z]+_(\d+)_приватных(?:\s\(\d+\))?\.txt"
PUBLIC_CHAT_FILE_PATTERN = r"[а-яА-ЯёЁa-zA-Z]+_(\d+)_публичных(?:\s\(\d+\))?\.txt"
TELEGRAM_CHECKER_FOLDER_PATTERN = r"Telegram Checker \[\d{2}\.\d{2}\.\d{2}\]"
WORK_CHATS_STATISTICS_FILE = "Work_Chats_Statistics.txt"

FILTER_PASSED_FILE = r"прошли\.txt"
FILTER_NOT_PASSED_FILE_PATTERN = r"не_прошли\d*\.txt" 
REPEATED_NO_DUPLICATES_FILE = r"прошли_без_дубликатов\.txt"
COLLECT_TXT_FILE_PATTERN = r"сбор\.txt" # Новый паттерн для сбор.txt

# --- Параметры ожидания ---
TIMEOUT_TELEGRAM_CHECKER_PROCESS = 7200 # 2 часа для Telegram Checker.exe
TIMEOUT_FOR_LATEST_FOLDER_DISCOVERY = 1800 # 30 минут для поиска новой папки Telegram Checker (изменено)
TIMEOUT_FILTER_FILES = 3600 # 1 час для ожидания файлов от ФИЛЬТР НЕ БОТ.py
TIMEOUT_REPEATED_PROCESS = 3600 # 1 час для повторные ссылки тг.py
TIMEOUT_CHAT_COUNT_PROCESS = 3600 # 1 час для Колич.чатов.py
TIMEOUT_ANY_FILES_IN_PACKED_CHATS = 600 # 10 минут для ожидания файлов в Чаты по пачкам
TIMEOUT_COLLECT_TXT_FILE = 600 # 10 минут для ожидания сбор.txt
PAUSE_BEFORE_EXE_LAUNCH = 10 # 10 секунд паузы перед запуском EXE


print("Запуск основного скрипта автоматизации...")

# 1. Запуск скрипта сбора ссылок в фоновом режиме (если еще не запущен)
tg_link_collector_pid = None
try:
    is_running, pid = is_process_running("python.exe", TG_LINK_COLLECTOR_SCRIPT)
    if not is_running:
        print(f"Шаг 1: Запуск скрипта '{TG_LINK_COLLECTOR_SCRIPT}' в фоновом режиме...")
        process = subprocess.Popen(['python', TG_LINK_COLLECTOR_SCRIPT], 
                                   creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP)
        tg_link_collector_pid = process.pid
        print(f"Скрипт запущен (PID: {tg_link_collector_pid}).")
    else:
        tg_link_collector_pid = pid
        print(f"Шаг 1: Python процесс '{TG_LINK_COLLECTOR_SCRIPT}' уже запущен (PID: {tg_link_collector_pid}).")
except Exception as e:
    print(f"Шаг 1: Ошибка при запуске '{TG_LINK_COLLECTOR_SCRIPT}': {e}")
    # Если скрипт не удалось запустить, и он не был запущен, то дальше нет смысла идти
    if tg_link_collector_pid is None:
        exit()


# 2. Ожидание файлов приватных и публичных чатов
print("\nШаг 2: Ожидание файлов приватных и публичных чатов...")
private_chats_file, public_chats_file = wait_for_files(ONLINE_CHAT_CHECKER_FOLDER, PRIVATE_CHAT_FILE_PATTERN, PUBLIC_CHAT_FILE_PATTERN)

if not private_chats_file or not public_chats_file:
    print("Шаг 2: Не удалось найти необходимые файлы приватных/публичных чатов. Скрипт завершает работу.")
    exit()

# После того как оба файла найдены, завершить C:\Софт\1TGlinkV1.0\Сбор ссылок на чаты OKSEARCH.py
if tg_link_collector_pid:
    print(f"Шаг 2: Файлы найдены, завершение процесса '{os.path.basename(TG_LINK_COLLECTOR_SCRIPT)}' (PID: {tg_link_collector_pid}).")
    terminate_process_by_pid(tg_link_collector_pid)
    time.sleep(5) # Даем время процессу на завершение


# 3. Перемещение файла приватных чатов в "ГОТОВЫЕ ЧАТЫ" (вырезание)
print("\nШаг 3: Перемещение файла приватных чатов (вырезание)...")
try:
    os.makedirs(READY_CHATS_FOLDER, exist_ok=True)
    destination_private_file = os.path.join(READY_CHATS_FOLDER, os.path.basename(private_chats_file))
    
    if os.path.exists(destination_private_file):
        base, ext = os.path.splitext(os.path.basename(private_chats_file))
        destination_private_file = os.path.join(READY_CHATS_FOLDER, f"{base}_{int(time.time())}{ext}")

    shutil.move(private_chats_file, destination_private_file)
    print(f"Файл '{os.path.basename(private_chats_file)}' перемещен в '{READY_CHATS_FOLDER}'.")
except Exception as e:
    print(f"Шаг 3: Ошибка при перемещении файла приватных чатов: {e}")
    exit() # Если не удалось переместить, дальше нет смысла


# --- Запоминаем текущие папки Telegram Checker до запуска EXE ---
print("\nСохранение снимка существующих папок 'Telegram Checker'...")
initial_telegram_checker_folders = set(get_telegram_checker_folders(ONLINE_CHAT_CHECKER_FOLDER, TELEGRAM_CHECKER_FOLDER_PATTERN))
print(f"Найдено {len(initial_telegram_checker_folders)} существующих папок 'Telegram Checker' до запуска EXE.")

# Добавленная пауза перед запуском EXE
print(f"\nПауза {PAUSE_BEFORE_EXE_LAUNCH} секунд перед запуском '{os.path.basename(ONLINE_CHAT_CHECKER_EXE)}'...")
time.sleep(PAUSE_BEFORE_EXE_LAUNCH)


# 4. Открытие Telegram Checker.exe от имени администратора и ожидание его завершения
telegram_checker_dir = os.path.dirname(ONLINE_CHAT_CHECKER_EXE)
telegram_checker_process = None

print(f"\nШаг 4: Запуск '{ONLINE_CHAT_CHECKER_EXE}' от имени администратора и ожидание его завершения...")
try:
    telegram_checker_process = subprocess.Popen(
        ['powershell', '-command', f'Start-Process -FilePath "{ONLINE_CHAT_CHECKER_EXE}" -WorkingDirectory "{telegram_checker_dir}" -Verb RunAs -Wait'],
        shell=True
    )
    print(f"Telegram Checker запущен (PID: {telegram_checker_process.pid}). Ожидание завершения...")
    telegram_checker_process.wait(timeout=TIMEOUT_TELEGRAM_CHECKER_PROCESS)
    print(f"Процесс '{os.path.basename(ONLINE_CHAT_CHECKER_EXE)}' завершил работу. Код выхода: {telegram_checker_process.returncode}")

except subprocess.TimeoutExpired:
    print(f"Шаг 4: Таймаут ({TIMEOUT_TELEGRAM_CHECKER_PROCESS} сек) ожидания завершения '{os.path.basename(ONLINE_CHAT_CHECKER_EXE)}' истек.")
    if telegram_checker_process and telegram_checker_process.poll() is None:
        print("Процесс все еще работает. Возможно, требуется ручное вмешательство. Завершение работы скрипта.")
    exit()
except Exception as e:
    print(f"Шаг 4: Ошибка при запуске '{ONLINE_CHAT_CHECKER_EXE}' или ожидании его завершения: {e}")
    exit()

# 5. Найти последнюю созданную папку Telegram Checker [время]
print("\nШаг 5: Поиск самой последней новой папки 'Telegram Checker [время]'...")
current_telegram_checker_folder = find_latest_new_telegram_checker_folder(
    ONLINE_CHAT_CHECKER_FOLDER, 
    TELEGRAM_CHECKER_FOLDER_PATTERN, 
    initial_telegram_checker_folders,
    timeout=TIMEOUT_FOR_LATEST_FOLDER_DISCOVERY 
)

if not current_telegram_checker_folder:
    print(f"Шаг 5: Ошибка: Не удалось найти самую последнюю новую папку 'Telegram Checker [время]' после завершения работы EXE. Завершение работы скрипта.")
    exit()

print(f"Найдена последняя новая папка: '{os.path.basename(current_telegram_checker_folder)}'.")

# 6. Поиск и перемещение Work_Chats_Statistics.txt и безусловное удаление папки Telegram Checker [время]
print("\nШаг 6: Поиск и перемещение 'Work_Chats_Statistics.txt' (вырезание) и удаление папки 'Telegram Checker [время]'...")
total_moved_work_chats = find_and_move_work_chats(current_telegram_checker_folder, UNPROCESSED_FOLDER_3, WORK_CHATS_STATISTICS_FILE)

if total_moved_work_chats == 0:
    print(f"Шаг 6: Внимание: Файлы '{WORK_CHATS_STATISTICS_FILE}' не были найдены и перемещены из '{os.path.basename(current_telegram_checker_folder)}'. Скрипт завершает работу.")
    exit()
else:
    print(f"Шаг 6: Успешно перемещено '{total_moved_work_chats}' файлов '{WORK_CHATS_STATISTICS_FILE}'.")
    # Безусловное удаление папки Telegram Checker [время]
    try:
        if os.path.exists(current_telegram_checker_folder):
            shutil.rmtree(current_telegram_checker_folder)
            print(f"Папка '{os.path.basename(current_telegram_checker_folder)}' удалена.")
        else:
            print(f"Папка '{os.path.basename(current_telegram_checker_folder)}' уже отсутствует.")
    except Exception as e:
        print(f"Ошибка при попытке удалить папку '{os.path.basename(current_telegram_checker_folder)}': {e}")


# --- НОВЫЕ ШАГИ АВТОМАТИЗАЦИИ ---

# 7. Запуск ФИЛЬТР НЕ БОТ.py в фоновом режиме и ожидание файлов
filter_not_bot_pid = None
print(f"\nШаг 7: Запуск '{FILTER_NOT_BOT_SCRIPT}' в фоновом режиме и ожидание файлов 'прошли.txt' и 'не_прошли*.txt'...")
try:
    process = subprocess.Popen(
        ['python', FILTER_NOT_BOT_SCRIPT], 
        creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
    )
    filter_not_bot_pid = process.pid
    print(f"Скрипт '{os.path.basename(FILTER_NOT_BOT_SCRIPT)}' запущен в фоновом режиме (PID: {filter_not_bot_pid}).")
except Exception as e:
    print(f"Шаг 7: Ошибка при запуске '{FILTER_NOT_BOT_SCRIPT}': {e}")
    exit()

# Ожидание файлов от ФИЛЬТР НЕ БОТ.py
print(f"Шаг 7: Ожидание файлов в '{SUCCESS_FOLDER_3}'...")
found_filter_files = wait_for_files(SUCCESS_FOLDER_3, FILTER_PASSED_FILE, FILTER_NOT_PASSED_FILE_PATTERN, timeout=TIMEOUT_FILTER_FILES)
passed_file = found_filter_files[0]
not_passed_file = found_filter_files[1]

if not passed_file or not not_passed_file:
    print("Шаг 7: Не удалось найти один или оба файла от ФИЛЬТР НЕ БОТ.py. Скрипт завершает работу.")
    exit()


# 8. Перемещение файлов прошли.txt и не_прошли*.txt
print("\nШаг 8: Перемещение файлов 'прошли.txt' и 'не_прошли*.txt'...")
try:
    if passed_file:
        os.makedirs(UNPROCESSED_FOLDER_4, exist_ok=True) 
        shutil.move(passed_file, os.path.join(UNPROCESSED_FOLDER_4, os.path.basename(passed_file)))
        print(f"Файл '{os.path.basename(passed_file)}' перемещен в '{UNPROCESSED_FOLDER_4}'.")
    if not_passed_file:
        # Создание папки, если ее нет
        os.makedirs(READY_CHATS_NOT_FOLDER, exist_ok=True) 
        shutil.move(not_passed_file, os.path.join(READY_CHATS_NOT_FOLDER, os.path.basename(not_passed_file)))
        print(f"Файл '{os.path.basename(not_passed_file)}' перемещен в '{READY_CHATS_NOT_FOLDER}'.")
except Exception as e:
    print(f"Шаг 8: Ошибка при перемещении файлов прошли/не_прошли: {e}")
    exit()


# Шаг 9: Очистка папки C:\Софт\3FiltrTGV1.0\УСПЕШНО
print("\nШаг 9: Очистка папки 'УСПЕШНО' (3FiltrTGV1.0)...")
if not clear_folder(SUCCESS_FOLDER_3):
    print("Шаг 9: Не удалось полностью очистить папку 'УСПЕШНО'. Возможно, остались файлы.")

# 9.1. Очистка папки C:\Софт\3FiltrTGV1.0\НЕ отработанные
print("\nШаг 9.1: Очистка папки 'НЕ отработанные' (3FiltrTGV1.0)...")
if not clear_folder(UNPROCESSED_FOLDER_3):
    print("Шаг 9.1: Не удалось полностью очистить папку 'НЕ отработанные' (3FiltrTGV1.0). Возможно, остались файлы.")


# 10. Запуск повторные ссылки тг.py в фоновом режиме
repeated_links_pid = None
print(f"\nШаг 10: Запуск '{REPEATED_LINKS_SCRIPT}' в фоновом режиме...")
try:
    process = subprocess.Popen(
        ['python', REPEATED_LINKS_SCRIPT], 
        creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
    )
    repeated_links_pid = process.pid
    print(f"Скрипт '{os.path.basename(REPEATED_LINKS_SCRIPT)}' запущен в фоновом режиме (PID: {repeated_links_pid}).")
    print(f"Основной скрипт продолжит работу, не дожидаясь завершения '{os.path.basename(REPEATED_LINKS_SCRIPT)}'.")
except Exception as e:
    print(f"Шаг 10: Ошибка при запуске '{REPEATED_LINKS_SCRIPT}': {e}")
    exit()


# 11. Поиск и перемещение прошли_без_дубликатов.txt
print("\nШаг 11: Поиск и перемещение 'прошли_без_дубликатов.txt' (вырезание)...")
time.sleep(5) # Изменено на 5 секунд
found_no_duplicates_file_list = wait_for_files(RESULTS_FOLDER_4, REPEATED_NO_DUPLICATES_FILE, timeout=600) 
no_duplicates_file = found_no_duplicates_file_list[0]

if not no_duplicates_file:
    print("Шаг 11: Не удалось найти файл 'прошли_без_дубликатов.txt'. Скрипт завершает работу.")
    exit()

try:
    os.makedirs(UNPROCESSED_FOLDER_5, exist_ok=True) 
    shutil.move(no_duplicates_file, os.path.join(UNPROCESSED_FOLDER_5, os.path.basename(no_duplicates_file)))
    print(f"Файл '{os.path.basename(no_duplicates_file)}' перемещен в '{UNPROCESSED_FOLDER_5}'.")
except Exception as e:
    print(f"Шаг 11: Ошибка при перемещении 'прошли_без_дубликатов.txt': {e}")
    exit()


# 12. Очистка папок C:\Софт\4POVTORЧЕК\Результаты и C:\Софт\4POVTORЧЕК\НЕ отработанные
print("\nШаг 12: Очистка папок 'Результаты' (4POVTORЧЕК) и 'НЕ отработанные' (4POVTORЧЕК)...")
if not clear_folder(RESULTS_FOLDER_4):
    print("Шаг 12: Не удалось полностью очистить папку 'Результаты' (4POVTORЧЕК).")
if not clear_folder(UNPROCESSED_FOLDER_4):
    print("Шаг 12: Не удалось полностью очистить папку 'НЕ отработанные' (4POVTORЧЕК).")


# 13. Запуск Колич.чатов.py в фоновом режиме
chat_count_pid = None
print(f"\nШаг 13: Запуск '{CHAT_COUNT_SCRIPT}' в фоновом режиме...")
try:
    process = subprocess.Popen(
        ['python', CHAT_COUNT_SCRIPT], 
        creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
    )
    chat_count_pid = process.pid
    print(f"Скрипт '{os.path.basename(CHAT_COUNT_SCRIPT)}' запущен в фоновом режиме (PID: {chat_count_pid}).")
    print(f"Основной скрипт продолжит работу, не дожидаясь завершения '{os.path.basename(CHAT_COUNT_SCRIPT)}'.")
except Exception as e:
    print(f"Шаг 13: Ошибка при запуске '{CHAT_COUNT_SCRIPT}': {e}")
    exit()

# Дополнительный шаг: Ожидание появления файлов в PACKED_CHATS_FOLDER_5
print(f"\nОжидание файлов в '{PACKED_CHATS_FOLDER_5}' от скрипта '{os.path.basename(CHAT_COUNT_SCRIPT)}'...")
time.sleep(5) 
if not wait_for_any_file_in_folder(PACKED_CHATS_FOLDER_5, timeout=TIMEOUT_ANY_FILES_IN_PACKED_CHATS):
    print(f"Шаг 13/14: Не удалось обнаружить файлы в '{PACKED_CHATS_FOLDER_5}' после запуска '{os.path.basename(CHAT_COUNT_SCRIPT)}'. Возможно, скрипт не создал их или таймаут истек. Завершение работы.")
    exit()


# 14. Перемещение (вырезание) всех файлов из C:\Софт\5ChekLinksHUM\Чаты по пачкам в C:\Софт\ГОТОВЫЕ ЧАТЫ
print("\nШаг 14: Перемещение всех файлов из 'Чаты по пачкам' (5ChekLinksHUM) в 'ГОТОВЫЕ ЧАТЫ' (вырезание)...")
moved_final_chats = move_all_files_from_folder(PACKED_CHATS_FOLDER_5, READY_CHATS_FOLDER)

if moved_final_chats == 0:
    print("Шаг 14: Не удалось переместить файлы из 'Чаты по пачкам'.")
else:
    print(f"Шаг 14: Успешно перемещено {moved_final_chats} файлов в 'ГОТОВЫЕ ЧАТЫ'.")

# 14.1. Очистка папки C:\Софт\5ChekLinksHUM\НЕ отработанные
print("\nШаг 14.1: Очистка папки 'НЕ отработанные' (5ChekLinksHUM)...")
if not clear_folder(UNPROCESSED_FOLDER_5):
    print("Шаг 14.1: Не удалось полностью очистить папку 'НЕ отработанные' (5ChekLinksHUM). Возможно, остались файлы.")

# Шаг 14.2: Ожидание сбор.txt и перемещение файлов из C:\Софт\5ChekLinksHUM\НЕ ПОЛНЫЕ СОБИРАЮТСЯ
print(f"\nШаг 14.2: Ожидание '{COLLECT_TXT_FILE_PATTERN}' и перемещение файлов из '{INCOMPLETE_CHATS_COLLECTING_FOLDER_5}' в '{READY_CHATS_NOT_FOLDER}' (вырезание)...")
found_collect_file_list = wait_for_files(INCOMPLETE_CHATS_COLLECTING_FOLDER_5, COLLECT_TXT_FILE_PATTERN, timeout=TIMEOUT_COLLECT_TXT_FILE)
collect_txt_file = found_collect_file_list[0] if found_collect_file_list else None

if not collect_txt_file:
    print(f"  Внимание: Файл '{COLLECT_TXT_FILE_PATTERN}' не был найден в '{INCOMPLETE_CHATS_COLLECTING_FOLDER_5}'.")
else:
    print(f"  Файл '{COLLECT_TXT_FILE_PATTERN}' найден. Продолжаем перемещение.")

moved_incomplete_chats = move_all_files_from_folder(INCOMPLETE_CHATS_COLLECTING_FOLDER_5, READY_CHATS_NOT_FOLDER)
if moved_incomplete_chats == 0:
    print(f"  Внимание: Не удалось переместить файлы из '{INCOMPLETE_CHATS_COLLECTING_FOLDER_5}'.")
else:
    print(f"  Успешно перемещено {moved_incomplete_chats} файлов из '{INCOMPLETE_CHATS_COLLECTING_FOLDER_5}' в '{READY_CHATS_NOT_FOLDER}'.")


# 15. Удаление исходных файлов приватных и публичных чатов (перенесено сюда, в самый конец)
if total_moved_work_chats > 0: 
    print("\nШаг 15: Удаление исходных файлов приватных и публичных чатов...")
    try:
        # Проверяем, что файлы действительно существуют перед удалением
        if os.path.exists(private_chats_file):
            os.remove(private_chats_file)
            print(f"Файл '{os.path.basename(private_chats_file)}' удален из '{ONLINE_CHAT_CHECKER_FOLDER}'.")
        else:
            print(f"Файл '{os.path.basename(private_chats_file)}' уже отсутствует.")

        if os.path.exists(public_chats_file):
            os.remove(public_chats_file)
            print(f"Файл '{os.path.basename(public_chats_file)}' удален из '{ONLINE_CHAT_CHECKER_FOLDER}'.")
        else:
            print(f"Файл '{os.path.basename(public_chats_file)}' уже отсутствует.")

    except Exception as e:
        print(f"Шаг 15: Ошибка при удалении исходных файлов приватных/публичных чатов: {e}")
else:
    print(f"\nШаг 15: Файлы '{os.path.basename(private_chats_file)}' и '{os.path.basename(public_chats_file)}' НЕ БЫЛИ УДАЛЕНЫ, так как '{WORK_CHATS_STATISTICS_FILE}' не были найдены и перемещены ранее.")

# 16. Перемещение всех файлов из C:\Софт\ГОТОВЫЕ ЧАТЫ в архивную папку
print("\nШаг 16: Архивирование файлов из 'ГОТОВЫЕ ЧАТЫ'...")
archive_folder_name = "НЕИЗВЕСТНО" # Значение по умолчанию

# Поиск файла "приватных чатов" для имени архивной папки
found_private_chat_in_ready_chats = False
for item in os.listdir(READY_CHATS_FOLDER):
    if re.fullmatch(PRIVATE_CHAT_FILE_PATTERN, item):
        match = re.match(r"([а-яА-ЯёЁa-zA-Z]+)_", item)
        if match:
            archive_folder_name = match.group(1)
            found_private_chat_in_ready_chats = True
            break
if not found_private_chat_in_ready_chats:
    print(f"Предупреждение: Не удалось найти файл '{PRIVATE_CHAT_FILE_PATTERN}' в '{READY_CHATS_FOLDER}' для определения имени архивной папки. Будет использовано '{archive_folder_name}'.")

final_archive_path = os.path.join(ARCHIVE_FOLDER, archive_folder_name)
os.makedirs(final_archive_path, exist_ok=True)
print(f"Создана/проверена архивная папка: '{final_archive_path}'.")

moved_to_archive_count = move_all_items_from_folder(READY_CHATS_FOLDER, final_archive_path)

if moved_to_archive_count == 0:
    print("Шаг 16: Не удалось переместить файлы из 'ГОТОВЫЕ ЧАТЫ' в архив.")
else:
    print(f"Шаг 16: Успешно перемещено {moved_to_archive_count} элементов в '{final_archive_path}'.")
    # Дополнительно, если папка READY_CHATS_FOLDER стала пустой, ее можно удалить
    try:
        if not os.listdir(READY_CHATS_FOLDER):
            os.rmdir(READY_CHATS_FOLDER)
            print(f"Пустая папка '{READY_CHATS_FOLDER}' удалена.")
    except OSError as e:
        print(f"Ошибка при попытке удалить пустую папку '{READY_CHATS_FOLDER}': {e}")

print("\nСкрипт полностью завершил работу.")