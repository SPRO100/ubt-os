FROM python:3.12-slim

# Системные зависимости (git нужен для obsidian_git_sync)
RUN apt-get update && apt-get install -y \
    git curl ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Python зависимости
COPY deploy/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Исходный код + файловые конфиги вертикалей (fallback для VerticalLoader)
COPY ubt_os/ ./ubt_os/
COPY vertical_configs/ ./vertical_configs/

# Git config для obsidian sync
RUN git config --global user.email "agent@ubt-os.local" && \
    git config --global user.name "UBT OS Agent"

CMD ["python", "-m", "ubt_os.main"]
