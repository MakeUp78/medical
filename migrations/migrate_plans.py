#!/usr/bin/env python3
"""
Script di migrazione per aggiornare i piani utenti da legacy a nuovi piani.

Mappatura:
- starter -> none (piano gratuito eliminato, ora nessun piano)
- professional -> monthly (piano professionale diventa mensile)
- enterprise -> annual (piano enterprise diventa annuale)

Esegui con: python migrate_plans.py
"""

import os
import sys

# Aggiungi il percorso parent per importare auth_server
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from auth_server import app, db, User

# Mappatura piani legacy -> nuovi piani
PLAN_MIGRATION = {
    'starter': 'none',
    'professional': 'monthly',
    'enterprise': 'annual'
}

# Limiti analisi per i nuovi piani
PLAN_LIMITS = {
    'none': 0,
    'monthly': -1,  # Illimitato
    'annual': -1    # Illimitato
}


def migrate_plans(dry_run=True):
    """
    Migra tutti gli utenti dai piani legacy ai nuovi piani.

    Args:
        dry_run: Se True, mostra solo cosa farebbe senza modificare il DB
    """
    with app.app_context():
        # Conta utenti per piano prima della migrazione
        print("=" * 60)
        print("MIGRAZIONE PIANI UTENTI")
        print("=" * 60)
        print()

        print("Situazione attuale:")
        for plan in ['starter', 'professional', 'enterprise', 'none', 'monthly', 'annual']:
            count = User.query.filter_by(plan=plan).count()
            if count > 0:
                print(f"  - {plan}: {count} utenti")

        print()
        print("-" * 60)
        print()

        # Trova utenti con piani legacy
        legacy_users = User.query.filter(User.plan.in_(['starter', 'professional', 'enterprise'])).all()

        if not legacy_users:
            print("Nessun utente con piano legacy trovato.")
            print("La migrazione non è necessaria.")
            return

        print(f"Trovati {len(legacy_users)} utenti con piani legacy da migrare:")
        print()

        migrated_count = 0
        for user in legacy_users:
            old_plan = user.plan
            new_plan = PLAN_MIGRATION.get(old_plan)

            if new_plan:
                print(f"  ID: {user.id}")
                print(f"    Email: {user.email}")
                print(f"    Nome: {user.firstname} {user.lastname}")
                print(f"    Piano: {old_plan} -> {new_plan}")
                print(f"    Limite analisi: {user.analyses_limit} -> {PLAN_LIMITS[new_plan]}")

                if not dry_run:
                    user.plan = new_plan
                    user.analyses_limit = PLAN_LIMITS[new_plan]
                    migrated_count += 1

                print()

        if dry_run:
            print("-" * 60)
            print()
            print("MODALITA' DRY RUN - Nessuna modifica effettuata")
            print("Per applicare le modifiche, esegui con --execute")
        else:
            # Commit delle modifiche
            db.session.commit()
            print("-" * 60)
            print()
            print(f"MIGRAZIONE COMPLETATA!")
            print(f"Migrati {migrated_count} utenti.")

        print()
        print("Situazione dopo migrazione:")
        for plan in ['none', 'monthly', 'annual']:
            count = User.query.filter_by(plan=plan).count()
            print(f"  - {plan}: {count} utenti")


def show_users_by_plan():
    """Mostra tutti gli utenti raggruppati per piano."""
    with app.app_context():
        print("=" * 60)
        print("UTENTI PER PIANO")
        print("=" * 60)
        print()

        for plan in ['none', 'monthly', 'annual', 'starter', 'professional', 'enterprise']:
            users = User.query.filter_by(plan=plan).all()
            if users:
                print(f"\n{plan.upper()} ({len(users)} utenti):")
                print("-" * 40)
                for user in users:
                    status = "attivo" if user.is_active else "disattivato"
                    print(f"  - {user.email} ({user.firstname} {user.lastname}) [{status}]")


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='Migra piani utenti da legacy a nuovi')
    parser.add_argument('--execute', action='store_true',
                        help='Esegue la migrazione (default: dry run)')
    parser.add_argument('--list', action='store_true',
                        help='Mostra utenti per piano senza migrare')

    args = parser.parse_args()

    if args.list:
        show_users_by_plan()
    else:
        migrate_plans(dry_run=not args.execute)
