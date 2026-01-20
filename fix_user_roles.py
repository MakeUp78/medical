#!/usr/bin/env python3
"""Fix user roles"""
from auth_server import app, db, User

with app.app_context():
    users = User.query.filter(User.role.is_(None)).all()
    print(f'Utenti con role NULL: {len(users)}')
    for u in users:
        u.role = 'user'
        print(f'Impostato role=user per {u.email}')
    db.session.commit()
    print('✅ Aggiornamento completato!')
    
    # Verifica
    all_users = User.query.all()
    print(f'\nTotale utenti: {len(all_users)}')
    for u in all_users:
        print(f'{u.id}. {u.email} - role: {u.role}')
