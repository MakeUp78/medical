#!/usr/bin/env python3
"""Fix nginx configuration - use negative lookahead for generic /api/ rule"""
import re
import shutil
from datetime import datetime

CONFIG_FILE = "/etc/nginx/sites-available/kimerika.cloud"
BACKUP_FILE = f"{CONFIG_FILE}.backup.{datetime.now().strftime('%Y%m%d_%H%M%S')}"

print("🔧 Fix nginx /api/ regex con negative lookahead")
print("=" * 60)

# Backup
print(f"📦 Backup: {BACKUP_FILE}")
shutil.copy2(CONFIG_FILE, BACKUP_FILE)

# Leggi configurazione
with open(CONFIG_FILE, 'r') as f:
    config = f.read()

# Trova la regola generica /api/ e sostituiscila
# DA: location ~ ^/api/ {
# A:  location ~ ^/api/(?!auth/|user/|admin/) {
old_pattern = r'location ~ \^/api/ \{'
new_pattern = r'location ~ ^/api/(?!auth/|user/|admin/) {'

if old_pattern not in config:
    print("❌ Pattern non trovato")
    exit(1)

# Sostituisci
new_config = config.replace(old_pattern, new_pattern)

# Scrivi
with open(CONFIG_FILE, 'w') as f:
    f.write(new_config)

print("✅ Regex aggiornata!")
print("\n📋 Nuova logica:")
print("  • /api/auth/*   → porta 5000 (Flask)")
print("  • /api/user/*   → porta 5000 (Flask)")
print("  • /api/admin/*  → porta 5000 (Flask)")
print("  • /api/*        → porta 8001 (FastAPI) [escluso auth/user/admin]")
