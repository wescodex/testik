import logging
import os
from datetime import datetime

def setup_logger():
    # Создаем директорию для логов, если её нет
    if not os.path.exists('logs'):
        os.makedirs('logs')

    # Имя файла с текущей датой
    log_file = os.path.join('logs', 'bot_logs.txt')

    # Настройка форматирования
    formatter = logging.Formatter(
        fmt='%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # Хендлер для файла
    file_handler = logging.FileHandler(log_file, encoding='utf-8', mode='a')
    file_handler.setFormatter(formatter)

    # Хендлер для консоли
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)

    # Настройка корневого логгера
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    
    # Удаляем существующие хендлеры, если они есть
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
    
    # Добавляем новые хендлеры
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    return logger

# Создаем и настраиваем логгер при импорте модуля
logger = setup_logger()
