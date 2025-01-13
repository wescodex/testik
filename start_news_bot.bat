@echo off
echo Starting News Bot Application...

:: Создаем директорию для логов, если её нет
if not exist logs mkdir logs

:: Запускаем Telegram бота в фоновом режиме
start "Telegram Bot" cmd /c "python telegram_news_bot.py"

:: Ждем 2 секунды
timeout /t 2 /nobreak > nul

:: Запускаем админ-панель
start "Admin Panel" cmd /c "streamlit run admin_interface.py"

echo Application started successfully!
echo Admin panel will open in your browser automatically.
echo Do not close this window while the application is running.

:: Ждем нажатия клавиши для выхода
pause
