# Multi-stage build для меньшего размера образа
FROM python:3.11-slim as builder

WORKDIR /app

# Устанавливаем зависимости для сборки
RUN pip install --no-cache-dir --upgrade pip setuptools wheel

# Копируем requirements и устанавливаем в виртуальное окружение
COPY requirements.txt .
RUN python -m venv /opt/venv && \
    /opt/venv/bin/pip install --no-cache-dir -r requirements.txt

# ===== Production stage =====
FROM python:3.11-slim

WORKDIR /app

# Создаём non-root пользователя
RUN groupadd -r botuser && useradd -r -g botuser botuser

# Копируем виртуальное окружение из builder stage
COPY --from=builder /opt/venv /opt/venv

# Копируем код приложения
COPY . .

# Меняем владельца файлов
RUN chown -R botuser:botuser /app

# Переключаемся на non-root пользователя
USER botuser

# Используем python из виртуального окружения
ENV PATH="/opt/venv/bin:$PATH"

# Healthcheck
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import sys; sys.exit(0)"

# Запуск бота
CMD ["python", "bot.py"]