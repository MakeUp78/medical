#!/usr/bin/env python3
"""
Script di test per verificare la funzionalità della dashboard admin
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from auth_server import app, db, User, UserActivity, AdminAuditLog
import datetime

def test_models():
    """Testa che i modelli siano accessibili"""
    print("🧪 Test Modelli...")
    with app.app_context():
        # Test User model
        user_count = User.query.count()
        print(f"  ✅ User model OK - {user_count} utenti nel database")
        
        # Test UserActivity model
        activity_count = UserActivity.query.count()
        print(f"  ✅ UserActivity model OK - {activity_count} attività tracciate")
        
        # Test AdminAuditLog model
        audit_count = AdminAuditLog.query.count()
        print(f"  ✅ AdminAuditLog model OK - {audit_count} log audit")
        
        # Check for admin users
        admin_count = User.query.filter_by(role='admin').count()
        if admin_count > 0:
            print(f"  ✅ Trovati {admin_count} admin nel sistema")
            # List admin emails
            admins = User.query.filter_by(role='admin').all()
            for admin in admins:
                print(f"     👤 Admin: {admin.email}")
        else:
            print("  ⚠️  Nessun admin trovato! Crea un admin prima di testare la dashboard.")
            print("     Usa: python3 -c \"from auth_server import app, db, User; ...")
    
    print("")

def test_endpoints():
    """Verifica che gli endpoint esistano"""
    print("🧪 Test Endpoint API...")
    with app.app_context():
        # Get all registered routes
        routes = []
        for rule in app.url_map.iter_rules():
            if 'admin' in rule.rule:
                routes.append(f"{rule.methods} {rule.rule}")
        
        print(f"  ✅ Trovati {len(routes)} endpoint admin:")
        for route in sorted(routes)[:10]:  # Show first 10
            print(f"     {route}")
        
        if len(routes) > 10:
            print(f"     ... e altri {len(routes) - 10} endpoint")
    
    print("")

def create_test_activity():
    """Crea alcune attività di test"""
    print("🧪 Creazione attività di test...")
    with app.app_context():
        # Get first user
        user = User.query.first()
        if not user:
            print("  ⚠️  Nessun utente trovato nel database")
            return
        
        # Check if test activities already exist
        existing = UserActivity.query.filter_by(
            user_id=user.id,
            action_type='test_activity'
        ).count()
        
        if existing > 0:
            print(f"  ℹ️  {existing} attività di test già presenti")
        else:
            # Create test activities
            for action_type in ['login', 'image_upload', 'video_upload', 'webcam_start']:
                activity = UserActivity(
                    user_id=user.id,
                    action_type=action_type,
                    action_details={'test': True},
                    ip_address='127.0.0.1',
                    user_agent='Test Script'
                )
                db.session.add(activity)
            
            db.session.commit()
            print("  ✅ Attività di test create con successo!")
    
    print("")

def test_analytics_data():
    """Verifica che ci siano dati per analytics"""
    print("🧪 Test Dati Analytics...")
    with app.app_context():
        # Count activities by type
        activity_types = db.session.query(
            UserActivity.action_type,
            db.func.count(UserActivity.id)
        ).group_by(UserActivity.action_type).all()
        
        if activity_types:
            print(f"  ✅ Dati analytics disponibili:")
            for action_type, count in activity_types:
                print(f"     {action_type}: {count} attività")
        else:
            print("  ⚠️  Nessuna attività tracciata ancora")
            print("     Usa la webapp per generare dati, oppure crea dati di test")
    
    print("")

def main():
    """Esegue tutti i test"""
    print("=" * 60)
    print("🧪 TEST ADMIN DASHBOARD - Kimerika Evolution")
    print("=" * 60)
    print("")
    
    try:
        test_models()
        test_endpoints()
        
        # Ask to create test data
        print("Vuoi creare dati di test per analytics? (s/n): ", end='')
        response = input().strip().lower()
        if response == 's':
            create_test_activity()
        
        test_analytics_data()
        
        print("=" * 60)
        print("✅ TUTTI I TEST COMPLETATI!")
        print("=" * 60)
        print("")
        print("📋 Prossimi passi:")
        print("  1. Avvia il server: python3 auth_server.py")
        print("  2. Login come admin nella webapp")
        print("  3. Vai su Profilo → Sezione 'Admin Dashboard'")
        print("  4. Apri admin.html → Sezione 'Statistiche'")
        print("  5. Verifica i grafici e le statistiche")
        print("")
        
    except Exception as e:
        print(f"❌ Errore durante i test: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    return True

if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)
