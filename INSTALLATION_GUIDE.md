# 🚀 Massage Bot - VPS Installation Guide

Полное руководство по развёртыванию Massage Bot на Linux VPS с помощью интерактивного install скрипта.

## 📋 Требования

- **ОС**: Ubuntu 20.04+ или Debian 10+
- **Привилегии**: root доступ (или sudo)
- **Интернет**: Требуется для скачивания Docker образов и npm пакетов
- **Место на диске**: Минимум 5GB свободного места

## 🔧 Что будет установлено

- Docker & Docker Compose
- Git (если отсутствует)
- Massage Bot приложение
- Redis (опционально, для хранения сессий)
- Systemd сервис для автозапуска

## 📥 Быстрая установка (3 команды)

```bash
# 1. Скачиваем install скрипт
curl -fsSL https://raw.githubusercontent.com/nxksxd/massage_bot/main/scripts/install_vps.sh -o install_vps.sh

# 2. Даём права на исполнение
chmod +x install_vps.sh

# 3. Запускаем установку
sudo ./install_vps.sh
```

Или клонируем весь репозиторий:

```bash
git clone https://github.com/nxksxd/massage_bot.git
cd massage_bot
sudo scripts/install_vps.sh
```

## 📝 Интерактивная конфигурация

При запуске скрипт запросит следующую информацию:

### 1️⃣ Параметры Telegram Bot

```
Введите BOT_TOKEN (от @BotFather): 123456789:ABCDEfghIjklmnOpQrStUvWxYz
Введите MASSEUR_ID (Telegram ID администратора) []: 987654321
```

**Где получить:**
- **BOT_TOKEN**: Напишите `/newbot` в Telegram чату с [@BotFather](https://t.me/BotFather)
- **MASSEUR_ID**: Напишите что угодно чату с [@userinfobot](https://t.me/userinfobot), получите свой ID

### 2️⃣ Параметры Google Sheets

```
Введите SPREADSHEET_ID (из ссылки Google Sheet) []: 1AbCdEfGhIjKlMnOpQrStUvWxYzAbCdEfGhIj
Введите имя листа в Google Sheets [Записи]: Записи
```

**Где найти SPREADSHEET_ID:**
- Откройте Google Sheet в браузере
- URL выглядит так: `https://docs.google.com/spreadsheets/d/**1AbCdEfGhIjKlMnOpQrStUvWxYzAbCdEfGhIj**/edit`
- Скопируйте часть между `/d/` и `/edit`

### 3️⃣ Google Service Account Credentials

```
Вам нужен JSON ключ от Google Service Account для доступа к Google Sheets
Инструкция: https://cloud.google.com/docs/authentication/getting-started

У вас уже есть credentials.json файл? (y/n) [y]: y
Введите путь к credentials.json: /home/user/credentials.json
```

**Как создать Service Account:**

1. Перейдите на [Google Cloud Console](https://console.cloud.google.com/)
2. Создайте новый проект или откройте существующий
3. Включите Google Sheets API:
   - API & Services → Library
   - Найдите "Google Sheets API"
   - Нажмите "Enable"
4. Создайте Service Account:
   - API & Services → Credentials
   - Create Credentials → Service Account
   - Заполните имя и описание
   - Grant roles: `Editor`
5. Создайте ключ:
   - На странице Service Account нажмите "Keys"
   - Add Key → Create new key → JSON
   - Скачанный файл используйте в установке

**Дайте доступ Service Account к Google Sheet:**
- Откройте ваш Google Sheet
- Нажмите "Share"
- Добавьте email Service Account (виде `...-...-....iam.gserviceaccount.com`)
- Дайте права Editor

### 4️⃣ Redis (опционально)

```
Использовать Redis для хранения сессий? (y/n) [n]: y
Введите REDIS_PASSWORD (оставьте пусто для автогенерации): 
```

Redis нужен для сохранения пользовательских сессий при рестарте бота. Если включить, пароль будет автогенерирован, если не указать свой.

### 5️⃣ Дополнительные настройки

```
Уровень логирования (INFO/DEBUG) [INFO]: INFO
Таймаут Google Sheets (сек) [30]: 30
```

## 🐳 После установки

### Проверка статуса

```bash
# Посмотреть статус контейнеров
docker compose -f /opt/massage_bot/docker-compose.yml ps

# Посмотреть логи бота
docker compose -f /opt/massage_bot/docker-compose.yml logs -f bot

# Посмотреть логи Redis (если включён)
docker compose -f /opt/massage_bot/docker-compose.yml logs -f redis
```

### Управление systemd сервисом

```bash
# Запустить
sudo systemctl start massage-bot

# Остановить
sudo systemctl stop massage-bot

# Перезагрузить
sudo systemctl restart massage-bot

# Посмотреть статус
sudo systemctl status massage-bot

# Реал-тайм логи
sudo journalctl -u massage-bot -f

# Отключить автозапуск
sudo systemctl disable massage-bot
```

### Редактирование конфигурации

Все параметры хранятся в файле `.env`:

```bash
# Редактируем конфигурацию
sudo nano /opt/massage_bot/.env

# После изменений перезагружаем бота
sudo systemctl restart massage-bot
```

## 🔐 Безопасность

### Выданные файлы

После установки в директории `/opt/massage_bot/` будут следующие файлы:

```
.env                    # Конфигурация (ПРИВАТНО - 600)
credentials.json        # Google Service Account ключ (ПРИВАТНО - 600)
.gitignore             # Исключает .env и credentials из git
docker-compose.yml     # Конфигурация Docker
Dockerfile             # Образ бота
```

### Файлы НЕ должны утечь в git

`.gitignore` автоматически исключает:
- `.env` (содержит BOT_TOKEN и Google credentials)
- `credentials.json` (содержит чувствительные ключи)
- `.obsidian/` (локальные данные)

Убедитесь что перед `git push` эти файлы не добавлены:

```bash
git status  # Проверьте что нет .env и credentials.json
```

## 🐛 Troubleshooting

### "Docker команда не найдена"

```bash
# Установите Docker вручную
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# Добавьте пользователя в группу docker (опционально)
sudo usermod -aG docker $USER
```

### "Permission denied" при запуске скрипта

```bash
# Даём права на исполнение
chmod +x install_vps.sh

# Запускаем с sudo
sudo ./install_vps.sh
```

### Бот не отвечает на сообщения

1. Проверьте логи:
   ```bash
   sudo journalctl -u massage-bot -f
   ```

2. Убедитесь что BOT_TOKEN правильный:
   ```bash
   sudo nano /opt/massage_bot/.env
   ```

3. Проверьте подключение к Google Sheets:
   ```bash
   sudo docker compose -f /opt/massage_bot/docker-compose.yml logs bot | grep -i "google\|sheet\|error"
   ```

4. Перезагрузитесь:
   ```bash
   sudo systemctl restart massage-bot
   ```

### Redis не стартует

```bash
# Посмотрите логи Redis
sudo docker compose -f /opt/massage_bot/docker-compose.yml logs redis

# Убедитесь что пароль правильный в .env
sudo nano /opt/massage_bot/.env

# Пересоберите контейнеры
sudo docker compose -f /opt/massage_bot/docker-compose.yml build --no-cache
sudo docker compose -f /opt/massage_bot/docker-compose.yml up -d
```

## 📊 Мониторинг

### Просмотр использования ресурсов

```bash
# Статус контейнеров с процентом использования
docker stats

# История логов (последние 100 строк)
sudo journalctl -u massage-bot -n 100

# Логи за последний час
sudo journalctl -u massage-bot --since "1 hour ago"
```

### Резервная копия конфигурации

```bash
# Создать архив
tar -czf massage_bot_backup_$(date +%Y%m%d).tar.gz /opt/massage_bot/.env /opt/massage_bot/credentials.json

# Восстановить
tar -xzf massage_bot_backup_20260703.tar.gz -C /
```

## 🔄 Обновление бота

```bash
cd /opt/massage_bot

# Скачиваем последние изменения
git pull origin main

# Пересобираем Docker образ
sudo docker compose build --no-cache

# Перезагружаем контейнеры
sudo systemctl restart massage-bot

# Проверяем статус
sudo systemctl status massage-bot
```

## 🆘 Поддержка

Если что-то не работает:

1. **Проверьте логи**: `sudo journalctl -u massage-bot -f`
2. **Посмотрите issues**: https://github.com/nxksxd/massage_bot/issues
3. **Откройте новый issue** с описанием проблемы и логами

## 📚 Дополнительно

- [README.md](./README.md) - Полное описание проекта
- [QUICK_REFERENCE.md](./QUICK_REFERENCE.md) - Быстрая справка по коду
- [REFACTORING_SUMMARY.md](./REFACTORING_SUMMARY.md) - История рефакторинга

---

**Версия**: 1.0 | **Дата**: 2026-07-03 | **Автор**: nxksxd
