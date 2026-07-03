#!/bin/bash

###############################################################################
# 🤖 Massage Bot — Interactive Installation Script
# 
# Использование:
#   bash install.sh
#
# Требования:
#   - Linux (Ubuntu 20.04+, Debian 11+)
#   - Интернет соединение
#   - sudo доступ (для установки Docker)
#
# Скрипт установит:
#   - Docker & Docker Compose
#   - Massage Bot с Redis
#   - Настроит .env файл
#   - Запустит сервис
#
###############################################################################

set -e  # Exit on any error

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Функции вывода
print_header() {
    echo -e "\n${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}\n"
}

print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

# Проверка прав
check_sudo() {
    if [ "$EUID" -ne 0 ]; then
        print_error "Требуется sudo доступ! Запустите: sudo bash install.sh"
        exit 1
    fi
}

# Проверка ОС
check_os() {
    print_header "🔍 Проверка системы"
    
    if [[ ! "$OSTYPE" == "linux-gnu"* ]]; then
        print_error "Этот скрипт работает только на Linux"
        exit 1
    fi
    
    if command -v lsb_release &> /dev/null; then
        OS=$(lsb_release -si)
        VERSION=$(lsb_release -sr)
        print_success "ОС: $OS $VERSION"
    else
        print_warning "Не удалось определить версию ОС, продолжаю..."
    fi
}

# Проверка Docker
check_docker() {
    print_header "🐳 Проверка Docker"
    
    if command -v docker &> /dev/null; then
        DOCKER_VERSION=$(docker --version | cut -d' ' -f3 | cut -d',' -f1)
        print_success "Docker установлен: $DOCKER_VERSION"
    else
        print_warning "Docker не установлен, устанавливаю..."
        install_docker
    fi
    
    if command -v docker-compose &> /dev/null; then
        COMPOSE_VERSION=$(docker-compose --version | cut -d' ' -f3 | cut -d',' -f1)
        print_success "Docker Compose установлен: $COMPOSE_VERSION"
    else
        print_warning "Docker Compose не установлен, устанавливаю..."
        install_docker_compose
    fi
}

install_docker() {
    print_info "Устанавливаю Docker..."
    
    # Удаляем старые версии
    apt-get remove -y docker docker-engine docker.io containerd runc 2>/dev/null || true
    
    # Обновляем репозитории
    apt-get update
    apt-get install -y \
        ca-certificates \
        curl \
        gnupg \
        lsb-release
    
    # Добавляем Docker GPG ключ
    mkdir -p /etc/apt/keyrings
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
    
    # Добавляем Docker репозиторий
    echo \
        "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
        $(lsb_release -cs) stable" | tee /etc/apt/sources.list.d/docker.list > /dev/null
    
    # Устанавливаем Docker
    apt-get update
    apt-get install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin
    
    # Запускаем Docker
    systemctl start docker
    systemctl enable docker
    
    print_success "Docker установлен успешно!"
}

install_docker_compose() {
    print_info "Устанавливаю Docker Compose..."
    
    # Загружаем последнюю версию Docker Compose
    COMPOSE_VERSION=$(curl -s https://api.github.com/repos/docker/compose/releases/latest | grep 'tag_name' | cut -d'"' -f4 | cut -d'v' -f2)
    curl -L "https://github.com/docker/compose/releases/download/v${COMPOSE_VERSION}/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
    chmod +x /usr/local/bin/docker-compose
    
    print_success "Docker Compose установлен успешно!"
}

# Проверка Git
check_git() {
    print_header "📦 Проверка зависимостей"
    
    if command -v git &> /dev/null; then
        GIT_VERSION=$(git --version | cut -d' ' -f3)
        print_success "Git установлен: $GIT_VERSION"
    else
        print_warning "Git не установлен, устанавливаю..."
        apt-get update
        apt-get install -y git
        print_success "Git установлен успешно!"
    fi
}

# Запрос данных конфигурации
input_configuration() {
    print_header "🔐 Ввод конфигурации"
    
    # BOT_TOKEN
    print_info "Получите токен у @BotFather: https://t.me/BotFather"
    read -p "Введите BOT_TOKEN: " BOT_TOKEN
    
    while [ -z "$BOT_TOKEN" ]; do
        print_error "BOT_TOKEN не может быть пусто!"
        read -p "Введите BOT_TOKEN: " BOT_TOKEN
    done
    print_success "BOT_TOKEN сохранён"
    
    # MASSEUR_ID
    print_info "Получите свой Telegram ID у @userinfobot"
    read -p "Введите MASSEUR_ID (ваш Telegram ID): " MASSEUR_ID
    
    while ! [[ "$MASSEUR_ID" =~ ^[0-9]+$ ]]; do
        print_error "MASSEUR_ID должен быть числом!"
        read -p "Введите MASSEUR_ID: " MASSEUR_ID
    done
    print_success "MASSEUR_ID: $MASSEUR_ID"
    
    # SPREADSHEET_ID
    print_info "Откройте Google Таблицу с записями"
    print_info "SPREADSHEET_ID — это ID из URL"
    print_info "Пример: https://docs.google.com/spreadsheets/d/[SPREADSHEET_ID]/edit"
    read -p "Введите SPREADSHEET_ID: " SPREADSHEET_ID
    
    while [ -z "$SPREADSHEET_ID" ]; do
        print_error "SPREADSHEET_ID не может быть пусто!"
        read -p "Введите SPREADSHEET_ID: " SPREADSHEET_ID
    done
    print_success "SPREADSHEET_ID сохранён"
    
    # GOOGLE_SHEET_NAME
    read -p "Введите имя листа в таблице (по умолчанию 'Записи'): " GOOGLE_SHEET_NAME
    GOOGLE_SHEET_NAME=${GOOGLE_SHEET_NAME:-"Записи"}
    print_success "Имя листа: $GOOGLE_SHEET_NAME"
    
    # Google credentials.json
    print_header "📄 Загрузка Google Service Account credentials"
    print_info "Получите credentials.json из Google Cloud Console:"
    print_info "1. Создайте Service Account"
    print_info "2. Создайте JSON ключ"
    print_info "3. Скопируйте содержимое JSON файла"
    echo ""
    
    # Проверяем если файл уже есть локально
    if [ -f "credentials.json" ]; then
        read -p "Найден credentials.json. Использовать его? (y/n): " USE_EXISTING
        if [[ "$USE_EXISTING" == "y" ]]; then
            print_success "Будет использован существующий credentials.json"
        else
            input_credentials_json
        fi
    else
        input_credentials_json
    fi
}

input_credentials_json() {
    print_info "Вставьте содержимое credentials.json (Ctrl+D для завершения):"
    CREDENTIALS_JSON=$(cat)
    
    while [ -z "$CREDENTIALS_JSON" ]; do
        print_error "credentials.json не может быть пусто!"
        print_info "Вставьте содержимое credentials.json (Ctrl+D для завершения):"
        CREDENTIALS_JSON=$(cat)
    done
    
    # Проверяем JSON валидность (простая проверка)
    if ! echo "$CREDENTIALS_JSON" | grep -q "private_key"; then
        print_error "Похоже, это не Google Service Account credentials!"
        print_info "Попробуйте снова..."
        input_credentials_json
    else
        print_success "credentials.json валиден"
    fi
}

# Выбор конфигурации оптимизации
input_optimization() {
    print_header "⚙️  Конфигурация оптимизации"
    
    echo "Параметры Google Sheets оптимизации:"
    echo "  GOOGLE_SHEET_CACHE_TTL — кеш подключения (сек, по умолчанию 300)"
    echo "  GOOGLE_SHEETS_MAX_RETRIES — макс попыток retry (по умолчанию 3)"
    echo "  GOOGLE_SHEETS_TIMEOUT — таймаут операции (сек, по умолчанию 30)"
    echo ""
    
    read -p "Использовать значения по умолчанию? (y/n): " USE_DEFAULTS
    
    if [[ "$USE_DEFAULTS" == "n" ]]; then
        read -p "GOOGLE_SHEET_CACHE_TTL (300): " GOOGLE_SHEET_CACHE_TTL
        GOOGLE_SHEET_CACHE_TTL=${GOOGLE_SHEET_CACHE_TTL:-300}
        
        read -p "GOOGLE_SHEETS_MAX_RETRIES (3): " GOOGLE_SHEETS_MAX_RETRIES
        GOOGLE_SHEETS_MAX_RETRIES=${GOOGLE_SHEETS_MAX_RETRIES:-3}
        
        read -p "GOOGLE_SHEETS_TIMEOUT (30): " GOOGLE_SHEETS_TIMEOUT
        GOOGLE_SHEETS_TIMEOUT=${GOOGLE_SHEETS_TIMEOUT:-30}
    else
        GOOGLE_SHEET_CACHE_TTL=300
        GOOGLE_SHEETS_MAX_RETRIES=3
        GOOGLE_SHEETS_TIMEOUT=30
    fi
    
    print_success "Параметры оптимизации установлены"
}

# Выбор каталога установки
input_install_path() {
    print_header "📁 Выбор каталога установки"
    
    DEFAULT_PATH="/opt/massage_bot"
    read -p "Каталог установки (по умолчанию $DEFAULT_PATH): " INSTALL_PATH
    INSTALL_PATH=${INSTALL_PATH:-$DEFAULT_PATH}
    
    print_success "Путь установки: $INSTALL_PATH"
}

# Клонирование репозитория
clone_repository() {
    print_header "📥 Клонирование репозитория"
    
    if [ -d "$INSTALL_PATH" ]; then
        print_warning "Каталог $INSTALL_PATH уже существует"
        read -p "Удалить существующую установку? (y/n): " DELETE_EXISTING
        
        if [[ "$DELETE_EXISTING" == "y" ]]; then
            rm -rf "$INSTALL_PATH"
            print_info "Каталог удалён"
        else
            print_info "Использую существующий каталог"
            return
        fi
    fi
    
    mkdir -p "$INSTALL_PATH"
    
    print_info "Клонирую репозиторий..."
    git clone https://github.com/nxksxd/massage_bot.git "$INSTALL_PATH"
    
    cd "$INSTALL_PATH"
    print_success "Репозиторий клонирован"
}

# Создание .env файла
create_env_file() {
    print_header "⚙️  Создание .env файла"
    
    ENV_FILE="$INSTALL_PATH/.env"
    
    cat > "$ENV_FILE" << EOF
# Telegram
BOT_TOKEN=$BOT_TOKEN
MASSEUR_ID=$MASSEUR_ID

# Google Sheets
CREDENTIALS_FILE=credentials.json
SPREADSHEET_ID=$SPREADSHEET_ID
GOOGLE_SHEET_NAME=$GOOGLE_SHEET_NAME

# Google Sheets оптимизация
GOOGLE_SHEET_CACHE_TTL=$GOOGLE_SHEET_CACHE_TTL
GOOGLE_SHEETS_MAX_RETRIES=$GOOGLE_SHEETS_MAX_RETRIES
GOOGLE_SHEETS_TIMEOUT=$GOOGLE_SHEETS_TIMEOUT
GOOGLE_SHEETS_RETRY_DELAY=1

# Redis (для продакшена — сохранение сессий)
REDIS_URL=redis://redis:6379/0
USE_REDIS_STORAGE=true

# Логирование
LOG_LEVEL=INFO
EOF
    
    print_success ".env файл создан: $ENV_FILE"
}

# Сохранение credentials.json
save_credentials() {
    print_header "💾 Сохранение Google Service Account"
    
    CREDENTIALS_FILE="$INSTALL_PATH/credentials.json"
    echo "$CREDENTIALS_JSON" > "$CREDENTIALS_FILE"
    
    # Ограничиваем права доступа (только владелец может читать)
    chmod 600 "$CREDENTIALS_FILE"
    
    print_success "credentials.json сохранён с безопасными правами (600)"
}

# Настройка systemd сервиса
setup_systemd_service() {
    print_header "🔧 Настройка systemd сервиса"
    
    SERVICE_FILE="/etc/systemd/system/massage-bot.service"
    
    cat > "$SERVICE_FILE" << EOF
[Unit]
Description=Massage Bot Telegram Service
After=docker.service
Requires=docker.service

[Service]
Type=simple
WorkingDirectory=$INSTALL_PATH
ExecStart=/usr/bin/docker-compose up --no-ansi
ExecStop=/usr/bin/docker-compose down
Restart=on-failure
RestartSec=10s
User=root

[Install]
WantedBy=multi-user.target
EOF
    
    systemctl daemon-reload
    systemctl enable massage-bot.service
    
    print_success "systemd сервис установлен"
    print_info "Команды управления:"
    print_info "  systemctl start massage-bot     # Запустить"
    print_info "  systemctl stop massage-bot      # Остановить"
    print_info "  systemctl restart massage-bot   # Перезагрузить"
    print_info "  systemctl status massage-bot    # Статус"
    print_info "  journalctl -u massage-bot -f    # Логи (реальное время)"
}

# Запуск docker-compose
start_services() {
    print_header "🚀 Запуск сервисов"
    
    cd "$INSTALL_PATH"
    
    print_info "Собираю Docker образ и запускаю сервисы..."
    docker-compose up -d --build
    
    print_success "Сервисы запущены!"
}

# Проверка здоровья
health_check() {
    print_header "🏥 Проверка здоровья"
    
    sleep 5  # Даём сервисам время на запуск
    
    print_info "Проверяю Redis..."
    if docker-compose -f "$INSTALL_PATH/docker-compose.yml" exec -T redis redis-cli ping &> /dev/null; then
        print_success "Redis работает"
    else
        print_warning "Redis может быть ещё в процессе запуска"
    fi
    
    print_info "Проверяю статус Docker контейнеров..."
    cd "$INSTALL_PATH"
    docker-compose ps
    
    echo ""
    print_success "Установка завершена!"
}

# Вывод информации после установки
print_final_info() {
    print_header "ℹ️  ИНФОРМАЦИЯ ПОСЛЕ УСТАНОВКИ"
    
    echo "Путь установки: $INSTALL_PATH"
    echo ""
    echo "Команды управления ботом:"
    echo "  Запустить:     systemctl start massage-bot"
    echo "  Остановить:    systemctl stop massage-bot"
    echo "  Перезагрузить: systemctl restart massage-bot"
    echo "  Статус:        systemctl status massage-bot"
    echo "  Логи (live):   journalctl -u massage-bot -f"
    echo ""
    echo "Команды Docker:"
    echo "  Логи бота:     docker logs -f massage_bot"
    echo "  Логи Redis:    docker logs -f massage_bot_redis"
    echo "  Статус:        docker ps"
    echo ""
    echo "Файлы конфигурации:"
    echo "  .env:          $INSTALL_PATH/.env"
    echo "  credentials:   $INSTALL_PATH/credentials.json"
    echo "  docker-compose: $INSTALL_PATH/docker-compose.yml"
    echo ""
    echo "Веб-интерфейсы:"
    echo "  Redis:         localhost:6379"
    echo "  Бот:           @$(echo $BOT_TOKEN | cut -d':' -f1)"
    echo ""
    echo "Документация: $INSTALL_PATH/README.md"
    echo ""
    print_success "Бот успешно установлен и запущен! 🎉"
    print_info "Отправьте /start боту в Telegram для проверки"
}

# Обработка ошибок
error_handler() {
    print_error "Произошла ошибка на линии $1"
    exit 1
}

trap 'error_handler $LINENO' ERR

# MAIN FLOW
main() {
    clear
    echo ""
    echo -e "${BLUE}"
    echo "╔════════════════════════════════════════════════════════╗"
    echo "║          🤖 Massage Bot — Installation Script          ║"
    echo "║                                                        ║"
    echo "║    Интерактивная установка Telegram бота на VPS       ║"
    echo "║                                                        ║"
    echo "╚════════════════════════════════════════════════════════╝"
    echo -e "${NC}"
    echo ""
    
    check_sudo
    check_os
    check_docker
    check_git
    input_install_path
    input_configuration
    input_optimization
    clone_repository
    create_env_file
    save_credentials
    start_services
    health_check
    setup_systemd_service
    print_final_info
}

# Запуск main функции
main "$@"