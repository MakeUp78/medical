#!/usr/bin/env python3
"""
Script di test per l'integrazione PayPal
Verifica che gli endpoint siano funzionanti e che il database sia configurato correttamente
"""

import requests
import json
import os
from dotenv import load_dotenv

# Carica variabili d'ambiente
load_dotenv()

# Configurazione
API_BASE_URL = "http://localhost:8001"
TEST_PLAN = "monthly"

def test_paypal_config():
    """Test endpoint configurazione PayPal"""
    print("🧪 Test 1: Configurazione PayPal")
    try:
        response = requests.get(f"{API_BASE_URL}/api/paypal/config")
        response.raise_for_status()
        config = response.json()
        
        if 'client_id' in config and config['client_id']:
            print(f"✅ Client ID configurato: {config['client_id'][:20]}...")
            print(f"✅ Valuta: {config['currency']}")
            return True
        else:
            print("❌ Client ID non configurato")
            return False
    except Exception as e:
        print(f"❌ Errore: {e}")
        return False

def test_create_order():
    """Test creazione ordine PayPal"""
    print("\n🧪 Test 2: Creazione ordine PayPal")
    try:
        response = requests.post(
            f"{API_BASE_URL}/api/paypal/create-order",
            json={"plan_type": TEST_PLAN},
            headers={"Content-Type": "application/json"}
        )
        response.raise_for_status()
        order = response.json()
        
        if 'order_id' in order and 'approval_url' in order:
            print(f"✅ Ordine creato: {order['order_id']}")
            print(f"✅ URL approvazione: {order['approval_url'][:50]}...")
            return True
        else:
            print("❌ Risposta ordine non valida")
            return False
    except Exception as e:
        print(f"❌ Errore: {e}")
        return False

def test_database_connection():
    """Test connessione database"""
    print("\n🧪 Test 3: Connessione database")
    try:
        import psycopg2
        database_url = os.environ.get('DATABASE_URL')
        
        if not database_url:
            print("❌ DATABASE_URL non configurato")
            return False
        
        conn = psycopg2.connect(database_url)
        cursor = conn.cursor()
        
        # Verifica che le tabelle esistano
        cursor.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public' 
            AND table_name IN ('user', 'payment_transactions')
        """)
        tables = cursor.fetchall()
        
        if len(tables) >= 2:
            print(f"✅ Database connesso")
            print(f"✅ Tabelle trovate: {', '.join([t[0] for t in tables])}")
            cursor.close()
            conn.close()
            return True
        else:
            print(f"⚠️ Alcune tabelle mancanti. Trovate: {tables}")
            cursor.close()
            conn.close()
            return False
            
    except Exception as e:
        print(f"❌ Errore connessione database: {e}")
        return False

def test_health():
    """Test health check API"""
    print("\n🧪 Test 4: Health Check API")
    try:
        response = requests.get(f"{API_BASE_URL}/health")
        response.raise_for_status()
        health = response.json()
        
        if health.get('status') == 'ok':
            print(f"✅ API funzionante")
            return True
        else:
            print(f"⚠️ API status: {health.get('status')}")
            return False
    except Exception as e:
        print(f"❌ Errore: {e}")
        return False

def main():
    """Esegue tutti i test"""
    print("=" * 60)
    print("🚀 Test Integrazione PayPal - Kimerika Evolution")
    print("=" * 60)
    
    results = []
    
    # Test health check
    results.append(("Health Check", test_health()))
    
    # Test configurazione PayPal
    results.append(("Configurazione PayPal", test_paypal_config()))
    
    # Test creazione ordine
    results.append(("Creazione Ordine", test_create_order()))
    
    # Test database
    results.append(("Connessione Database", test_database_connection()))
    
    # Riepilogo
    print("\n" + "=" * 60)
    print("📊 RIEPILOGO TEST")
    print("=" * 60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} - {name}")
    
    print("\n" + "=" * 60)
    print(f"Risultato finale: {passed}/{total} test passati")
    
    if passed == total:
        print("🎉 Tutti i test superati! L'integrazione PayPal è pronta.")
    else:
        print("⚠️ Alcuni test non sono passati. Controlla la configurazione.")
    print("=" * 60)

if __name__ == "__main__":
    main()
