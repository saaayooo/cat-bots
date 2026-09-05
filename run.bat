@echo off
chcp 65001 > nul
title Кошачий Хаб & Telegram Bot (@koshe4k4bot)
echo ====================================================
echo      Запуск Telegram-бота и Mini App "Кошачий Хаб"
echo ====================================================
echo.

:loop
python bot.py
echo.
echo [INFO] Перезапуск бота через 3 секунды... (Нажмите Ctrl+C для выхода)
timeout /t 3 /nobreak > nul
goto loop
