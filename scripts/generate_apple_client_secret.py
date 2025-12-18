#!/usr/bin/env python3
"""
Script per generare il Client Secret per Apple Sign In
Apple richiede un JWT firmato come client secret che scade dopo 6 mesi
"""

import jwt
import time
import os
from datetime import datetime, timedelta

def generate_apple_client_secret():
    """
    Genera un JWT valido come client secret per Apple Sign In
    """
    
    print("=" * 60)
    print("  🍎 Generatore Client Secret Apple Sign In")
    print("=" * 60)
    print()
    
    # Raccolta informazioni
    team_id = input("Team ID (10 caratteri, es: ABC123XYZ): ").strip()
    client_id = input("Client ID/Service ID (es: com.kimerika.cloud.signin): ").strip()
    key_id = input("Key ID (10 caratteri, es: ABCDEFGHIJ): ").strip()
    key_file = input("Path alla chiave privata (.p8) (es: AuthKey_ABCDEFGHIJ.p8): ").strip()
    
    # Validazione
    if len(team_id) != 10:
        print("❌ Errore: Team ID deve essere esattamente 10 caratteri")
        return
    
    if len(key_id) != 10:
        print("❌ Errore: Key ID deve essere esattamente 10 caratteri")
        return
    
    if not os.path.exists(key_file):
        print(f"❌ Errore: File chiave non trovato: {key_file}")
        return
    
    # Leggi la chiave privata
    try:
        with open(key_file, 'r') as f:
            private_key = f.read()
    except Exception as e:
        print(f"❌ Errore nella lettura del file: {e}")
        return
    
    # Genera JWT
    try:
        headers = {
            'kid': key_id,
            'alg': 'ES256'
        }
        
        # Token valido per 6 mesi (massimo consentito da Apple)
        expiration_time = int(time.time()) + (86400 * 180)  # 180 giorni
        
        payload = {
            'iss': team_id,
            'iat': int(time.time()),
            'exp': expiration_time,
            'aud': 'https://appleid.apple.com',
            'sub': client_id
        }
        
        client_secret = jwt.encode(
            payload, 
            private_key, 
            algorithm='ES256', 
            headers=headers
        )
        
        # Mostra risultati
        print()
        print("=" * 60)
        print("  ✅ Client Secret Generato con Successo!")
        print("=" * 60)
        print()
        print("📋 Aggiungi queste righe al tuo file .env:")
        print()
        print(f"APPLE_CLIENT_ID={client_id}")
        print(f"APPLE_CLIENT_SECRET={client_secret}")
        print(f"APPLE_TEAM_ID={team_id}")
        print(f"APPLE_KEY_ID={key_id}")
        print()
        
        expiration_date = datetime.fromtimestamp(expiration_time)
        print(f"⏰ Scadenza: {expiration_date.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"   (in {(expiration_date - datetime.now()).days} giorni)")
        print()
        print("⚠️  NOTA: Rigenera il client secret prima della scadenza!")
        print()
        
        # Salva in un file
        output_file = "apple_client_secret.txt"
        with open(output_file, 'w') as f:
            f.write(f"# Apple Sign In Client Secret\n")
            f.write(f"# Generato: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"# Scadenza: {expiration_date.strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            f.write(f"APPLE_CLIENT_ID={client_id}\n")
            f.write(f"APPLE_CLIENT_SECRET={client_secret}\n")
            f.write(f"APPLE_TEAM_ID={team_id}\n")
            f.write(f"APPLE_KEY_ID={key_id}\n")
        
        print(f"💾 Configurazione salvata in: {output_file}")
        print("   (Ricorda di aggiungere questo file a .gitignore!)")
        print()
        
    except Exception as e:
        print(f"❌ Errore nella generazione del JWT: {e}")
        print()
        print("Verifica che:")
        print("  1. La chiave privata sia nel formato corretto (.p8)")
        print("  2. Il modulo 'jwt' sia installato: pip install PyJWT")
        print("  3. Il modulo 'cryptography' sia installato: pip install cryptography")
        return


if __name__ == "__main__":
    try:
        generate_apple_client_secret()
    except KeyboardInterrupt:
        print("\n\n❌ Operazione annullata dall'utente")
    except Exception as e:
        print(f"\n\n❌ Errore imprevisto: {e}")
