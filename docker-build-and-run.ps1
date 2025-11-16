# Скрипт для сборки и запуска Docker контейнера
# Использование: .\docker-build-and-run.ps1

Write-Host "=== Сборка и запуск English Learning Bot ===" -ForegroundColor Cyan

# Проверяем наличие .env файла
if (-not (Test-Path ".env")) {
    Write-Host "⚠️  Файл .env не найден!" -ForegroundColor Yellow
    Write-Host "Создайте .env файл на основе env_example.txt" -ForegroundColor Yellow
    Write-Host "Копирую env_example.txt в .env..." -ForegroundColor Yellow
    Copy-Item "env_example.txt" ".env"
    Write-Host "✅ Файл .env создан. Заполните его своими значениями!" -ForegroundColor Green
    Write-Host "Нажмите Enter после заполнения .env файла..." -ForegroundColor Yellow
    Read-Host
}

# Проверяем наличие credentials.json
if (-not (Test-Path "python-datalens-f6500fa9f949.json")) {
    Write-Host "⚠️  Файл python-datalens-f6500fa9f949.json не найден!" -ForegroundColor Yellow
    Write-Host "Убедитесь, что файл с учетными данными Google Sheets находится в корне проекта" -ForegroundColor Yellow
}

# Останавливаем и удаляем старый контейнер если существует
Write-Host "`n🛑 Останавливаем старый контейнер (если существует)..." -ForegroundColor Yellow
docker-compose down 2>$null

# Собираем образ
Write-Host "`n🔨 Собираем Docker образ..." -ForegroundColor Cyan
docker-compose build

if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ Ошибка при сборке образа!" -ForegroundColor Red
    exit 1
}

Write-Host "✅ Образ успешно собран!" -ForegroundColor Green

# Запускаем контейнер
Write-Host "`n🚀 Запускаем контейнер..." -ForegroundColor Cyan
docker-compose up -d

if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ Ошибка при запуске контейнера!" -ForegroundColor Red
    exit 1
}

Write-Host "✅ Контейнер запущен!" -ForegroundColor Green

# Показываем логи
Write-Host "`n📋 Логи контейнера (Ctrl+C для выхода):" -ForegroundColor Cyan
Write-Host "Для просмотра логов в будущем используйте: docker-compose logs -f" -ForegroundColor Yellow
Write-Host ""

docker-compose logs -f

