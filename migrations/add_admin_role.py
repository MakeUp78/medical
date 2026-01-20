"""
Migration: Aggiunge il campo role al modello User e crea la tabella admin_audit_log
Eseguire: python migrations/add_admin_role.py
"""
import sys
import os

# Aggiungi la directory principale al path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from auth_server import app, db, User

def migrate():
    """Esegue la migrazione del database"""
    with app.app_context():
        print("Avvio migrazione...")

        # Verifica se la colonna role esiste gia
        from sqlalchemy import inspect
        inspector = inspect(db.engine)
        columns = [col['name'] for col in inspector.get_columns('user')]

        if 'role' not in columns:
            print("Aggiunta colonna 'role' alla tabella user...")
            db.engine.execute("ALTER TABLE \"user\" ADD COLUMN role VARCHAR(20) DEFAULT 'user' NOT NULL")
            print("Colonna 'role' aggiunta con successo!")
        else:
            print("Colonna 'role' gia esistente, skip...")

        # Crea tabella admin_audit_log se non esiste
        tables = inspector.get_table_names()
        if 'admin_audit_log' not in tables:
            print("Creazione tabella 'admin_audit_log'...")
            db.engine.execute("""
                CREATE TABLE IF NOT EXISTS admin_audit_log (
                    id SERIAL PRIMARY KEY,
                    admin_id INTEGER NOT NULL REFERENCES "user"(id),
                    action VARCHAR(100) NOT NULL,
                    target_user_id INTEGER REFERENCES "user"(id),
                    details JSON,
                    ip_address VARCHAR(45),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            print("Tabella 'admin_audit_log' creata con successo!")

            # Crea indici
            print("Creazione indici...")
            db.engine.execute("CREATE INDEX IF NOT EXISTS idx_audit_admin_id ON admin_audit_log(admin_id)")
            db.engine.execute("CREATE INDEX IF NOT EXISTS idx_audit_created_at ON admin_audit_log(created_at)")
            print("Indici creati con successo!")
        else:
            print("Tabella 'admin_audit_log' gia esistente, skip...")

        print("\nMigrazione completata con successo!")


def promote_to_admin(email):
    """Promuove un utente esistente a ruolo admin"""
    with app.app_context():
        user = User.query.filter_by(email=email.lower().strip()).first()

        if not user:
            print(f"Errore: Utente con email '{email}' non trovato!")
            return False

        if user.role == 'admin':
            print(f"L'utente {user.firstname} {user.lastname} ({email}) e gia admin.")
            return True

        user.role = 'admin'
        db.session.commit()

        print(f"\nUtente promosso a admin con successo!")
        print(f"  Nome: {user.firstname} {user.lastname}")
        print(f"  Email: {user.email}")
        print(f"  Ruolo: {user.role}")
        return True


def list_users():
    """Elenca tutti gli utenti nel database"""
    with app.app_context():
        users = User.query.all()

        if not users:
            print("Nessun utente trovato nel database.")
            return

        print(f"\nUtenti nel database ({len(users)} totali):")
        print("-" * 60)
        for u in users:
            role_badge = "[ADMIN]" if u.role == 'admin' else ""
            print(f"  {u.id}. {u.firstname} {u.lastname} - {u.email} {role_badge}")
        print("-" * 60)


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='Migrazione database per admin dashboard')
    parser.add_argument('--migrate', action='store_true', help='Esegui migrazione schema')
    parser.add_argument('--promote', type=str, help='Promuovi utente a admin (email)')
    parser.add_argument('--list', action='store_true', help='Elenca tutti gli utenti')

    args = parser.parse_args()

    if args.migrate:
        migrate()
    elif args.promote:
        promote_to_admin(args.promote)
    elif args.list:
        list_users()
    else:
        # Se nessun argomento, mostra help e esegui migrazione
        print("Uso:")
        print("  python add_admin_role.py --migrate          # Esegui migrazione")
        print("  python add_admin_role.py --list             # Elenca utenti")
        print("  python add_admin_role.py --promote EMAIL    # Promuovi utente a admin")
        print("")

        # Esegui migrazione di default
        migrate()
