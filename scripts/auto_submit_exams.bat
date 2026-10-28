@echo off
rem Auto-submit overdue exam sheets (call via Windows Task Scheduler).
rem Depends on python being on PATH; log appended to backend\auto_submit_exams.log
cd /d "%~dp0.."
python manage.py auto_submit_exams >> auto_submit_exams.log 2>&1
