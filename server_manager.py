#!/usr/bin/env python3
"""
Kimerika Cloud - Gestore Unificato Server
==========================================
Script centralizzato per la gestione di tutti i server dell'applicazione.
Indipendente da configurazioni esterne, autocontenuto.

Server gestiti:
1. API Server (FastAPI) - porta 8001
2. WebApp Server (start_webapp.py) - porta 3000
3. WebSocket Server - porta 8765
4. Auth Server (opzionale) - porta 5000

Utilizzo:
    python server_manager.py start   # Avvia tutti i server
    python server_manager.py stop    # Ferma tutti i server
    python server_manager.py restart # Riavvia tutti i server
    python server_manager.py status  # Mostra stato server
"""

import os
import sys
import time
import signal
import subprocess
import socket
import psutil
import json
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime

# ========== CONFIGURAZIONE ==========
# Tutti i percorsi sono relativi a questo file
BASE_DIR = Path(__file__).parent.absolute()

SERVER_CONFIG = {
    "api_server": {
        "name": "API Server (FastAPI)",
        "port": 8001,
        "command": [
            sys.executable, "-m", "uvicorn",
            "webapp.api.main:app",
            "--host", "0.0.0.0",
            "--port", "8001",
            "--reload"
        ],
        "cwd": BASE_DIR,
        "log_file": "api_server.log",
        "pid_file": ".api_server.pid",
        "required": True,
        "startup_delay": 2
    },
    "webapp_server": {
        "name": "WebApp Server",
        "port": 3000,
        "command": [sys.executable, "start_webapp.py"],
        "cwd": BASE_DIR,
        "log_file": "webapp_server.log",
        "pid_file": ".webapp_server.pid",
        "required": True,
        "startup_delay": 1
    },
    "websocket_server": {
        "name": "WebSocket Server",
        "port": 8765,
        "command": [
            sys.executable,
            "face-landmark-localization-master/websocket_frame_api.py"
        ],
        "cwd": BASE_DIR,
        "log_file": "websocket_server.log",
        "pid_file": ".websocket_server.pid",
        "required": True,
        "startup_delay": 1
    },
    "auth_server": {
        "name": "Auth Server",
        "port": 5000,
        "command": [sys.executable, "auth_server.py"],
        "cwd": BASE_DIR,
        "log_file": "auth_server.log",
        "pid_file": ".auth_server.pid",
        "required": False,  # Opzionale
        "startup_delay": 1
    }
}

# Colori per output terminale
class Colors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'

def print_header(text: str):
    """Stampa intestazione colorata"""
    print(f"\n{Colors.BOLD}{Colors.HEADER}{'=' * 60}")
    print(f"{text.center(60)}")
    print(f"{'=' * 60}{Colors.ENDC}\n")

def print_success(text: str):
    """Stampa messaggio di successo"""
    print(f"{Colors.OKGREEN}✓{Colors.ENDC} {text}")

def print_error(text: str):
    """Stampa messaggio di errore"""
    print(f"{Colors.FAIL}✗{Colors.ENDC} {text}")

def print_warning(text: str):
    """Stampa messaggio di warning"""
    print(f"{Colors.WARNING}⚠{Colors.ENDC} {text}")

def print_info(text: str):
    """Stampa messaggio informativo"""
    print(f"{Colors.OKCYAN}ℹ{Colors.ENDC} {text}")

def is_port_in_use(port: int) -> bool:
    """Verifica se una porta è in uso"""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind(('0.0.0.0', port))
            return False
        except OSError:
            return True

def get_process_using_port(port: int) -> Optional[psutil.Process]:
    """Trova il processo che sta usando una porta"""
    for proc in psutil.process_iter(['pid', 'name', 'connections']):
        try:
            for conn in proc.connections():
                if conn.laddr.port == port:
                    return proc
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    return None

def read_pid_file(pid_file: Path) -> Optional[int]:
    """Legge PID da file"""
    try:
        if pid_file.exists():
            with open(pid_file, 'r') as f:
                pid = int(f.read().strip())
                # Verifica se il processo esiste
                if psutil.pid_exists(pid):
                    return pid
                else:
                    # Rimuovi file PID stantio
                    pid_file.unlink()
    except (ValueError, OSError):
        pass
    return None

def write_pid_file(pid_file: Path, pid: int):
    """Scrive PID su file"""
    try:
        with open(pid_file, 'w') as f:
            f.write(str(pid))
    except OSError as e:
        print_error(f"Impossibile scrivere PID file: {e}")

def kill_process_by_pid(pid: int, timeout: int = 5) -> bool:
    """Termina processo per PID con timeout"""
    try:
        process = psutil.Process(pid)
        process.terminate()
        
        # Attendi che il processo termini
        gone, alive = psutil.wait_procs([process], timeout=timeout)
        
        if alive:
            # Forza terminazione
            process.kill()
            gone, alive = psutil.wait_procs([process], timeout=2)
            
        return len(alive) == 0
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        return True

def start_server(server_id: str, config: Dict) -> bool:
    """Avvia un singolo server"""
    print_info(f"Avvio {config['name']}...")
    
    # Verifica se la porta è già in uso
    if is_port_in_use(config['port']):
        proc = get_process_using_port(config['port'])
        if proc:
            print_warning(f"Porta {config['port']} già in uso da {proc.name()} (PID: {proc.pid})")
        else:
            print_warning(f"Porta {config['port']} già in uso")
        
        # Verifica se è il nostro server (tramite PID file)
        pid_file = BASE_DIR / config['pid_file']
        existing_pid = read_pid_file(pid_file)
        if existing_pid:
            print_info(f"{config['name']} già in esecuzione (PID: {existing_pid})")
            return True
        
        if not config['required']:
            print_warning(f"Skip {config['name']} (opzionale)")
            return True
        else:
            print_error(f"Impossibile avviare {config['name']}: porta occupata")
            return False
    
    # Verifica che il comando esista
    cmd_path = Path(config['cwd']) / config['command'][1]
    if not cmd_path.exists() and config['command'][1] != '-m':
        # Se non è un modulo Python (-m), verifica l'esistenza del file
        if not Path(config['cwd']) / config['command'][1].split('/')[-1]:
            print_error(f"File non trovato: {config['command'][1]}")
            if not config['required']:
                print_warning(f"Skip {config['name']} (opzionale)")
                return True
            return False
    
    # Apri log file
    log_path = BASE_DIR / config['log_file']
    try:
        log_file = open(log_path, 'a')
        log_file.write(f"\n{'='*60}\n")
        log_file.write(f"Avvio: {datetime.now().isoformat()}\n")
        log_file.write(f"Comando: {' '.join(config['command'])}\n")
        log_file.write(f"{'='*60}\n\n")
        log_file.flush()
    except OSError as e:
        print_error(f"Impossibile aprire log file: {e}")
        log_file = subprocess.DEVNULL
    
    # Avvia processo
    try:
        process = subprocess.Popen(
            config['command'],
            cwd=config['cwd'],
            stdout=log_file if log_file != subprocess.DEVNULL else subprocess.DEVNULL,
            stderr=subprocess.STDOUT if log_file != subprocess.DEVNULL else subprocess.DEVNULL,
            start_new_session=True  # Crea nuovo process group per isolamento
        )
        
        # Salva PID
        pid_file = BASE_DIR / config['pid_file']
        write_pid_file(pid_file, process.pid)
        
        # Attendi startup
        time.sleep(config.get('startup_delay', 1))
        
        # Verifica che il processo sia ancora attivo
        if process.poll() is not None:
            print_error(f"{config['name']} terminato immediatamente (exit code: {process.poll()})")
            if isinstance(log_file, type(open(''))):
                log_file.close()
            return False
        
        # Verifica che la porta sia ora in uso
        time.sleep(1)
        if not is_port_in_use(config['port']):
            print_warning(f"{config['name']} avviato ma porta {config['port']} non in ascolto")
            # Non è necessariamente un errore, alcuni server potrebbero richiedere più tempo
        
        print_success(f"{config['name']} avviato (PID: {process.pid}, porta: {config['port']})")
        
        if isinstance(log_file, type(open(''))):
            log_file.close()
        
        return True
        
    except FileNotFoundError:
        print_error(f"Comando non trovato: {config['command'][0]}")
        if isinstance(log_file, type(open(''))):
            log_file.close()
        return False
    except Exception as e:
        print_error(f"Errore avvio {config['name']}: {e}")
        if isinstance(log_file, type(open(''))):
            log_file.close()
        return False

def stop_server(server_id: str, config: Dict) -> bool:
    """Ferma un singolo server"""
    print_info(f"Arresto {config['name']}...")
    
    pid_file = BASE_DIR / config['pid_file']
    pid = read_pid_file(pid_file)
    
    if not pid:
        # Verifica se la porta è comunque in uso
        if is_port_in_use(config['port']):
            proc = get_process_using_port(config['port'])
            if proc:
                print_warning(f"Processo trovato sulla porta {config['port']} (PID: {proc.pid})")
                print_info(f"Tentativo di terminazione...")
                if kill_process_by_pid(proc.pid):
                    print_success(f"{config['name']} terminato")
                    return True
                else:
                    print_error(f"Impossibile terminare processo {proc.pid}")
                    return False
        else:
            print_info(f"{config['name']} non in esecuzione")
            return True
    
    # Termina processo
    if kill_process_by_pid(pid):
        # Rimuovi PID file
        try:
            pid_file.unlink()
        except OSError:
            pass
        
        print_success(f"{config['name']} terminato (PID: {pid})")
        return True
    else:
        print_error(f"Impossibile terminare {config['name']} (PID: {pid})")
        return False

def get_server_status(server_id: str, config: Dict) -> Dict:
    """Ottiene stato di un server"""
    pid_file = BASE_DIR / config['pid_file']
    pid = read_pid_file(pid_file)
    port_in_use = is_port_in_use(config['port'])
    
    status = {
        'name': config['name'],
        'port': config['port'],
        'running': False,
        'pid': None,
        'port_in_use': port_in_use
    }
    
    if pid:
        try:
            proc = psutil.Process(pid)
            status['running'] = True
            status['pid'] = pid
            status['cpu_percent'] = proc.cpu_percent(interval=0.1)
            status['memory_mb'] = proc.memory_info().rss / 1024 / 1024
        except psutil.NoSuchProcess:
            # PID file stantio
            try:
                pid_file.unlink()
            except OSError:
                pass
    
    return status

def start_all_servers():
    """Avvia tutti i server"""
    print_header("AVVIO SERVER KIMERIKA CLOUD")
    
    print_info(f"Directory base: {BASE_DIR}")
    print_info(f"Python: {sys.executable}\n")
    
    results = {}
    failed = []
    
    for server_id, config in SERVER_CONFIG.items():
        success = start_server(server_id, config)
        results[server_id] = success
        
        if not success and config['required']:
            failed.append(server_id)
    
    print("\n" + "="*60)
    if failed:
        print_error(f"Alcuni server richiesti non sono stati avviati: {', '.join(failed)}")
        print_info("Controlla i file di log per dettagli:")
        for server_id in failed:
            log_file = BASE_DIR / SERVER_CONFIG[server_id]['log_file']
            print(f"  - {log_file}")
        return False
    else:
        print_success("Tutti i server avviati con successo!")
        print_info("\nPer fermare i server: python server_manager.py stop")
        print_info("Per vedere lo stato: python server_manager.py status")
        return True

def stop_all_servers():
    """Ferma tutti i server"""
    print_header("ARRESTO SERVER KIMERIKA CLOUD")
    
    results = {}
    for server_id, config in SERVER_CONFIG.items():
        results[server_id] = stop_server(server_id, config)
    
    print("\n" + "="*60)
    if all(results.values()):
        print_success("Tutti i server fermati")
    else:
        print_warning("Alcuni server potrebbero essere ancora attivi")
        print_info("Esegui: python server_manager.py status")

def show_status():
    """Mostra stato di tutti i server"""
    print_header("STATO SERVER KIMERIKA CLOUD")
    
    all_running = True
    
    for server_id, config in SERVER_CONFIG.items():
        status = get_server_status(server_id, config)
        
        name_padded = status['name'].ljust(30)
        port_str = f"porta {status['port']}".ljust(12)
        
        if status['running']:
            cpu = f"{status.get('cpu_percent', 0):.1f}%"
            mem = f"{status.get('memory_mb', 0):.1f}MB"
            print(f"{Colors.OKGREEN}●{Colors.ENDC} {name_padded} {port_str} PID: {status['pid']:5d}  CPU: {cpu:6s}  MEM: {mem}")
        else:
            all_running = False
            if status['port_in_use']:
                print(f"{Colors.WARNING}◐{Colors.ENDC} {name_padded} {port_str} porta occupata da altro processo")
            else:
                print(f"{Colors.FAIL}○{Colors.ENDC} {name_padded} {port_str} non in esecuzione")
    
    print("\n" + "="*60)
    if all_running:
        print_success("Tutti i server operativi")
    else:
        print_warning("Alcuni server non sono attivi")
        print_info("Per avviare: python server_manager.py start")

def restart_all_servers():
    """Riavvia tutti i server"""
    print_header("RIAVVIO SERVER KIMERIKA CLOUD")
    
    print_info("Fase 1: Arresto server esistenti\n")
    stop_all_servers()
    
    print_info("\nAttesa 3 secondi...")
    time.sleep(3)
    
    print_info("\nFase 2: Avvio server\n")
    return start_all_servers()

def cleanup_stale_pids():
    """Rimuove file PID obsoleti"""
    print_info("Pulizia file PID obsoleti...")
    
    cleaned = 0
    for server_id, config in SERVER_CONFIG.items():
        pid_file = BASE_DIR / config['pid_file']
        if pid_file.exists():
            pid = read_pid_file(pid_file)
            if not pid:
                try:
                    pid_file.unlink()
                    cleaned += 1
                    print_info(f"Rimosso: {pid_file.name}")
                except OSError:
                    pass
    
    if cleaned > 0:
        print_success(f"Puliti {cleaned} file PID obsoleti")
    else:
        print_info("Nessun file PID obsoleto trovato")

def main():
    """Entry point principale"""
    if len(sys.argv) < 2:
        print(f"""
{Colors.BOLD}Kimerika Cloud - Gestore Server{Colors.ENDC}

Utilizzo:
    python server_manager.py <comando>

Comandi disponibili:
    start     Avvia tutti i server
    stop      Ferma tutti i server  
    restart   Riavvia tutti i server
    status    Mostra stato server
    cleanup   Rimuove file PID obsoleti

Esempi:
    python server_manager.py start
    python server_manager.py status
    python server_manager.py restart
""")
        sys.exit(0)
    
    command = sys.argv[1].lower()
    
    try:
        if command == 'start':
            success = start_all_servers()
            sys.exit(0 if success else 1)
        
        elif command == 'stop':
            stop_all_servers()
            sys.exit(0)
        
        elif command == 'restart':
            success = restart_all_servers()
            sys.exit(0 if success else 1)
        
        elif command == 'status':
            show_status()
            sys.exit(0)
        
        elif command == 'cleanup':
            cleanup_stale_pids()
            sys.exit(0)
        
        else:
            print_error(f"Comando sconosciuto: {command}")
            print_info("Usa: python server_manager.py --help")
            sys.exit(1)
    
    except KeyboardInterrupt:
        print(f"\n\n{Colors.WARNING}Operazione interrotta dall'utente{Colors.ENDC}")
        sys.exit(130)
    except Exception as e:
        print_error(f"Errore imprevisto: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
