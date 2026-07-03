@echo off
cd /d "%~dp0"
echo ============================================
echo   AI Document Summarizer
echo   Starting server at http://127.0.0.1:9000
echo ============================================
echo.
python app.py
pause