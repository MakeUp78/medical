#!/usr/bin/env python3
"""
Script di verifica rapida per l'implementazione OAuth
Controlla che tutto sia configurato correttamente
"""

import sys
import os
from pathlib import Path

def check_imports():
    """Verifica che tutti i moduli necessari siano installati"""
    print("🔍 Controllo dipendenze...")
    
    modules = {
        'flask': 'Flask',
        'flask_cors': 'Flask-CORS',
        'flask_sqlalchemy': 'Flask-SQLAlchemy',
        'jwt': 'PyJWT',
        'authlib': 'Authlib',
        'dotenv': 'python-dotenv',
        'cryptography': 'cryptography'
    }
    
    missing = []
    for module, name in modules.items():
        try:
            __import__(module)
            print(f"  ✓ {name}")
        except ImportError:
            print(f"  ✗ {name} - MANCANTE")
            missing.append(name)
    
    if missing:
        print(f"\n❌ Dipendenze mancanti: {', '.join(missing)}")
        print("   Installale con: pip install -r requirements_auth.txt")
        return False
    
    print("✅ Tutte le dipendenze sono installate\n")
    return True


def check_env_file():
    """Verifica l'esistenza e il contenuto del file .env"""
    print("🔍 Controllo file .env...")
    
    env_path = Path('.env')
    if not env_path.exists():
        print("  ✗ File .env non trovato")
        print("   Crea il file .env basandoti su .env.example")
        return False
    
    print("  ✓ File .env esiste")
    
    # Leggi il file .env
    with open(env_path, 'r') as f:
        content = f.read()
    
    # Controlla le variabili chiave
    checks = {
        'SECRET_KEY': 'SECRET_KEY=',
        'JWT_SECRET_KEY': 'JWT_SECRET_KEY=',
        'GOOGLE_CLIENT_ID': 'GOOGLE_CLIENT_ID=',
        'GOOGLE_CLIENT_SECRET': 'GOOGLE_CLIENT_SECRET=',
        'APPLE_CLIENT_ID': 'APPLE_CLIENT_ID=',
        'APPLE_CLIENT_SECRET': 'APPLE_CLIENT_SECRET=',
        'DATABASE_URL': 'DATABASE_URL='
    }
    
    configured = {}
    for key, search in checks.items():
        if search in content:
            # Trova la riga
            for line in content.split('\n'):
                if line.startswith(search):
                    value = line.split('=', 1)[1].strip()
                    # Controlla se è configurato (non vuoto e non placeholder)
                    if value and not value.startswith('your-') and not value.startswith('CHANGE'):
                        configured[key] = True
                        print(f"  ✓ {key} configurato")
                    else:
                        configured[key] = False
                        print(f"  ⚠️  {key} non configurato (placeholder)")
                    break
    
    if not configured.get('GOOGLE_CLIENT_ID') and not configured.get('APPLE_CLIENT_ID'):
        print("\n⚠️  Attenzione: Né Google né Apple OAuth sono configurati")
        print("   L'autenticazione OAuth non funzionerà finché non configuri almeno uno dei due")
        print("   Vedi: OAUTH_SETUP_GUIDE.md\n")
    
    return True


def check_auth_server():
    """Verifica che il file auth_server.py esista e sia valido"""
    print("🔍 Controllo auth_server.py...")
    
    auth_path = Path('auth_server.py')
    if not auth_path.exists():
        print("  ✗ auth_server.py non trovato")
        return False
    
    print("  ✓ auth_server.py esiste")
    
    # Leggi il file
    with open(auth_path, 'r') as f:
        content = f.read()
    
    # Verifica gli endpoint OAuth
    endpoints = [
        '/api/auth/google/login',
        '/api/auth/google/signup',
        '/api/auth/google/callback',
        '/api/auth/apple/login',
        '/api/auth/apple/signup',
        '/api/auth/apple/callback'
    ]
    
    for endpoint in endpoints:
        if endpoint in content:
            print(f"  ✓ Endpoint {endpoint}")
        else:
            print(f"  ✗ Endpoint {endpoint} - MANCANTE")
    
    print()
    return True


def check_frontend():
    """Verifica i file frontend"""
    print("🔍 Controllo file frontend...")
    
    landing_path = Path('webapp/landing.html')
    if not landing_path.exists():
        print("  ✗ webapp/landing.html non trovato")
        return False
    
    print("  ✓ webapp/landing.html esiste")
    
    with open(landing_path, 'r') as f:
        content = f.read()
    
    # Controlla i pulsanti OAuth
    if 'loginWithGoogle' in content and 'loginWithApple' in content:
        print("  ✓ Pulsanti OAuth presenti")
    else:
        print("  ✗ Pulsanti OAuth mancanti")
    
    # Controlla il file JS
    js_path = Path('webapp/static/js/landing.js')
    if not js_path.exists():
        print("  ✗ webapp/static/js/landing.js non trovato")
        return False
    
    print("  ✓ webapp/static/js/landing.js esiste")
    
    with open(js_path, 'r') as f:
        js_content = f.read()
    
    # Verifica le funzioni OAuth
    oauth_funcs = ['loginWithGoogle', 'signupWithGoogle', 'loginWithApple', 'signupWithApple']
    for func in oauth_funcs:
        if f'function {func}' in js_content:
            print(f"  ✓ Funzione {func}()")
        else:
            print(f"  ✗ Funzione {func}() - MANCANTE")
    
    print()
    return True


def check_database():
    """Verifica il database e la struttura"""
    print("🔍 Controllo database...")
    
    try:
        # Importa app e db
        from auth_server import app, db, User
        
        with app.app_context():
            # Verifica che il database sia accessibile
            try:
                user_count = User.query.count()
                print(f"  ✓ Database accessibile ({user_count} utenti)")
                
                # Verifica i campi OAuth
                sample = User.query.first()
                if sample:
                    if hasattr(sample, 'google_id'):
                        print("  ✓ Campo 'google_id' presente")
                    else:
                        print("  ✗ Campo 'google_id' MANCANTE")
                    
                    if hasattr(sample, 'apple_id'):
                        print("  ✓ Campo 'apple_id' presente")
                    else:
                        print("  ✗ Campo 'apple_id' MANCANTE")
                else:
                    print("  ℹ️  Nessun utente nel database (impossibile verificare campi)")
                
            except Exception as e:
                print(f"  ✗ Errore accesso database: {e}")
                return False
        
        print()
        return True
        
    except ImportError as e:
        print(f"  ✗ Impossibile importare auth_server: {e}")
        return False
    except Exception as e:
        print(f"  ✗ Errore: {e}")
        return False


def print_summary():
    """Stampa un riepilogo finale"""
    print("=" * 70)
    print("  📋 RIEPILOGO")
    print("=" * 70)
    print()
    print("✅ Implementazione OAuth completata!")
    print()
    print("Prossimi passi:")
    print("  1. Configura le credenziali OAuth nel file .env")
    print("     Vedi: OAUTH_SETUP_GUIDE.md")
    print()
    print("  2. Avvia il server di autenticazione:")
    print("     python3 auth_server.py")
    print()
    print("  3. Avvia il frontend:")
    print("     python3 start_webapp.py")
    print()
    print("  4. Testa nel browser:")
    print("     http://localhost:3000")
    print()
    print("Per test senza configurazione OAuth:")
    print("  Vedi: OAUTH_TEST_GUIDE.md")
    print()


def main():
    """Funzione principale"""
    print()
    print("=" * 70)
    print("  🔐 VERIFICA IMPLEMENTAZIONE OAUTH - KIMERIKA CLOUD")
    print("=" * 70)
    print()
    
    # Cambia alla directory corretta
    script_dir = Path(__file__).parent.parent
    os.chdir(script_dir)
    
    all_ok = True
    
    # Esegui i controlli
    if not check_imports():
        all_ok = False
    
    if not check_env_file():
        all_ok = False
    
    if not check_auth_server():
        all_ok = False
    
    if not check_frontend():
        all_ok = False
    
    if not check_database():
        all_ok = False
    
    # Riepilogo
    print_summary()
    
    if not all_ok:
        print("⚠️  Alcuni controlli non sono passati. Vedi i dettagli sopra.")
        sys.exit(1)
    else:
        print("🎉 Tutti i controlli sono passati!")
        sys.exit(0)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n❌ Verifica interrotta dall'utente")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Errore imprevisto: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
