#!/usr/bin/env python3
"""
Kimerika Cloud - Script di Cleanup Server
==========================================
Risolve problemi di processi duplicati e file PID obsoleti.
Uso: python3 cleanup_servers.py [auth|all]

Risolve specialmente il problema del doppio processo auth che causa 
il fallimento del primo tentativo di login.
"""

import os
import sys
import psutil
from pathlib import Path
import signal

BASE_DIR = Path(__file__).parent

# Configurazione server e relativi file PID
SERVERS = {
    'auth': {
        'name': 'Auth Server',
        'pid_file': BASE_DIR / '.auth_server.pid',
        'port': 5000,
        'script_patterns': ['auth_server.py']
    },
    'api': {
        'name': 'API Server',
        'pid_file': BASE_DIR / '.api_server.pid',
        'port': 8001,
        'script_patterns': ['uvicorn', 'webapp.api.main:app']
    },
    'webapp': {
        'name': 'WebApp Server',
        'pid_file': BASE_DIR / '.webapp_server.pid',
        'port': 3000,
        'script_patterns': ['start_webapp.py']
    },
    'websocket': {
        'name': 'WebSocket Server',
        'pid_file': BASE_DIR / '.websocket_server.pid',
        'port': 8765,
        'script_patterns': ['websocket_frame_api.py']
    }
}


def find_processes_by_pattern(patterns):
    """Trova tutti i processi che corrispondono ai pattern"""
    matching_procs = []
    
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            cmdline_str = ' '.join(proc.cmdline())
            if any(pattern in cmdline_str for pattern in patterns):
                matching_procs.append(proc)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    
    return matching_procs


def cleanup_server(server_key, force_kill=False):
    """
    Pulisce un server specifico:
    1. Trova tutti i processi con pattern corrispondente
    2. Termina i processi duplicati (lascia solo uno attivo se richiesto)
    3. Rimuove file PID obsoleti
    4. Verifica porte occupate e le libera se necessario
    """
    server = SERVERS[server_key]
    print(f"\n🔍 Analisi {server['name']}...")

    # NUOVO: Verifica porta occupata prima di tutto
    import socket
    port_occupied = False
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        result = sock.connect_ex(('127.0.0.1', server['port']))
        sock.close()
        port_occupied = (result == 0)

        if port_occupied:
            print(f"   ⚠️  Porta {server['port']} è occupata")
    except Exception as e:
        print(f"   ⚠️  Errore verifica porta: {e}")

    # Trova processi attivi
    procs = find_processes_by_pattern(server['script_patterns'])
    
    if not procs:
        print(f"   ✅ Nessun processo {server['name']} attivo")
        
        # Rimuovi PID file se esiste
        if server['pid_file'].exists():
            server['pid_file'].unlink()
            print(f"   🧹 File PID obsoleto rimosso: {server['pid_file']}")
        
        return True
    
    # Se c'è UN SOLO processo, controlla coerenza con PID file
    if len(procs) == 1 and not force_kill:
        proc = procs[0]
        print(f"   ℹ  Processo singolo trovato (PID: {proc.pid})")
        
        # Verifica PID file
        if server['pid_file'].exists():
            try:
                with open(server['pid_file'], 'r') as f:
                    recorded_pid = int(f.read().strip())
                
                if recorded_pid == proc.pid:
                    print(f"   ✅ PID file coerente - tutto OK")
                    return True
                else:
                    print(f"   ⚠  PID file non corrisponde ({recorded_pid} vs {proc.pid})")
                    print(f"   🧹 Aggiorno PID file...")
                    with open(server['pid_file'], 'w') as f:
                        f.write(str(proc.pid))
                    print(f"   ✅ PID file aggiornato")
                    return True
            except (ValueError, IOError) as e:
                print(f"   ⚠  Errore lettura PID file: {e}")
                server['pid_file'].unlink()
        else:
            # Crea PID file mancante
            print(f"   ⚠  File PID mancante, lo creo...")
            with open(server['pid_file'], 'w') as f:
                f.write(str(proc.pid))
            print(f"   ✅ PID file creato")
        
        return True
    
    # PROBLEMA: Processi multipli o force_kill richiesto
    if len(procs) > 1 and not force_kill:
        # Verifica se sono padre + reloader Flask (normale in debug mode)
        if len(procs) == 2 and server_key == 'auth':
            # Controlla se hanno PPID padre-figlio
            try:
                pids = [p.pid for p in procs]
                ppids = [p.ppid() for p in procs]
                
                # Se uno è padre dell'altro, è Flask reloader (OK)
                if pids[0] in ppids or pids[1] in ppids:
                    print(f"   ℹ  2 processi trovati (Flask padre + reloader - normale in debug mode)")
                    # Aggiorna PID file con il padre
                    parent_pid = pids[0] if pids[0] not in ppids[1:] else pids[1]
                    if server['pid_file'].exists():
                        with open(server['pid_file'], 'r') as f:
                            recorded_pid = int(f.read().strip())
                        if recorded_pid == parent_pid:
                            print(f"   ✅ Sistema normale - tutto OK")
                            return True
                    # PID file mancante o non corrispondente
                    with open(server['pid_file'], 'w') as f:
                        f.write(str(parent_pid))
                    print(f"   ✅ PID file aggiornato (padre: {parent_pid})")
                    return True
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        
        # Vero problema: istanze multiple indipendenti
        print(f"   ❌ PROBLEMA: {len(procs)} processi duplicati trovati!")
        print(f"      Questo causa il problema del doppio login!")
    
    print(f"   🛑 Termino {'tutti i processi' if force_kill or len(procs) > 1 else 'processi extra'}...")
    
    killed_count = 0
    for proc in procs:
        try:
            print(f"      - Termino PID {proc.pid}...", end=' ')
            proc.terminate()
            
            # Attendi terminazione graceful
            try:
                proc.wait(timeout=3)
                print("✓")
                killed_count += 1
            except psutil.TimeoutExpired:
                # Forza terminazione
                print("(forzato)...", end=' ')
                proc.kill()
                proc.wait(timeout=2)
                print("✓")
                killed_count += 1
                
        except (psutil.NoSuchProcess, psutil.AccessDenied) as e:
            print(f"✗ ({e})")
    
    # Rimuovi PID file
    if server['pid_file'].exists():
        server['pid_file'].unlink()
        print(f"   🧹 File PID rimosso")
    
    print(f"   ✅ {killed_count} processo/i terminato/i")
    return True


def cleanup_all_servers(force_kill=False):
    """Pulisce tutti i server"""
    print("=" * 60)
    print("  KIMERIKA CLOUD - CLEANUP SERVER")
    print("=" * 60)
    
    if force_kill:
        print("⚠  MODALITÀ FORCE: terminerò tutti i processi")
    
    for server_key in SERVERS:
        cleanup_server(server_key, force_kill)
    
    print("\n" + "=" * 60)
    print("✅ Cleanup completato!")
    print("=" * 60)


def show_status():
    """Mostra lo stato di tutti i server"""
    print("=" * 60)
    print("  STATO SERVER KIMERIKA CLOUD")
    print("=" * 60)
    
    for server_key, server in SERVERS.items():
        print(f"\n📊 {server['name']} (Porta {server['port']})")
        
        procs = find_processes_by_pattern(server['script_patterns'])
        
        if not procs:
            print("   ⚪ FERMO")
        elif len(procs) == 1:
            print(f"   🟢 ATTIVO (PID: {procs[0].pid})")
        elif len(procs) == 2 and server_key == 'auth':
            # Verifica se sono padre + reloader Flask
            try:
                pids = [p.pid for p in procs]
                ppids = [p.ppid() for p in procs]
                
                # Se uno è padre dell'altro, è Flask reloader (OK)
                if pids[0] in ppids or pids[1] in ppids:
                    parent_pid = pids[0] if pids[0] not in ppids[1:] else pids[1]
                    print(f"   🟢 ATTIVO (PID: {parent_pid} + reloader)")
                else:
                    print(f"   🔴 DUPLICATI ({len(procs)} processi) - PROBLEMA!")
                    for proc in procs:
                        print(f"      - PID: {proc.pid}")
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                print(f"   🔴 DUPLICATI ({len(procs)} processi) - PROBLEMA!")
                for proc in procs:
                    print(f"      - PID: {proc.pid}")
        else:
            print(f"   🔴 DUPLICATI ({len(procs)} processi) - PROBLEMA!")
            for proc in procs:
                print(f"      - PID: {proc.pid}")
        
        # Verifica PID file
        if server['pid_file'].exists():
            try:
                with open(server['pid_file'], 'r') as f:
                    pid = int(f.read().strip())
                
                if psutil.pid_exists(pid):
                    print(f"   📄 PID file: {pid} (✓ processo attivo)")
                else:
                    print(f"   📄 PID file: {pid} (✗ processo non esiste - OBSOLETO)")
            except (ValueError, IOError):
                print(f"   📄 PID file: corrotto")
        else:
            if procs:
                print(f"   📄 PID file: ⚠ mancante")
    
    print("\n" + "=" * 60)


def main():
    if len(sys.argv) < 2:
        print("Uso: python3 cleanup_servers.py [comando]")
        print("\nComandi:")
        print("  auth      - Pulisce solo auth server (risolve problema doppio login)")
        print("  all       - Pulisce tutti i server")
        print("  force     - Termina TUTTI i processi di tutti i server")
        print("  status    - Mostra stato server senza modifiche")
        print("\nEsempio:")
        print("  python3 cleanup_servers.py auth")
        sys.exit(1)
    
    cmd = sys.argv[1].lower()
    
    if cmd == 'status':
        show_status()
    elif cmd == 'auth':
        print("🎯 Cleanup Auth Server (risolve problema doppio login)")
        cleanup_server('auth', force_kill=True)
    elif cmd == 'all':
        cleanup_all_servers(force_kill=False)
    elif cmd == 'force':
        print("⚠️  ATTENZIONE: Terminerò TUTTI i server in esecuzione!")
        # Se stdin non è TTY (es. chiamato da script), procedi senza chiedere
        if not sys.stdin.isatty():
            print("   (Script mode - procedo senza conferma)")
            cleanup_all_servers(force_kill=True)
        else:
            response = input("Confermi? (sì/no): ")
            if response.lower() in ['sì', 'si', 'yes', 'y', 's']:
                cleanup_all_servers(force_kill=True)
            else:
                print("❌ Operazione annullata")
    else:
        print(f"❌ Comando non riconosciuto: {cmd}")
        sys.exit(1)


if __name__ == '__main__':
    main()
