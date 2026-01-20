#!/usr/bin/env python3
"""Fix nginx configuration for /api/admin/ endpoints"""
import re
import shutil
from datetime import datetime

CONFIG_FILE = "/etc/nginx/sites-available/kimerika.cloud"
BACKUP_FILE = f"{CONFIG_FILE}.backup.{datetime.now().strftime('%Y%m%d_%H%M%S')}"

ADMIN_BLOCK = """    # Admin API endpoints (Flask auth_server.py:5000)
    location ~ ^/api/admin/ {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

"""

print("🔧 Aggiornamento configurazione NGINX per /api/admin/")
print("=" * 60)

# Backup
print(f"📦 Backup: {BACKUP_FILE}")
shutil.copy2(CONFIG_FILE, BACKUP_FILE)

# Leggi configurazione
with open(CONFIG_FILE, 'r') as f:
    config = f.read()

# Verifica se esiste già
if 'location ~ ^/api/admin/' in config:
    print("✅ La regola /api/admin/ esiste già!")
    exit(0)

# Trova la posizione di "location ~ ^/api/ {" (regola generica)
# e inserisci il blocco admin PRIMA
pattern = r'(\s+)(location ~ \^/api/ \{)'
match = re.search(pattern, config)

if not match:
    print("❌ Non trovata la regola generica /api/")
    exit(1)

# Inserisci il blocco admin prima della regola generica
new_config = config[:match.start()] + ADMIN_BLOCK + config[match.start():]

# Scrivi la nuova configurazione
with open(CONFIG_FILE, 'w') as f:
    f.write(new_config)

print("✅ Regola aggiunta con successo!")
print("\n📋 Ordine delle regole API ora:")
print("  1. /api/auth/   → 5000 (Flask)")
print("  2. /api/user/   → 5000 (Flask)")
print("  3. /api/admin/  → 5000 (Flask) ← NUOVO")
print("  4. /api/*       → 8001 (FastAPI)")
