#!/bin/bash
# Script per aggiungere la regola /api/admin/ a nginx

CONFIG_FILE="/etc/nginx/sites-available/kimerika.cloud"
BACKUP_FILE="${CONFIG_FILE}.backup.$(date +%Y%m%d_%H%M%S)"

echo "🔧 Aggiornamento configurazione NGINX per /api/admin/"
echo "=================================================="

# Backup
echo "📦 Backup configurazione attuale..."
sudo cp "$CONFIG_FILE" "$BACKUP_FILE"
echo "✅ Backup salvato in: $BACKUP_FILE"

# Cerca se la regola admin esiste già
if sudo grep -q "location ~ \^/api/admin/" "$CONFIG_FILE"; then
    echo "✅ La regola /api/admin/ esiste già!"
    exit 0
fi

# Crea il nuovo blocco per /api/admin/
ADMIN_BLOCK='    # Admin API endpoints (Flask auth_server.py:5000)
    location ~ ^/api/admin/ {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

'

# Inserisci la regola PRIMA di "location ~ ^/api/"
echo "📝 Aggiunta regola /api/admin/ alla configurazione..."
sudo sed -i "/location ~ \^\/api\/ {/i\\
$ADMIN_BLOCK" "$CONFIG_FILE"

echo "✅ Regola aggiunta con successo!"

# Test configurazione
echo ""
echo "🧪 Test configurazione NGINX..."
if sudo nginx -t; then
    echo ""
    echo "✅ Configurazione valida!"
    echo ""
    echo "🔄 Ricarico NGINX..."
    sudo systemctl reload nginx
    echo "✅ NGINX ricaricato!"
    echo ""
    echo "📋 Nuova configurazione API:"
    sudo grep -A 5 "location ~ \^/api" "$CONFIG_FILE" | head -30
else
    echo ""
    echo "❌ Errore nella configurazione!"
    echo "🔄 Ripristino backup..."
    sudo cp "$BACKUP_FILE" "$CONFIG_FILE"
    echo "⚠️  Configurazione originale ripristinata"
    exit 1
fi

echo ""
echo "✨ Completato! Gli endpoint /api/admin/* ora puntano alla porta 5000"
