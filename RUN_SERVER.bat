@echo off
title ChildMonitor Server (Port 3375)
cd /d "%~dp0"
echo =================================================================
echo 🛡️ ChildMonitor Server सुरु होत आहे...
echo 💻 PC वर पाहण्यासाठी: http://127.0.0.1:3375
echo 📱 मोबाईल ब्राऊझर/ॲपसाठी: http://10.247.151.235:3375
echo 🔐 डॅशबोर्ड पासवर्ड: Indiansk@5460
echo =================================================================
echo.
python server.py
pause
