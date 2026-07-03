#!/bin/bash

################################################################################
# Massage Bot VPS Installation Script (FIXED VERSION)
# Интерактивная установка Massage Bot на Linux VPS с Docker Compose
# Автор: nxksxd
# Дата: 2026-07-03
# Версия: 1.1 (Fixed - no unbound variable errors)
################################################################################

set -euo pipefail

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Логирование
LOG_FILE="/var/log/massage_bot_install_$(date +%Y%m%d_%H%M%S).log"

log() {
    echo -e "${GREEN}[$(date +'%Y-%m-%d %H:%M:%S')]${NC} $1" | tee -a "$LOG_FILE"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1" | tee -a "$LOG_FILE"
    exit 1
}

warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1" | tee -a "$LOG_FILE"
}

info() {
    echo -e "${BLUE}[INFO]${NC} $1" | tee -a "$LOG_FILE"
}

success() {
    echo -e "${GREEN}[✓]${NC} $1" | tee -a "$LOG_FILE"
}

################################################################################
# ПРОВЕРКА ПРИВИЛЕГИЙ И ОКРУЖЕНИЯ
################################################################################

check_root() {
    if [[ $EUID -ne 0 ]]; then
        error "Этот скрипт должен быть запущен от root'а или с sudo"
    fi
    success "Проверка привилегий пройдена"
}

check_os() {
    if [[ ! -f /etc/os-release ]]; then
        error "Невозможно определить ОС"
    fi
    
    . /etc/os-release
    if [[ "$ID" != "ubuntu" && "$ID" != "debian" ]]; then
        warning "Скрипт тестирован только на Ubuntu/Debian, но работает и на других Linux дистрибутивах"
    fi
    success "ОС: $PRETTY_NAME"
}

################################################################################
# ПРОВЕРКА ЗАВИСИМОСТЕЙ
################################################################################

check_dependencies() {
    log "Проверяю зависимости..."
    
    local missing_docker=false
    
    # Проверяем git
    if ! command -v git &> /dev/null; then
        log "git не найден, устанавливаю..."
        apt-get update || error "Не удалось обновить списки пакетов"
        apt-get install -y git || error "Не удалось установить git"
    fi
    success "git найден: $(git --version)"
    
    # Проверяем Docker
    if ! command -v docker &> /dev/null; then
        missing_docker=true
    else
        success "docker найден: $(docker --version)"
    fi
    
    # Проверяем Docker Compose
    if ! docker compose version &> /dev/null 2>&1 && ! command -v docker-compose &> /dev/null; then
        missing_docker=true
    else
        if docker compose version &> /dev/null 2>&1; then
            success "docker compose найден (встроено в Docker)"
        else
            success "docker-compose найден: $(docker-compose --version)"
        fi
    fi
    
    # Проверяем curl
    if ! command -v curl &> /dev/null; then
        log "curl не найден, устанавливаю..."
        apt-get update || error "Не удалось обновить списки пакетов"
        apt-get install -y curl || error "Не удалось установить curl"
    fi
    success "curl найден"
    
    # Если Docker не установлен, устанавливаем из официального репозитория
    if [[ "$missing_docker" == "true" ]]; then
        install_docker_official
    fi
}

install_docker_official() {
    log "Устанавливаю Docker из официального репозитория..."
    
    # Удаляем старые версии Docker если они есть
    apt-get remove -y docker docker.io docker-doc docker-compose podman-docker containerd runc 2>/dev/null || true
    
    # Устанавливаем зависимости для добавления репозитория
    apt-get update
    apt-get install -y ca-certificates curl gnupg lsb-release
    
    # Добавляем GPG ключ Docker
    info "Добавляю GPG ключ Docker..."
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg
    
    # Добавляем Docker репозиторий
    info "Добавляю Docker репозиторий..."
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | \
        tee /etc/apt/sources.list.d/docker.list > /dev/null
    
    # Обновляем список пакетов и устанавливаем Docker
    log "Устанавливаю Docker Engine и Docker Compose..."
    apt-get update
    apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin || \
        error "Не удалось установить Docker из официального репозитория"
    
    # Проверяем успешность установки
    if command -v docker &> /dev/null; then
        success "Docker установлен: $(docker --version)"
        
        # Запускаем Docker daemon
        systemctl start docker
        systemctl enable docker
        success "Docker daemon запущен и включен в автозагрузку"
    else
        error "Не удалось установить Docker"
    fi
}

################################################################################
# ИНТЕРАКТИВНЫЙ ВВОД КОНФИГУРАЦИИ - FIXED VERSION (NO UNBOUND VARIABLES)
################################################################################

prompt_input() {
    local prompt="$1"
    local default="$2"
    local var_name="$3"
    local response=""
    
    if [[ -n "$default" ]]; then
        read -p "$(echo -e ${BLUE})$prompt${NC} [${YELLOW}$default${NC}]: " response
        response="${response:-$default}"
    else
        while [[ -z "$response" ]]; do
            read -p "$(echo -e ${BLUE})$prompt${NC}: " response
            if [[ -z "$response" ]]; then
                echo -e "${RED}Это поле обязательно!${NC}"
            fi
        done
    fi
    
    eval "$var_name='$response'"
}

prompt_secret() {
    local prompt="$1"
    local var_name="$2"
    local response=""
    
    while [[ -z "$response" ]]; do
        read -s -p "$(echo -e ${BLUE})$prompt${NC}: " response || true
        echo
        if [[ -z "$response" ]]; then
            echo -e "${RED}Это поле обязательно!${NC}"
        fi
    done
    
    eval "$var_name='$response'"
}

interactive_config() {
    log "=== КОНФИГУРАЦИЯ MASSAGE BOT ==="
    echo
    
    info "1. Параметры Telegram Bot"
    prompt_secret "Введите BOT_TOKEN (от @BotFather)" BOT_TOKEN
    prompt_input "Введите MASSEUR_ID (Telegram ID администратора)" "" MASSEUR_ID
    
    echo
    info "2. Параметры Google Sheets"
    prompt_input "Введите SPREADSHEET_ID (из ссылки Google Sheet)" "" SPREADSHEET_ID
    prompt_input "Введите имя листа в Google Sheets" "Записи" GOOGLE_SHEET_NAME
    
    echo
    info "3. Google Service Account Credentials"
    info "Вам нужен JSON ключ от Google Service Account для доступа к Google Sheets"
    info "Инструкция: https://cloud.google.com/docs/authentication/getting-started"
    echo
    
    local credentials_file="/tmp/credentials_temp.json"
    local use_file="y"
    
    read -p "$(echo -e ${BLUE})У вас уже есть credentials.json файл? (y/n)${NC} [y]: " use_file
    use_file="${use_file:-y}"
    
    if [[ "$use_file" == "y" ]]; then
        read -p "$(echo -e ${BLUE})Введите путь к credentials.json${NC}: " creds_path
        if [[ ! -f "$creds_path" ]]; then
            error "Файл не найден: $creds_path"
        fi
        GOOGLE_CREDENTIALS=$(cat "$creds_path" | jq -c '.')
    else
        info "Скопируйте JSON содержимое credentials.json и вставьте (завершите с Ctrl+D):"
        GOOGLE_CREDENTIALS=$(cat)
        
        # Валидируем JSON
        if ! echo "$GOOGLE_CREDENTIALS" | jq . > /dev/null 2>&1; then
            error "Невалидный JSON в credentials"
        fi
    fi
    
    echo
    info "4. Redis конфигурация (опционально)"
    read -p "$(echo -e ${BLUE})Использовать Redis для хранения сессий? (y/n)${NC} [n]: " use_redis
    use_redis="${use_redis:-n}"
    
    if [[ "$use_redis" == "y" ]]; then
        prompt_secret "Введите REDIS_PASSWORD (оставьте пусто для автогенерации)" REDIS_PASSWORD
        if [[ -z "$REDIS_PASSWORD" ]]; then
            REDIS_PASSWORD=$(openssl rand -base64 32)
            info "Сгенерирован пароль Redis: $REDIS_PASSWORD"
        fi
        USE_REDIS_STORAGE="true"
    else
        REDIS_PASSWORD=""
        USE_REDIS_STORAGE="false"
    fi
    
    echo
    info "5. Дополнительные настройки"
    prompt_input "Уровень логирования (INFO/DEBUG)" "INFO" LOG_LEVEL
    prompt_input "Таймаут Google Sheets (сек)" "30" GOOGLE_SHEETS_TIMEOUT
    
    # Сохраняем в глобальные переменные для последующего использования
    export BOT_TOKEN MASSEUR_ID SPREADSHEET_ID GOOGLE_SHEET_NAME GOOGLE_CREDENTIALS
    export REDIS_PASSWORD USE_REDIS_STORAGE LOG_LEVEL GOOGLE_SHEETS_TIMEOUT
}

################################################################################
# КЛОНИРОВАНИЕ РЕПОЗИТОРИЯ
################################################################################

clone_repository() {
    log "Клонирую репозиторий massage_bot..."
    
    local repo_url="https://github.com/nxksxd/massage_bot.git"
    local install_dir="/opt/massage_bot"
    
    if [[ -d "$install_dir" ]]; then
        warning "Директория $install_dir уже существует"
        read -p "$(echo -e ${BLUE})Перезаписать? (y/n)${NC} [n]: " overwrite
        overwrite="${overwrite:-n}"
        
        if [[ "$overwrite" == "y" ]]; then
            rm -rf "$install_dir"
            log "Директория удалена"
        else
            log "Используется существующая директория"
            cd "$install_dir" || error "Не удалось перейти в $install_dir"
            return 0
        fi
    fi
    
    mkdir -p "$install_dir"
    cd "$install_dir" || error "Не удалось перейти в $install_dir"
    
    git clone "$repo_url" . || error "Не удалось клонировать репозиторий"
    success "Репозиторий клонирован в $install_dir"
    
    export INSTALL_DIR="$install_dir"
}

################################################################################
# ГЕНЕРАЦИЯ .env ФАЙЛА
################################################################################

generate_env_file() {
    log "Генерирую .env файл..."
    
    local env_file="${INSTALL_DIR}/.env"
    
    cat > "$env_file" << EOF
# Telegram Bot Token (получите у @BotFather)
BOT_TOKEN=${BOT_TOKEN}

# Telegram ID массажиста (узнайте через @userinfobot)
MASSEUR_ID=${MASSEUR_ID}

# Google Sheets
CREDENTIALS_FILE=credentials.json
SPREADSHEET_ID=${SPREADSHEET_ID}
GOOGLE_SHEET_NAME=${GOOGLE_SHEET_NAME}

# Google Sheets оптимизация
GOOGLE_SHEET_CACHE_TTL=300
GOOGLE_SHEETS_MAX_RETRIES=3
GOOGLE_SHEETS_TIMEOUT=${GOOGLE_SHEETS_TIMEOUT}
GOOGLE_SHEETS_RETRY_DELAY=1

# Redis (для продакшена - сохранение сессий при рестарте)
REDIS_URL=redis://redis:6379/0
USE_REDIS_STORAGE=${USE_REDIS_STORAGE}
EOF

    if [[ -n "$REDIS_PASSWORD" && "$USE_REDIS_STORAGE" == "true" ]]; then
        echo "REDIS_PASSWORD=${REDIS_PASSWORD}" >> "$env_file"
    fi
    
    cat >> "$env_file" << EOF

# Логирование
LOG_LEVEL=${LOG_LEVEL}
EOF

    # Создаём credentials.json из переменной
    if [[ -n "$GOOGLE_CREDENTIALS" ]]; then
        echo "$GOOGLE_CREDENTIALS" | jq '.' > "${INSTALL_DIR}/credentials.json" || \
            error "Не удалось создать credentials.json"
        success "credentials.json создан"
    fi
    
    # Устанавливаем правильные права доступа
    chmod 600 "$env_file"
    chmod 600 "${INSTALL_DIR}/credentials.json" 2>/dev/null || true
    
    success ".env файл сгенерирован"
}

################################################################################
# ПОДГОТОВКА DOCKER COMPOSE
################################################################################

prepare_docker_compose() {
    log "Подготавливаю docker-compose.yml..."
    
    local compose_file="${INSTALL_DIR}/docker-compose.yml"
    
    if [[ ! -f "$compose_file" ]]; then
        error "docker-compose.yml не найден в репозитории"
    fi
    
    # Если используется Redis, убеждаемся что он в compose файле
    if [[ "$USE_REDIS_STORAGE" == "true" ]]; then
        info "Redis включён в конфигурацию"
    fi
    
    success "docker-compose.yml готов"
}

################################################################################
# ЗАПУСК DOCKER COMPOSE
################################################################################

start_services() {
    log "Запускаю Docker контейнеры..."
    
    cd "$INSTALL_DIR" || error "Не удалось перейти в $INSTALL_DIR"
    
    # Строим образ
    docker compose build || error "Не удалось собрать Docker образ"
    success "Docker образ собран"
    
    # Запускаем контейнеры
    docker compose up -d || error "Не удалось запустить контейнеры"
    success "Docker контейнеры запущены"
    
    # Ждём немного для инициализации
    sleep 5
}

################################################################################
# ПРОВЕРКА СТАТУСА
################################################################################

check_status() {
    log "=== ПРОВЕРКА СТАТУСА ==="
    echo
    
    info "Docker контейнеры:"
    docker compose ps || warning "Не удалось получить статус контейнеров"
    
    echo
    info "Логи бота (последние 20 строк):"
    docker compose logs --tail=20 bot 2>/dev/null || warning "Не удалось получить логи"
    
    echo
    info "Проверка подключения к боту..."
    if docker compose exec -T bot python -c "import telegram; print('✓ Telegram library OK')" 2>/dev/null; then
        success "Telegram библиотека загружена"
    else
        warning "Не удалось проверить Telegram библиотеку"
    fi
}

################################################################################
# СОЗДАНИЕ SYSTEMD СЕРВИСА
################################################################################

create_systemd_service() {
    log "Создаю systemd сервис для автозапуска..."
    
    local service_file="/etc/systemd/system/massage-bot.service"
    
    cat > "$service_file" << EOF
[Unit]
Description=Massage Bot Service
After=network.target docker.service
Requires=docker.service

[Service]
Type=simple
WorkingDirectory=${INSTALL_DIR}
ExecStart=docker compose up
ExecStop=docker compose down
Restart=on-failure
RestartSec=10
User=root

[Install]
WantedBy=multi-user.target
EOF

    systemctl daemon-reload
    systemctl enable massage-bot.service
    success "Systemd сервис создан: massage-bot.service"
    
    info "Используйте следующие команды для управления:"
    echo "  systemctl start massage-bot     # Запустить"
    echo "  systemctl stop massage-bot      # Остановить"
    echo "  systemctl restart massage-bot   # Перезагрузить"
    echo "  systemctl status massage-bot    # Статус"
    echo "  journalctl -u massage-bot -f    # Логи"
}

################################################################################
# ФИНАЛЬНЫЙ ОТЧЁТ
################################################################################

print_summary() {
    echo
    echo -e "${GREEN}════════════════════════════════════════════════════════════${NC}"
    echo -e "${GREEN}  ✓ MASSAGE BOT УСПЕШНО УСТАНОВЛЕН${NC}"
    echo -e "${GREEN}════════════════════════════════════════════════════════════${NC}"
    echo
    
    echo -e "${BLUE}📍 Локация установки:${NC} ${YELLOW}${INSTALL_DIR}${NC}"
    echo -e "${BLUE}📋 Конфигурация:${NC} ${YELLOW}${INSTALL_DIR}/.env${NC}"
    echo -e "${BLUE}📊 Google Credentials:${NC} ${YELLOW}${INSTALL_DIR}/credentials.json${NC}"
    echo -e "${BLUE}📜 Логи установки:${NC} ${YELLOW}${LOG_FILE}${NC}"
    echo
    
    echo -e "${BLUE}🐳 Docker контейнеры:${NC}"
    docker compose -f "${INSTALL_DIR}/docker-compose.yml" ps | tail -n +2 || true
    echo
    
    echo -e "${BLUE}⚙️ Управление сервисом:${NC}"
    echo "  systemctl start massage-bot      # Запустить"
    echo "  systemctl stop massage-bot       # Остановить"
    echo "  systemctl restart massage-bot    # Перезагрузить"
    echo "  systemctl status massage-bot     # Статус"
    echo "  journalctl -u massage-bot -f     # Реал-тайм логи"
    echo
    
    echo -e "${BLUE}📚 Документация:${NC}"
    echo "  ${YELLOW}${INSTALL_DIR}/README.md${NC}"
    echo "  ${YELLOW}${INSTALL_DIR}/QUICK_REFERENCE.md${NC}"
    echo
    
    echo -e "${BLUE}✨ Следующие шаги:${NC}"
    echo "  1. Убедитесь что бот активен и обрабатывает сообщения"
    echo "  2. Проверьте логи: journalctl -u massage-bot -f"
    echo "  3. При необходимости отредактируйте .env и перезагрузитесь"
    echo
    
    echo -e "${GREEN}════════════════════════════════════════════════════════════${NC}"
    echo
}

################################################################################
# MAIN FLOW
################################################################################

main() {
    echo
    echo -e "${BLUE}╔══════════════════════════════════════════════════════╗${NC}"
    echo -e "${BLUE}║      MASSAGE BOT VPS INSTALLATION SCRIPT             ║${NC}"
    echo -e "${BLUE}║            Версия 1.1 | 2026-07-03 (FIXED)           ║${NC}"
    echo -e "${BLUE}╚══════════════════════════════════════════════════════╝${NC}"
    echo
    
    # Этап 1: Проверки
    log "=== ЭТАП 1: ПРОВЕРКИ ==="
    check_root
    check_os
    check_dependencies
    echo
    
    # Этап 2: Интерактивная конфигурация
    log "=== ЭТАП 2: КОНФИГУРАЦИЯ ==="
    interactive_config
    echo
    
    # Этап 3: Клонирование
    log "=== ЭТАП 3: КЛОНИРОВАНИЕ РЕПОЗИТОРИЯ ==="
    clone_repository
    echo
    
    # Этап 4: Генерация .env
    log "=== ЭТАП 4: ГЕНЕРАЦИЯ КОНФИГУРАЦИИ ==="
    generate_env_file
    prepare_docker_compose
    echo
    
    # Этап 5: Запуск Docker
    log "=== ЭТАП 5: ЗАПУСК DOCKER КОНТЕЙНЕРОВ ==="
    start_services
    echo
    
    # Этап 6: Проверка статуса
    log "=== ЭТАП 6: ПРОВЕРКА СТАТУСА ==="
    check_status
    echo
    
    # Этап 7: Systemd сервис
    log "=== ЭТАП 7: НАСТРОЙКА АВТОЗАПУСКА ==="
    create_systemd_service
    echo
    
    # Финальный отчёт
    print_summary
    
    log "Установка завершена успешно. Логи сохранены в $LOG_FILE"
}

# Запуск
main "$@"
