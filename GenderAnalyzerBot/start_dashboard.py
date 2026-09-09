import os
import sys

# Dashboardni ishga tushirish uchun yordamchi skript
def run_dashboard():
    print("=== Gender Analyzer Dashboard ishga tushirilmoqda ===")
    print("Manzil: http://127.0.0.1:5000")
    
    # Dashboard papkasiga o'tib app.py ni ishga tushiramiz
    os.system(f"{sys.executable} dashboard/app.py")

if __name__ == "__main__":
    run_dashboard()
