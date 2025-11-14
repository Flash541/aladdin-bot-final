# Используем официальный образ Python
FROM python:3.12-slim

# Устанавливаем рабочую директорию внутри контейнера
WORKDIR /app

# --- ГЛАВНЫЙ ШАГ: Устанавливаем Tesseract OCR ---
# Новый, исправленный код
RUN apt-get update && apt-get install -y \
    tesseract-ocr \
    libtesseract-dev \
    libgl1-mesa-glx \
    && rm -rf /var/lib/apt/lists/*

# Копируем файл с зависимостями Python
COPY requirements.txt .

# Устанавливаем Python-библиотеки
RUN pip install --no-cache-dir -r requirements.txt

# Копируем весь остальной код нашего приложения
COPY . .

# Команда для запуска будет взята из Procfile или настроек Render
CMD ["python3", "bot.py"]
