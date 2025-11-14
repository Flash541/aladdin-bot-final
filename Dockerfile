# 1. Используем полный, не "slim", образ Python 3.12
FROM python:3.12

# 2. Устанавливаем рабочую директорию
WORKDIR /app

# 3. Обновляем список пакетов и устанавливаем системные зависимости
#    - build-essential: нужен для компиляции некоторых пакетов
#    - tesseract-ocr: сам движок OCR
#    - libgl1-mesa-glx: графическая библиотека для OpenCV
RUN apt-get update && \
    apt-get install -y \
    build-essential \
    tesseract-ocr \
    libgl1-mesa-glx --no-install-recommends && \
    rm -rf /var/lib/apt/lists/*

# 4. Копируем requirements.txt и устанавливаем Python-библиотеки
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 5. Копируем весь остальной код приложения
COPY . .

# 6. Команда по умолчанию для запуска
CMD ["python3", "bot.py"]
