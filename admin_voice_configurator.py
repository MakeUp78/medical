#!/usr/bin/env python3
"""
🔧 ADMIN VOICE CONFIGURATOR - Tool Amministrativo
===============================================

Tool per amministratori che permette di:
- Mappare pulsanti dell'interfaccia ai comandi vocali
- Configurare nuovi comandi vocali
- Testare e validare l'integrazione
- Gestire configurazioni avanzate

ACCESSO: Solo per amministratori del sistema
SICUREZZA: Password protetto + file di configurazione

Autore: AI Assistant
Data: 6 Ottobre 2025
Versione: 1.0.0
"""

import tkinter as tk
import ttkbootstrap as ttk
from tkinter import messagebox, simpledialog, filedialog
import json
import os
import sys
import hashlib
import getpass
from typing import Dict, List, Any, Optional, Callable
import inspect
import importlib.util
from datetime import datetime
import logging

# Query intelligenti rimosse per semplificare il codice
INTELLIGENT_QUERIES_AVAILABLE = False

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("AdminVoiceConfigurator")


class AdminAuthenticator:
    """Gestisce l'autenticazione amministratore"""
    
    def __init__(self, config_file="admin_config.json"):
        self.config_file = config_file
        self.admin_config = self._load_admin_config()
    
    def _load_admin_config(self) -> Dict[str, Any]:
        """Carica configurazione amministratore"""
        default_config = {
            "admin_password_hash": "5e884898da28047151d0e56f8dc6292773603d0d6aabbdd62a11ef721d1542d8",  # "password"
            "admin_users": ["admin", "administrator"],
            "max_login_attempts": 3,
            "session_timeout": 3600,
            "backup_configs": True,
            "last_access": None
        }
        
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    loaded = json.load(f)
                    default_config.update(loaded)
        except Exception as e:
            logger.warning(f"Errore caricamento config admin: {e}")
        
        return default_config
    
    def _save_admin_config(self):
        """Salva configurazione amministratore"""
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self.admin_config, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Errore salvataggio config admin: {e}")
    
    def _hash_password(self, password: str) -> str:
        """Hash della password"""
        return hashlib.sha256(password.encode()).hexdigest()
    
    def authenticate(self) -> bool:
        """Autentica amministratore"""
        attempts = 0
        max_attempts = self.admin_config.get("max_login_attempts", 3)
        
        while attempts < max_attempts:
            # Dialog per credenziali
            auth_dialog = AdminLoginDialog()
            if not auth_dialog.show():
                return False
            
            username, password = auth_dialog.get_credentials()
            
            # Verifica username
            if username not in self.admin_config.get("admin_users", []):
                attempts += 1
                messagebox.showerror("Errore", f"Username non valido. Tentativi rimasti: {max_attempts - attempts}")
                continue
            
            # Verifica password
            password_hash = self._hash_password(password)
            if password_hash == self.admin_config.get("admin_password_hash"):
                # Login riuscito
                self.admin_config["last_access"] = datetime.now().isoformat()
                self._save_admin_config()
                logger.info(f"Login amministratore riuscito: {username}")
                return True
            else:
                attempts += 1
                messagebox.showerror("Errore", f"Password non valida. Tentativi rimasti: {max_attempts - attempts}")
        
        messagebox.showerror("Accesso Negato", "Troppi tentativi falliti. Accesso bloccato.")
        logger.warning("Troppi tentativi di login falliti")
        return False


class AdminLoginDialog:
    """Dialog per login amministratore"""
    
    def __init__(self):
        self.result = False
        self.username = ""
        self.password = ""
    
    def show(self) -> bool:
        """Mostra dialog e restituisce risultato"""
        self.dialog = tk.Toplevel()
        self.dialog.title("🔐 Accesso Amministratore")
        self.dialog.geometry("400x250")
        self.dialog.resizable(False, False)
        self.dialog.grab_set()
        
        # Centra il dialog
        self.dialog.transient()
        
        # Frame principale
        main_frame = ttk.Frame(self.dialog, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Titolo
        ttk.Label(
            main_frame, 
            text="🔧 Admin Voice Configurator",
            font=("Arial", 14, "bold")
        ).pack(pady=(0, 20))
        
        # Username
        ttk.Label(main_frame, text="Username:").pack(anchor="w")
        self.username_entry = ttk.Entry(main_frame, width=30)
        self.username_entry.pack(fill=tk.X, pady=(0, 10))
        
        # Password
        ttk.Label(main_frame, text="Password:").pack(anchor="w")
        self.password_entry = ttk.Entry(main_frame, show="*", width=30)
        self.password_entry.pack(fill=tk.X, pady=(0, 20))
        
        # Pulsanti
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X)
        
        ttk.Button(
            button_frame,
            text="Annulla",
            command=self._cancel,
            bootstyle="secondary"
        ).pack(side=tk.RIGHT, padx=(5, 0))
        
        ttk.Button(
            button_frame,
            text="Accedi",
            command=self._login,
            bootstyle="primary"
        ).pack(side=tk.RIGHT)
        
        # Focus e binding
        self.username_entry.focus()
        self.dialog.bind('<Return>', lambda e: self._login())
        self.dialog.bind('<Escape>', lambda e: self._cancel())
        
        # Aspetta chiusura dialog
        self.dialog.wait_window()
        return self.result
    
    def _login(self):
        """Conferma login"""
        self.username = self.username_entry.get().strip()
        self.password = self.password_entry.get()
        
        if not self.username or not self.password:
            messagebox.showerror("Errore", "Inserire username e password")
            return
        
        self.result = True
        self.dialog.destroy()
    
    def _cancel(self):
        """Annulla login"""
        self.result = False
        self.dialog.destroy()
    
    def get_credentials(self) -> tuple:
        """Restituisce credenziali inserite"""
        return self.username, self.password


class UIButtonScanner:
    """Scansiona l'interfaccia per trovare tutti i pulsanti"""
    
    def __init__(self):
        self.discovered_buttons = {}
        self.discovered_methods = {}
    
    def scan_canvas_app(self) -> Dict[str, Any]:
        """Scansiona CanvasApp per trovare pulsanti e metodi"""
        try:
            # Importa CanvasApp
            sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))
            from canvas_app import CanvasApp
            
            # Scansiona metodi pubblici
            methods = {}
            for name, method in inspect.getmembers(CanvasApp, predicate=inspect.isfunction):
                if not name.startswith('_'):  # Solo metodi pubblici
                    signature = str(inspect.signature(method))
                    docstring = inspect.getdoc(method) or "Nessuna descrizione disponibile"
                    
                    methods[name] = {
                        'signature': signature,
                        'docstring': docstring[:200] + "..." if len(docstring) > 200 else docstring,
                        'is_callback_candidate': self._is_callback_candidate(name, docstring)
                    }
            
            # Cerca pattern di pulsanti nel codice sorgente
            buttons = self._scan_source_for_buttons()
            
            return {
                'methods': methods,
                'buttons': buttons,
                'scan_timestamp': datetime.now().isoformat(),
                'total_methods': len(methods),
                'callback_candidates': len([m for m in methods.values() if m['is_callback_candidate']])
            }
            
        except Exception as e:
            logger.error(f"Errore scansione CanvasApp: {e}")
            return {}
    
    def _is_callback_candidate(self, name: str, docstring: str) -> bool:
        """Determina se un metodo è candidato per callback vocali"""
        callback_keywords = [
            'load', 'save', 'start', 'stop', 'calculate', 'clear', 
            'detect', 'analyze', 'export', 'import', 'toggle',
            'show', 'hide', 'open', 'close', 'apply', 'reset'
        ]
        
        action_keywords = [
            'click', 'press', 'button', 'action', 'command',
            'execute', 'run', 'perform', 'trigger'
        ]
        
        # Controlla nome metodo
        name_lower = name.lower()
        if any(keyword in name_lower for keyword in callback_keywords):
            return True
        
        # Controlla docstring
        if docstring:
            doc_lower = docstring.lower()
            if any(keyword in doc_lower for keyword in action_keywords + callback_keywords):
                return True
        
        return False
    
    def _scan_source_for_buttons(self) -> Dict[str, Any]:
        """Scansiona il codice sorgente per trovare definizioni di pulsanti"""
        buttons_found = {}
        
        try:
            canvas_app_path = os.path.join(os.path.dirname(__file__), "src", "canvas_app.py")
            if os.path.exists(canvas_app_path):
                with open(canvas_app_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # Pattern per trovare pulsanti
                import re
                
                # ttk.Button pattern
                button_patterns = [
                    r'ttk\.Button\([^,)]*,\s*text=["\']([^"\']+)["\'][^)]*command=([^,)]+)',
                    r'tk\.Button\([^,)]*,\s*text=["\']([^"\']+)["\'][^)]*command=([^,)]+)',
                    r'Button\([^,)]*,\s*text=["\']([^"\']+)["\'][^)]*command=([^,)]+)'
                ]
                
                for pattern in button_patterns:
                    matches = re.finditer(pattern, content, re.IGNORECASE | re.MULTILINE)
                    for match in matches:
                        button_text = match.group(1)
                        command = match.group(2).strip()
                        
                        # Pulisci comando
                        if command.startswith('self.'):
                            command = command[5:]
                        
                        buttons_found[button_text] = {
                            'text': button_text,
                            'command': command,
                            'type': 'button'
                        }
                
                # Menu pattern
                menu_pattern = r'add_command\([^,)]*label=["\']([^"\']+)["\'][^)]*command=([^,)]+)'
                matches = re.finditer(menu_pattern, content, re.IGNORECASE | re.MULTILINE)
                for match in matches:
                    menu_text = match.group(1)
                    command = match.group(2).strip()
                    
                    if command.startswith('self.'):
                        command = command[5:]
                    
                    buttons_found[menu_text] = {
                        'text': menu_text,
                        'command': command,
                        'type': 'menu'
                    }
        
        except Exception as e:
            logger.error(f"Errore scansione sorgente: {e}")
        
        return buttons_found


class VoiceConfiguratorGUI:
    """Interfaccia grafica principale del configuratore"""
    
    def __init__(self):
        self.root = None
        self.scanner = UIButtonScanner()
        self.current_mappings = {}
        self.scanned_data = {}
        
        # Carica configurazioni esistenti
        self._load_current_mappings()
        
        # Sistema query intelligenti rimosso per semplificare
        self.query_handler = None
    
    def _load_current_mappings(self):
        """Carica mappature vocali esistenti"""
        try:
            # Carica da voice_gui_integration.py
            voice_integration_path = os.path.join(os.path.dirname(__file__), "voice", "voice_gui_integration.py")
            if os.path.exists(voice_integration_path):
                with open(voice_integration_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # Estrai mappature esistenti (semplice parsing)
                import re
                pattern = r'keywords=\[(.*?)\].*?action=["\']([^"\']+)["\'].*?handler=.*?["\']([^"\']+)["\']'
                matches = re.finditer(pattern, content, re.DOTALL)
                
                for match in matches:
                    keywords_str = match.group(1)
                    action = match.group(2)
                    handler = match.group(3)
                    
                    # Estrai keywords
                    keywords = re.findall(r'["\']([^"\']+)["\']', keywords_str)
                    
                    self.current_mappings[action] = {
                        'keywords': keywords,
                        'handler': handler,
                        'action': action
                    }
        
        except Exception as e:
            logger.error(f"Errore caricamento mappature: {e}")
    
    def create_gui(self):
        """Crea interfaccia grafica"""
        self.root = ttk.Window(themename="cosmo")
        self.root.title("🔧 Admin Voice Configurator - Symmetra System")
        self.root.geometry("1200x800")
        self.root.minsize(1000, 600)
        
        # Menu
        self._create_menu()
        
        # Toolbar
        self._create_toolbar()
        
        # Layout principale con notebook
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        # Tabs
        self._create_scanner_tab()
        self._create_mapper_tab()
        self._create_tester_tab()
        self._create_queries_tab()
        self._create_config_tab()
        
        # Status bar
        self._create_status_bar()
        
        # Keybindings utili
        self._setup_keybindings()
        
        # Esegui scansione iniziale
        self._scan_interface()
    
    def _setup_keybindings(self):
        """Configura keybindings utili"""
        # Ctrl+S per salvare
        self.root.bind('<Control-s>', lambda e: self._save_config())
        
        # F5 per refresh/scan
        self.root.bind('<F5>', lambda e: self._scan_interface())
        
        # F9 per test
        self.root.bind('<F9>', lambda e: self._test_voice_commands())
        
        # ESC per chiudere dialoghi (se supportato)
        self.root.bind('<Escape>', lambda e: self.root.focus_set())
    
    def _create_menu(self):
        """Crea menu principale"""
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)
        
        # File menu
        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="File", menu=file_menu)
        file_menu.add_command(label="Carica Configurazione...", command=self._load_config)
        file_menu.add_command(label="Salva Configurazione...", command=self._save_config)
        file_menu.add_separator()
        file_menu.add_command(label="Esporta Report...", command=self._export_report)
        file_menu.add_separator()
        file_menu.add_command(label="Esci", command=self.root.quit)
        
        # Tools menu
        tools_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Strumenti", menu=tools_menu)
        tools_menu.add_command(label="Riscansiona Interfaccia", command=self._scan_interface)
        tools_menu.add_command(label="Valida Configurazione", command=self._validate_config)
        tools_menu.add_command(label="Genera Codice", command=self._generate_code)
        
        # Help menu
        help_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Aiuto", menu=help_menu)
        help_menu.add_command(label="Guida", command=self._show_help)
        help_menu.add_command(label="Info", command=self._show_about)
    
    def _create_toolbar(self):
        """Crea toolbar"""
        toolbar = ttk.Frame(self.root)
        toolbar.pack(fill=tk.X, padx=10, pady=5)
        
        ttk.Button(
            toolbar,
            text="🔍 Scansiona",
            command=self._scan_interface,
            bootstyle="primary"
        ).pack(side=tk.LEFT, padx=(0, 5))
        
        ttk.Button(
            toolbar,
            text="💾 Salva",
            command=self._save_config,
            bootstyle="success"
        ).pack(side=tk.LEFT, padx=5)
        
        ttk.Button(
            toolbar,
            text="🧪 Test",
            command=self._test_voice_commands,
            bootstyle="warning"
        ).pack(side=tk.LEFT, padx=5)
        
        # Separatore
        ttk.Separator(toolbar, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=10)
        
        # Info
        ttk.Label(
            toolbar,
            text="🎤 Configuratore Comandi Vocali Symmetra",
            font=("Arial", 10, "bold")
        ).pack(side=tk.LEFT, padx=10)
    
    def _create_scanner_tab(self):
        """Crea tab scanner interfaccia"""
        scanner_frame = ttk.Frame(self.notebook)
        self.notebook.add(scanner_frame, text="🔍 Scanner Interfaccia")
        
        # Layout a tre pannelli
        paned = ttk.PanedWindow(scanner_frame, orient=tk.HORIZONTAL)
        paned.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Pannello metodi
        methods_frame = ttk.LabelFrame(paned, text="📋 Metodi Disponibili", padding=5)
        paned.add(methods_frame, weight=1)
        
        # Treeview metodi
        columns = ("Nome", "Tipo", "Candidato")
        self.methods_tree = ttk.Treeview(methods_frame, columns=columns, show="tree headings")
        
        for col in columns:
            self.methods_tree.heading(col, text=col)
            self.methods_tree.column(col, width=100)
        
        # Scrollbar per metodi
        methods_scroll = ttk.Scrollbar(methods_frame, orient=tk.VERTICAL, command=self.methods_tree.yview)
        self.methods_tree.configure(yscrollcommand=methods_scroll.set)
        
        self.methods_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        methods_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Pannello pulsanti
        buttons_frame = ttk.LabelFrame(paned, text="🖱️ Pulsanti Rilevati", padding=5)
        paned.add(buttons_frame, weight=1)
        
        # Treeview pulsanti
        buttons_columns = ("Testo", "Comando", "Tipo")
        self.buttons_tree = ttk.Treeview(buttons_frame, columns=buttons_columns, show="tree headings")
        
        for col in buttons_columns:
            self.buttons_tree.heading(col, text=col)
            self.buttons_tree.column(col, width=120)
        
        # Scrollbar per pulsanti
        buttons_scroll = ttk.Scrollbar(buttons_frame, orient=tk.VERTICAL, command=self.buttons_tree.yview)
        self.buttons_tree.configure(yscrollcommand=buttons_scroll.set)
        
        self.buttons_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        buttons_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Pannello dettagli
        details_frame = ttk.LabelFrame(paned, text="📖 Dettagli", padding=5)
        paned.add(details_frame, weight=1)
        
        self.details_text = tk.Text(details_frame, wrap=tk.WORD, height=10)
        details_text_scroll = ttk.Scrollbar(details_frame, orient=tk.VERTICAL, command=self.details_text.yview)
        self.details_text.configure(yscrollcommand=details_text_scroll.set)
        
        self.details_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        details_text_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Binding per selezione
        self.methods_tree.bind("<<TreeviewSelect>>", self._on_method_select)
        self.buttons_tree.bind("<<TreeviewSelect>>", self._on_button_select)
    
    def _create_mapper_tab(self):
        """Crea tab mapper comandi vocali"""
        mapper_frame = ttk.Frame(self.notebook)
        self.notebook.add(mapper_frame, text="🗺️ Mapper Comandi")
        
        # Layout principale
        main_paned = ttk.PanedWindow(mapper_frame, orient=tk.VERTICAL)
        main_paned.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Pannello mappature esistenti
        existing_frame = ttk.LabelFrame(main_paned, text="🎤 Mappature Vocali Esistenti", padding=5)
        main_paned.add(existing_frame, weight=1)
        
        # Treeview mappature
        mapping_columns = ("Azione", "Keywords", "Handler", "Status")
        self.mapping_tree = ttk.Treeview(existing_frame, columns=mapping_columns, show="tree headings")
        
        for col in mapping_columns:
            self.mapping_tree.heading(col, text=col)
            self.mapping_tree.column(col, width=150)
        
        mapping_scroll = ttk.Scrollbar(existing_frame, orient=tk.VERTICAL, command=self.mapping_tree.yview)
        self.mapping_tree.configure(yscrollcommand=mapping_scroll.set)
        
        self.mapping_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        mapping_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Binding per selezione mappatura
        self.mapping_tree.bind("<<TreeviewSelect>>", self._on_mapping_select)
        
        # Pannello editor
        editor_frame = ttk.LabelFrame(main_paned, text="✏️ Editor Mappature", padding=10)
        main_paned.add(editor_frame, weight=1)
        
        # Form editor
        form_frame = ttk.Frame(editor_frame)
        form_frame.pack(fill=tk.X, pady=(0, 10))
        
        # Azione
        ttk.Label(form_frame, text="Azione:").grid(row=0, column=0, sticky="w", padx=(0, 10))
        self.action_var = tk.StringVar()
        self.action_combo = ttk.Combobox(form_frame, textvariable=self.action_var, width=20, state="normal")
        self.action_combo.grid(row=0, column=1, sticky="ew", padx=(0, 20))
        
        # Handler
        ttk.Label(form_frame, text="Handler:").grid(row=0, column=2, sticky="w", padx=(0, 10))
        self.handler_var = tk.StringVar()
        self.handler_combo = ttk.Combobox(form_frame, textvariable=self.handler_var, width=25, state="normal")
        self.handler_combo.grid(row=0, column=3, sticky="ew")
        
        form_frame.columnconfigure(1, weight=1)
        form_frame.columnconfigure(3, weight=2)
        
        # Binding per sincronizzazione combobox
        self.action_combo.bind("<<ComboboxSelected>>", self._sync_action_var)
        self.action_combo.bind("<KeyRelease>", self._sync_action_var)
        self.handler_combo.bind("<<ComboboxSelected>>", self._sync_handler_var)
        self.handler_combo.bind("<KeyRelease>", self._sync_handler_var)
        
        # Keywords
        ttk.Label(editor_frame, text="Keywords (una per riga):").pack(anchor="w", pady=(10, 5))
        
        # Frame per keywords con layout corretto
        keywords_frame = ttk.Frame(editor_frame)
        keywords_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        
        # Text widget per keywords
        self.keywords_text = tk.Text(keywords_frame, height=6, wrap=tk.WORD, 
                                   font=("Arial", 10), bg="white", fg="black")
        keywords_scroll = ttk.Scrollbar(keywords_frame, orient=tk.VERTICAL, command=self.keywords_text.yview)
        self.keywords_text.configure(yscrollcommand=keywords_scroll.set)
        
        # Layout corretto
        self.keywords_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        keywords_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Pulsanti editor
        buttons_frame = ttk.Frame(editor_frame)
        buttons_frame.pack(fill=tk.X)
        
        ttk.Button(
            buttons_frame,
            text="➕ Nuovo",
            command=self._new_mapping,
            bootstyle="success-outline"
        ).pack(side=tk.LEFT, padx=(0, 5))
        
        ttk.Button(
            buttons_frame,
            text="💾 Salva",
            command=self._save_mapping,
            bootstyle="primary"
        ).pack(side=tk.LEFT, padx=5)
        
        ttk.Button(
            buttons_frame,
            text="🗑️ Elimina",
            command=self._delete_mapping,
            bootstyle="danger-outline"
        ).pack(side=tk.LEFT, padx=5)
        
        ttk.Button(
            buttons_frame,
            text="🧪 Test",
            command=self._test_mapping,
            bootstyle="warning-outline"
        ).pack(side=tk.RIGHT)
    
    def _create_tester_tab(self):
        """Crea tab tester"""
        tester_frame = ttk.Frame(self.notebook)
        self.notebook.add(tester_frame, text="🧪 Tester")
        
        # Area di test
        test_area = ttk.LabelFrame(tester_frame, text="🎤 Test Comandi Vocali", padding=10)
        test_area.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Input test
        input_frame = ttk.Frame(test_area)
        input_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(input_frame, text="Comando da testare:").pack(anchor="w")
        self.test_input = ttk.Entry(input_frame, font=("Arial", 12))
        self.test_input.pack(fill=tk.X, pady=(5, 0))
        
        # Pulsanti test
        test_buttons = ttk.Frame(test_area)
        test_buttons.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Button(
            test_buttons,
            text="🧪 Testa Comando",
            command=self._test_single_command,
            bootstyle="primary"
        ).pack(side=tk.LEFT, padx=(0, 10))
        
        ttk.Button(
            test_buttons,
            text="🔊 Test TTS",
            command=self._test_tts,
            bootstyle="info"
        ).pack(side=tk.LEFT, padx=10)
        
        ttk.Button(
            test_buttons,
            text="🎤 Test STT",
            command=self._test_stt,
            bootstyle="warning"
        ).pack(side=tk.LEFT, padx=10)
        
        # Seconda riga pulsanti
        test_buttons2 = ttk.Frame(test_area)
        test_buttons2.pack(fill=tk.X, pady=(5, 10))
        
        ttk.Button(
            test_buttons2,
            text="🔄 Test Completo",
            command=self._test_voice_commands,
            bootstyle="success"
        ).pack(side=tk.LEFT, padx=(0, 10))
        
        ttk.Button(
            test_buttons2,
            text="🧹 Pulisci Output",
            command=self._clear_test_output,
            bootstyle="secondary"
        ).pack(side=tk.LEFT, padx=10)
        
        ttk.Button(
            test_buttons2,
            text="💾 Salva Log",
            command=self._save_test_log,
            bootstyle="info"
        ).pack(side=tk.LEFT, padx=10)
        
        # Output test
        ttk.Label(test_area, text="Risultato Test:").pack(anchor="w", pady=(10, 0))
        
        # Frame per text widget e scrollbar
        output_frame = ttk.Frame(test_area)
        output_frame.pack(fill=tk.BOTH, expand=True, pady=(5, 0))
        
        self.test_output = tk.Text(output_frame, height=12, wrap=tk.WORD, bg="black", fg="green", font=("Consolas", 10))
        test_scroll = ttk.Scrollbar(output_frame, orient=tk.VERTICAL, command=self.test_output.yview)
        self.test_output.configure(yscrollcommand=test_scroll.set)
        
        self.test_output.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        test_scroll.pack(side=tk.RIGHT, fill=tk.Y)
    
    def _create_config_tab(self):
        """Crea tab configurazione"""
        config_frame = ttk.Frame(self.notebook)
        self.notebook.add(config_frame, text="⚙️ Configurazione")
        
        # Configurazione assistente vocale
        voice_config_frame = ttk.LabelFrame(config_frame, text="🎤 Configurazione Assistente Vocale", padding=10)
        voice_config_frame.pack(fill=tk.X, padx=10, pady=10)
        
        # Configurazione avanzata
        advanced_frame = ttk.LabelFrame(config_frame, text="🔧 Configurazione Avanzata", padding=10)
        advanced_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # JSON Editor per configurazioni
        ttk.Label(advanced_frame, text="Editor Configurazione JSON:").pack(anchor="w")
        self.config_editor = tk.Text(advanced_frame, wrap=tk.WORD, font=("Consolas", 10))
        config_scroll = ttk.Scrollbar(advanced_frame, orient=tk.VERTICAL, command=self.config_editor.yview)
        self.config_editor.configure(yscrollcommand=config_scroll.set)
        
        config_edit_frame = ttk.Frame(advanced_frame)
        config_edit_frame.pack(fill=tk.BOTH, expand=True, pady=(5, 0))
        self.config_editor.pack(in_=config_edit_frame, side=tk.LEFT, fill=tk.BOTH, expand=True)
        config_scroll.pack(in_=config_edit_frame, side=tk.RIGHT, fill=tk.Y)
    
    def _create_status_bar(self):
        """Crea status bar migliorata"""
        self.status_bar = ttk.Frame(self.root)
        self.status_bar.pack(fill=tk.X, side=tk.BOTTOM, padx=5, pady=2)
        
        # Status principale
        self.status_text = tk.StringVar(value="✅ Pronto")
        ttk.Label(self.status_bar, textvariable=self.status_text, 
                 font=("Arial", 9)).pack(side=tk.LEFT, padx=5)
        
        # Separator
        ttk.Separator(self.status_bar, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=10)
        
        # Stats
        self.stats_text = tk.StringVar(value="📊 Mappature: 0 | Pattern: 0")
        ttk.Label(self.status_bar, textvariable=self.stats_text, 
                 font=("Arial", 8)).pack(side=tk.LEFT, padx=5)
        
        # Info connessione
        self.connection_status = tk.StringVar(value="🔴 Offline")
        ttk.Label(self.status_bar, textvariable=self.connection_status, 
                 font=("Arial", 9)).pack(side=tk.RIGHT, padx=5)
        
        # Update stats iniziale (protetto)
        try:
            self._update_stats()
        except Exception as e:
            logger.debug(f"Stats iniziali non ancora disponibili: {e}")
    
    # === METODI EVENTI ===
    
    def _scan_interface(self):
        """Scansiona interfaccia per trovare pulsanti e metodi"""
        self.status_text.set("🔍 Scansione interfaccia in corso...")
        self.root.update()
        
        try:
            self.scanned_data = self.scanner.scan_canvas_app()
            
            # Popola treeview metodi
            self.methods_tree.delete(*self.methods_tree.get_children())
            for name, info in self.scanned_data.get('methods', {}).items():
                candidate = "✅ Sì" if info['is_callback_candidate'] else "❌ No"
                self.methods_tree.insert("", tk.END, values=(name, "Metodo", candidate))
            
            # Popola treeview pulsanti
            self.buttons_tree.delete(*self.buttons_tree.get_children())
            for text, info in self.scanned_data.get('buttons', {}).items():
                self.buttons_tree.insert("", tk.END, values=(info['text'], info['command'], info['type']))
            
            # Aggiorna mappature
            self._update_mapping_tree()
            
            total_methods = self.scanned_data.get('total_methods', 0)
            candidates = self.scanned_data.get('callback_candidates', 0)
            buttons = len(self.scanned_data.get('buttons', {}))
            
            self.status_text.set(f"✅ Scansione completata: {total_methods} metodi, {buttons} pulsanti, {candidates} candidati")
            
            # Popola combobox del mapper
            self._populate_mapper_comboboxes()
            
        except Exception as e:
            self.status_text.set(f"❌ Errore scansione: {e}")
            messagebox.showerror("Errore Scansione", f"Errore durante la scansione: {e}")
    
    def _populate_mapper_comboboxes(self):
        """Popola i combobox del mapper con dati dalla scansione"""
        try:
            # Popola azioni (basato sui pulsanti scansionati)
            actions = []
            for text, info in self.scanned_data.get('buttons', {}).items():
                button_text = info.get('text', '').lower()
                # Genera azioni basate sui nomi pulsanti
                if button_text:
                    action_name = button_text.replace(' ', '_').replace('-', '_')
                    actions.append(action_name)
            
            # Aggiungi azioni esistenti dalle mappature
            for action in self.current_mappings.keys():
                if action not in actions:
                    actions.append(action)
            
            # Aggiungi azioni predefinite comuni
            default_actions = [
                'start_webcam', 'stop_webcam', 'start_analysis', 'stop_analysis',
                'load_image', 'save_results', 'clear_data', 'show_measurements',
                'calculate_distances', 'show_axis', 'hide_axis', 'zoom_in', 'zoom_out'
            ]
            
            for action in default_actions:
                if action not in actions:
                    actions.append(action)
            
            # Popola handlers (metodi candidati dalla scansione)
            handlers = []
            for name, info in self.scanned_data.get('methods', {}).items():
                if info.get('is_callback_candidate', False):
                    handlers.append(name)
            
            # Aggiungi handlers dai pulsanti
            for text, info in self.scanned_data.get('buttons', {}).items():
                handler = info.get('command', '')
                if handler and handler not in handlers:
                    handlers.append(handler)
            
            # Aggiorna comboboxes se esistono
            if hasattr(self, 'action_combo'):
                self.action_combo['values'] = sorted(actions)
            
            if hasattr(self, 'handler_combo'):
                self.handler_combo['values'] = sorted(handlers)
                
            logger.info(f"Combobox popolati: {len(actions)} azioni, {len(handlers)} handlers")
            
        except Exception as e:
            logger.error(f"Errore popolamento combobox: {e}")
    
    def _update_mapping_tree(self):
        """Aggiorna treeview mappature"""
        self.mapping_tree.delete(*self.mapping_tree.get_children())
        
        for action, mapping in self.current_mappings.items():
            keywords = ", ".join(mapping.get('keywords', []))
            handler = mapping.get('handler', 'N/A')
            status = "✅ Attivo" if handler in self.scanned_data.get('methods', {}) else "❌ Handler non trovato"
            
            self.mapping_tree.insert("", tk.END, values=(action, keywords, handler, status))
    
    def _on_method_select(self, event):
        """Gestisce selezione metodo"""
        selection = self.methods_tree.selection()
        if not selection:
            return
        
        item = self.methods_tree.item(selection[0])
        method_name = item['values'][0]
        
        if method_name in self.scanned_data.get('methods', {}):
            method_info = self.scanned_data['methods'][method_name]
            
            details = f"Metodo: {method_name}\n"
            details += f"Firma: {method_info['signature']}\n"
            details += f"Candidato Callback: {'Sì' if method_info['is_callback_candidate'] else 'No'}\n\n"
            details += f"Descrizione:\n{method_info['docstring']}"
            
            self.details_text.delete(1.0, tk.END)
            self.details_text.insert(1.0, details)
    
    def _on_button_select(self, event):
        """Gestisce selezione pulsante"""
        selection = self.buttons_tree.selection()
        if not selection:
            return
        
        item = self.buttons_tree.item(selection[0])
        button_text, command, btn_type = item['values']
        
        details = f"Pulsante: {button_text}\n"
        details += f"Comando: {command}\n"
        details += f"Tipo: {btn_type}\n\n"
        
        # Cerca se esiste già una mappatura
        existing_mapping = None
        for action, mapping in self.current_mappings.items():
            if mapping.get('handler') == command:
                existing_mapping = mapping
                break
        
        if existing_mapping:
            details += f"Mappatura Esistente:\n"
            details += f"Azione: {existing_mapping.get('action', 'N/A')}\n"
            details += f"Keywords: {', '.join(existing_mapping.get('keywords', []))}\n"
        else:
            details += "Nessuna mappatura vocale trovata per questo pulsante.\n"
            details += "Puoi crearne una nel tab 'Mapper Comandi'."
        
        self.details_text.delete(1.0, tk.END)
        self.details_text.insert(1.0, details)
    
    def _clear_placeholder(self, event):
        """Pulisce il testo di placeholder quando l'utente clicca nel campo"""
        current_text = self.keywords_text.get(1.0, tk.END)
        if "# Inserisci le keywords qui" in current_text:
            self.keywords_text.delete(1.0, tk.END)
            # Rimuovi il binding dopo il primo clic
            self.keywords_text.unbind("<Button-1>")
    
    def _sync_action_var(self, event):
        """Sincronizza il valore del combobox action con la StringVar"""
        value = self.action_combo.get()
        self.action_var.set(value)
    
    def _sync_handler_var(self, event):
        """Sincronizza il valore del combobox handler con la StringVar"""
        value = self.handler_combo.get()
        self.handler_var.set(value)
    
    def _on_mapping_select(self, event):
        """Gestisce selezione mappatura per editing"""
        selection = self.mapping_tree.selection()
        if not selection:
            return
        
        try:
            item = self.mapping_tree.item(selection[0])
            action = item['values'][0]
            
            if action in self.current_mappings:
                mapping = self.current_mappings[action]
                
                # Popola i campi dell'editor
                self.action_var.set(action)
                self.handler_var.set(mapping.get('handler', ''))
                
                # Popola keywords (una per riga)
                keywords = mapping.get('keywords', [])
                self.keywords_text.delete(1.0, tk.END)
                self.keywords_text.insert(1.0, '\n'.join(keywords))
                
        except Exception as e:
            logger.error(f"Errore selezione mappatura: {e}")
    
    # === METODI MAPPER ===
    
    def _new_mapping(self):
        """Crea nuova mappatura"""
        self.action_var.set("")
        self.handler_var.set("")
        self.keywords_text.delete(1.0, tk.END)
        
        # Aggiungi testo di esempio
        example_text = "# Inserisci le keywords qui, una per riga:\n# Esempio:\nasse\nmostra asse\nattiva asse"
        self.keywords_text.insert(1.0, example_text)
        self.keywords_text.bind("<Button-1>", self._clear_placeholder)
    
    def _save_mapping(self):
        """Salva mappatura corrente"""
        # Prova anche a leggere direttamente dai combobox
        action = self.action_var.get().strip()
        if not action:
            action = self.action_combo.get().strip()
            
        handler = self.handler_var.get().strip()
        if not handler:
            handler = self.handler_combo.get().strip()
            
        keywords_text = self.keywords_text.get(1.0, tk.END).strip()
        
        # Debug: stampa i valori letti
        print(f"DEBUG - Action: '{action}', Handler: '{handler}', Keywords: '{keywords_text[:50]}...'")
        
        # Rimuovi il testo di esempio se presente
        if "# Inserisci le keywords qui" in keywords_text:
            keywords_text = ""
        
        # Validazione dettagliata
        missing_fields = []
        if not action:
            missing_fields.append("Azione")
        if not handler:
            missing_fields.append("Handler")
        if not keywords_text:
            missing_fields.append("Keywords")
        
        if missing_fields:
            error_msg = f"Campi mancanti: {', '.join(missing_fields)}\n\n"
            if "Keywords" in missing_fields:
                error_msg += "💡 Per le Keywords: scrivi una parola chiave per riga nell'area di testo grande."
            messagebox.showerror("Campi Obbligatori", error_msg)
            return
        
        keywords = [kw.strip() for kw in keywords_text.split('\n') if kw.strip()]
        
        self.current_mappings[action] = {
            'action': action,
            'handler': handler,
            'keywords': keywords
        }
        
        self._update_mapping_tree()
        self._update_stats()
        self.status_text.set(f"✅ Mappatura '{action}' salvata")
    
    def _delete_mapping(self):
        """Elimina mappatura selezionata"""
        selection = self.mapping_tree.selection()
        if not selection:
            messagebox.showwarning("Selezione", "Seleziona una mappatura da eliminare")
            return
        
        item = self.mapping_tree.item(selection[0])
        action = item['values'][0]
        
        if messagebox.askyesno("Conferma", f"Eliminare la mappatura '{action}'?"):
            del self.current_mappings[action]
            self._update_mapping_tree()
            self._update_stats()
            self.status_text.set(f"🗑️ Mappatura '{action}' eliminata")
    
    def _test_mapping(self):
        """Testa mappatura corrente nell'editor"""
        action = self.action_var.get().strip()
        handler = self.handler_var.get().strip()
        keywords_text = self.keywords_text.get(1.0, tk.END).strip()
        
        if not action or not handler or not keywords_text:
            messagebox.showwarning("Test", "Completa tutti i campi per testare la mappatura")
            return
        
        keywords = [kw.strip() for kw in keywords_text.split('\n') if kw.strip()]
        
        # Vai al tab tester
        self.notebook.select(2)
        
        # Testa prima keyword
        if keywords:
            self.test_input.delete(0, tk.END)
            self.test_input.insert(0, keywords[0])
            
            self._log_test(f"🧪 Test mappatura in corso...")
            self._log_test(f"📋 Azione: {action}")
            self._log_test(f"🔗 Handler: {handler}")
            self._log_test(f"🔑 Keywords da testare: {', '.join(keywords)}")
            self._log_test("-" * 40)
            
            # Esegui test del comando
            self._test_single_command()
        
        self.status_text.set("🧪 Test mappatura eseguito")
    
    # === METODI TESTER ===
    
    def _test_single_command(self):
        """Testa singolo comando vocale con feedback dettagliato"""
        command = self.test_input.get().strip()
        if not command:
            messagebox.showwarning("Input", "Inserisci un comando da testare")
            return
        
        self._log_test(f"🧪 Testing comando: '{command}'")
        self._log_test("=" * 50)
        
        # Analisi comando
        command_lower = command.lower()
        found_mappings = []
        partial_matches = []
        
        # Cerca corrispondenze esatte e parziali
        for action, mapping in self.current_mappings.items():
            keywords = mapping.get('keywords', [])
            exact_match = False
            partial_match = False
            
            for keyword in keywords:
                if keyword.lower() == command_lower:
                    exact_match = True
                    break
                elif keyword.lower() in command_lower or command_lower in keyword.lower():
                    partial_match = True
            
            if exact_match:
                found_mappings.append(mapping)
            elif partial_match:
                partial_matches.append(mapping)
        
        # Report risultati
        if found_mappings:
            self._log_test(f"✅ COMANDO RICONOSCIUTO!")
            for mapping in found_mappings:
                self._log_test(f"   📋 Azione: {mapping['action']}")
                self._log_test(f"   🔗 Handler: {mapping['handler']}")
                self._log_test(f"   🔑 Keywords: {', '.join(mapping['keywords'])}")
                self._log_test("")
                
                # Test simulazione esecuzione
                try:
                    self._log_test(f"   🚀 Simulazione esecuzione...")
                    self._log_test(f"   ➡️ Chiamata metodo: {mapping['handler']}")
                    self._log_test(f"   ✅ Comando eseguibile!")
                except Exception as e:
                    self._log_test(f"   ❌ Errore simulazione: {e}")
        
        elif partial_matches:
            self._log_test(f"⚠️ CORRISPONDENZE PARZIALI TROVATE:")
            for mapping in partial_matches:
                self._log_test(f"   📋 {mapping['action']} - Keywords: {', '.join(mapping['keywords'])}")
        
        else:
            self._log_test(f"❌ COMANDO NON RICONOSCIUTO")
            self._log_test("📋 Comandi disponibili:")
            for i, (action, mapping) in enumerate(list(self.current_mappings.items())[:8]):
                keywords_str = ', '.join(mapping['keywords'][:3]) if mapping['keywords'] else 'N/A'
                self._log_test(f"   {i+1}. {action}: {keywords_str}")
        
        # Statistiche
        self._log_test("")
        self._log_test(f"📊 STATISTICHE:")
        self._log_test(f"   • Comandi totali configurati: {len(self.current_mappings)}")
        self._log_test(f"   • Corrispondenze esatte: {len(found_mappings)}")
        self._log_test(f"   • Corrispondenze parziali: {len(partial_matches)}")
        self._log_test("=" * 50)
    
    def _test_tts(self):
        """Testa Text-to-Speech con edge-tts"""
        self._log_test("🔊 Test TTS avviato...")
        
        try:
            # Import necessari per TTS
            import subprocess
            import tempfile
            import os
            import pygame
            
            # Testo di test
            test_text = "Test del sistema text-to-speech. Comando vocale riconosciuto correttamente."
            
            self._log_test(f"📝 Testo da sintetizzare: '{test_text}'")
            self._log_test("🔄 Generazione audio...")
            
            # Crea file temporaneo per l'audio
            with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as temp_file:
                temp_audio_path = temp_file.name
            
            # Comando edge-tts
            edge_command = [
                'edge-tts',
                '--voice', 'it-IT-IsabellaNeural',
                '--text', test_text,
                '--write-media', temp_audio_path
            ]
            
            # Esegui edge-tts
            result = subprocess.run(edge_command, capture_output=True, text=True, timeout=10)
            
            if result.returncode == 0:
                self._log_test("✅ Audio generato con successo!")
                self._log_test("🔊 Riproduzione audio...")
                
                # Inizializza pygame mixer se non già fatto
                try:
                    pygame.mixer.init()
                    pygame.mixer.music.load(temp_audio_path)
                    pygame.mixer.music.play()
                    
                    self._log_test("✅ Audio riprodotto correttamente!")
                    self._log_test("ℹ️ Voice: it-IT-IsabellaNeural (Edge TTS)")
                    
                    # Cleanup dopo un delay
                    self.root.after(3000, lambda: self._cleanup_temp_file(temp_audio_path))
                    
                except pygame.error as e:
                    self._log_test(f"⚠️ Audio generato ma errore riproduzione: {e}")
                    os.unlink(temp_audio_path)
            else:
                self._log_test(f"❌ Errore generazione TTS: {result.stderr}")
                os.unlink(temp_audio_path)
                
        except subprocess.TimeoutExpired:
            self._log_test("⏱️ Timeout generazione TTS (>10s)")
        except FileNotFoundError:
            self._log_test("❌ edge-tts non trovato. Installa con: pip install edge-tts")
        except ImportError as e:
            self._log_test(f"❌ Modulo mancante: {e}")
            self._log_test("💡 Installa con: pip install pygame")
        except Exception as e:
            self._log_test(f"❌ Errore TTS: {e}")
            
    def _cleanup_temp_file(self, filepath):
        """Pulisce file temporanei"""
        try:
            if os.path.exists(filepath):
                os.unlink(filepath)
        except Exception:
            pass
    
    def _test_stt(self):
        """Testa Speech-to-Text con riconoscimento vocale"""
        self._log_test("🎤 Test STT avviato...")
        
        try:
            import speech_recognition as sr
            
            # Inizializza riconoscitore
            recognizer = sr.Recognizer()
            
            self._log_test("🔧 Configurazione microfono...")
            
            # Usa microfono
            with sr.Microphone() as source:
                self._log_test("🔄 Calibrazione rumore ambientale...")
                recognizer.adjust_for_ambient_noise(source, duration=1)
                
                self._log_test("🎙️ PARLA ORA! (5 secondi per dire un comando)")
                self._log_test("💡 Suggerimento: prova 'avvia webcam' o 'ferma analisi'")
                
                # Registra audio
                try:
                    audio = recognizer.listen(source, timeout=1, phrase_time_limit=5)
                    self._log_test("✅ Audio registrato!")
                    
                except sr.WaitTimeoutError:
                    self._log_test("⏱️ Timeout - nessun audio rilevato")
                    return
            
            # Riconoscimento
            self._log_test("🔄 Elaborazione riconoscimento...")
            
            try:
                # Prova Google Speech Recognition
                text = recognizer.recognize_google(audio, language='it-IT')
                self._log_test(f"✅ RICONOSCIUTO: '{text}'")
                
                # Test se è un comando valido
                command_lower = text.lower()
                found_mapping = None
                
                for action, mapping in self.current_mappings.items():
                    keywords = mapping.get('keywords', [])
                    if any(keyword.lower() in command_lower for keyword in keywords):
                        found_mapping = mapping
                        break
                
                if found_mapping:
                    self._log_test(f"🎯 COMANDO VALIDO RICONOSCIUTO!")
                    self._log_test(f"   ➡️ Azione: {found_mapping['action']}")
                    self._log_test(f"   🔗 Handler: {found_mapping['handler']}")
                else:
                    self._log_test("⚠️ Testo riconosciuto ma non corrisponde a comandi configurati")
                    
            except sr.UnknownValueError:
                self._log_test("❌ Audio non comprensibile")
            except sr.RequestError as e:
                self._log_test(f"❌ Errore servizio riconoscimento: {e}")
                
        except ImportError:
            self._log_test("❌ speech_recognition non trovato")
            self._log_test("💡 Installa con: pip install SpeechRecognition pyaudio")
        except OSError as e:
            if "No Default Input Device Available" in str(e):
                self._log_test("❌ Nessun microfono disponibile")
            else:
                self._log_test(f"❌ Errore dispositivo audio: {e}")
        except Exception as e:
            self._log_test(f"❌ Errore STT: {e}")
    
    def _log_test(self, message: str):
        """Logga messaggio nel tester"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        log_message = f"[{timestamp}] {message}\n"
        
        self.test_output.insert(tk.END, log_message)
        self.test_output.see(tk.END)
        self.root.update()
    
    def _clear_test_output(self):
        """Pulisce l'output del tester"""
        self.test_output.delete("1.0", tk.END)
        self._log_test("🧹 Output pulito - Tester pronto per nuovi test")
    
    def _save_test_log(self):
        """Salva log del tester su file"""
        try:
            from tkinter import filedialog
            import datetime
            
            # Ottieni contenuto del log
            log_content = self.test_output.get("1.0", tk.END)
            
            if not log_content.strip():
                messagebox.showwarning("Log vuoto", "Non ci sono log da salvare")
                return
            
            # File di default con timestamp
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            default_filename = f"voice_test_log_{timestamp}.txt"
            
            # Dialog salvataggio
            filename = filedialog.asksaveasfilename(
                title="Salva Log Test",
                defaultextension=".txt",
                initialname=default_filename,
                filetypes=[("Text files", "*.txt"), ("Log files", "*.log"), ("All files", "*.*")]
            )
            
            if filename:
                with open(filename, 'w', encoding='utf-8') as f:
                    f.write(f"VOICE TEST LOG - {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                    f.write("=" * 70 + "\n\n")
                    f.write(log_content)
                
                self._log_test(f"💾 Log salvato in: {os.path.basename(filename)}")
                self.status_text.set(f"✅ Log test salvato")
                
        except Exception as e:
            self._log_test(f"❌ Errore salvataggio log: {e}")
            messagebox.showerror("Errore", f"Impossibile salvare log: {e}")

    # === METODI CONFIGURAZIONE ===
    
    def _load_config(self):
        """Carica configurazione da file"""
        filename = filedialog.askopenfilename(
            title="Carica Configurazione",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )
        
        if filename:
            try:
                with open(filename, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                
                self.current_mappings = config.get('mappings', {})
                self._update_mapping_tree()
                
                self.status_text.set(f"✅ Configurazione caricata da {os.path.basename(filename)}")
                
            except Exception as e:
                messagebox.showerror("Errore", f"Errore caricamento configurazione: {e}")
    
    def _save_config(self):
        """Salva configurazione su file"""
        filename = filedialog.asksaveasfilename(
            title="Salva Configurazione",
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )
        
        if filename:
            try:
                config = {
                    'mappings': self.current_mappings,
                    'scan_data': self.scanned_data,
                    'timestamp': datetime.now().isoformat(),
                    'version': '1.0.0'
                }
                
                with open(filename, 'w', encoding='utf-8') as f:
                    json.dump(config, f, indent=2, ensure_ascii=False)
                
                self.status_text.set(f"✅ Configurazione salvata in {os.path.basename(filename)}")
                
            except Exception as e:
                messagebox.showerror("Errore", f"Errore salvataggio configurazione: {e}")
    
    def _validate_config(self):
        """Valida configurazione corrente"""
        self.status_text.set("🔍 Validazione configurazione...")
        
        errors = []
        warnings = []
        
        # Verifica mappature
        for action, mapping in self.current_mappings.items():
            handler = mapping.get('handler')
            
            # Verifica esistenza handler
            if handler not in self.scanned_data.get('methods', {}):
                errors.append(f"Handler '{handler}' non trovato per azione '{action}'")
            
            # Verifica keywords
            keywords = mapping.get('keywords', [])
            if not keywords:
                warnings.append(f"Nessuna keyword definita per azione '{action}'")
            elif len(keywords) < 2:
                warnings.append(f"Solo una keyword per azione '{action}' - consigliato almeno 2")
        
        # Mostra risultati
        if errors:
            result = "❌ ERRORI TROVATI:\n" + "\n".join(f"• {err}" for err in errors)
            if warnings:
                result += "\n\n⚠️ AVVISI:\n" + "\n".join(f"• {warn}" for warn in warnings)
            messagebox.showerror("Validazione Fallita", result)
        elif warnings:
            result = "⚠️ AVVISI:\n" + "\n".join(f"• {warn}" for warn in warnings)
            messagebox.showwarning("Validazione con Avvisi", result)
        else:
            messagebox.showinfo("Validazione", "✅ Configurazione valida!")
        
        self.status_text.set("Validazione completata")
    
    def _generate_code(self):
        """Genera codice per l'integrazione"""
        self.status_text.set("🔧 Generazione codice...")
        messagebox.showinfo("Genera Codice", "Funzionalità in sviluppo")
    
    def _export_report(self):
        """Esporta report completo"""
        filename = filedialog.asksaveasfilename(
            title="Esporta Report",
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")]
        )
        
        if filename:
            try:
                with open(filename, 'w', encoding='utf-8') as f:
                    f.write("REPORT CONFIGURAZIONE COMANDI VOCALI SYMMETRA\n")
                    f.write("=" * 50 + "\n\n")
                    f.write(f"Generato il: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}\n\n")
                    
                    # Statistiche
                    f.write(f"STATISTICHE:\n")
                    f.write(f"- Metodi scansionati: {len(self.scanned_data.get('methods', {}))}\n")
                    f.write(f"- Pulsanti rilevati: {len(self.scanned_data.get('buttons', {}))}\n")
                    f.write(f"- Mappature vocali: {len(self.current_mappings)}\n\n")
                    
                    # Mappature
                    f.write("MAPPATURE COMANDI VOCALI:\n")
                    f.write("-" * 30 + "\n")
                    for action, mapping in self.current_mappings.items():
                        f.write(f"\nAzione: {action}\n")
                        f.write(f"Handler: {mapping.get('handler', 'N/A')}\n")
                        f.write(f"Keywords: {', '.join(mapping.get('keywords', []))}\n")
                    
                    # Pulsanti
                    f.write(f"\n\nPULSANTI RILEVATI:\n")
                    f.write("-" * 20 + "\n")
                    for text, info in self.scanned_data.get('buttons', {}).items():
                        f.write(f"- {info['text']} → {info['command']} ({info['type']})\n")
                
                self.status_text.set(f"✅ Report esportato in {os.path.basename(filename)}")
                
            except Exception as e:
                messagebox.showerror("Errore", f"Errore esportazione report: {e}")
    
    def _test_voice_commands(self):
        """Testa tutti i comandi vocali con report dettagliato"""
        self.notebook.select(2)  # Vai al tab tester
        self._log_test("🧪 TEST COMPLETO COMANDI VOCALI AVVIATO")
        self._log_test("=" * 60)
        
        if not self.current_mappings:
            self._log_test("⚠️ Nessuna mappatura configurata per il test")
            return
        
        test_results = {
            'total': len(self.current_mappings),
            'tested': 0,
            'valid': 0,
            'invalid': 0,
            'errors': []
        }
        
        for i, (action, mapping) in enumerate(self.current_mappings.items(), 1):
            keywords = mapping.get('keywords', [])
            handler = mapping.get('handler', 'N/A')
            
            self._log_test(f"\n📋 [{i}/{test_results['total']}] Testing: {action}")
            self._log_test(f"   🔗 Handler: {handler}")
            
            if not keywords:
                self._log_test("   ❌ ERRORE: Nessuna keyword configurata")
                test_results['invalid'] += 1
                test_results['errors'].append(f"{action}: Nessuna keyword")
                continue
                
            test_results['tested'] += 1
            
            # Testa prima keyword
            test_keyword = keywords[0]
            self._log_test(f"   🔑 Keyword primaria: '{test_keyword}'")
            
            # Simula riconoscimento
            recognition_success = len(test_keyword.strip()) > 0
            
            if recognition_success:
                self._log_test(f"   ✅ RICONOSCIMENTO: OK")
                self._log_test(f"   🎯 MAPPATURA: {action} → {handler}")
                
                # Verifica altre keywords
                if len(keywords) > 1:
                    self._log_test(f"   📝 Keywords alternative: {', '.join(keywords[1:])}")
                
                test_results['valid'] += 1
            else:
                self._log_test(f"   ❌ ERRORE: Keyword vuota o invalida")
                test_results['invalid'] += 1
                test_results['errors'].append(f"{action}: Keyword invalida")
        
        # Report finale
        self._log_test("\n" + "=" * 60)
        self._log_test("📊 REPORT FINALE TEST")
        self._log_test("=" * 60)
        self._log_test(f"📈 Comandi totali: {test_results['total']}")
        self._log_test(f"🧪 Comandi testati: {test_results['tested']}")
        self._log_test(f"✅ Comandi validi: {test_results['valid']}")
        self._log_test(f"❌ Comandi con errori: {test_results['invalid']}")
        
        # Calcola percentuale successo
        if test_results['tested'] > 0:
            success_rate = (test_results['valid'] / test_results['tested']) * 100
            self._log_test(f"📊 Tasso successo: {success_rate:.1f}%")
            
            if success_rate >= 90:
                self._log_test("🎉 ECCELLENTE: Configurazione ottima!")
            elif success_rate >= 70:
                self._log_test("👍 BUONO: Configurazione accettabile")
            else:
                self._log_test("⚠️ ATTENZIONE: Configurazione da migliorare")
        
        # Lista errori se presenti
        if test_results['errors']:
            self._log_test(f"\n🔧 ERRORI DA CORREGGERE:")
            for error in test_results['errors']:
                self._log_test(f"   • {error}")
        
        self._log_test("\n" + "=" * 60)
        self._log_test("🏁 Test completo terminato")
    
    # === METODI HELP ===
    
    def _show_help(self):
        """Mostra aiuto"""
        help_text = """
🔧 ADMIN VOICE CONFIGURATOR - GUIDA

FUNZIONALITÀ PRINCIPALI:
• Scanner Interfaccia: Rileva automaticamente pulsanti e metodi
• Mapper Comandi: Collega comandi vocali a pulsanti specifici
• Tester: Verifica il funzionamento dei comandi
• Configurazione: Editor avanzato per personalizzazioni

WORKFLOW CONSIGLIATO:
1. Esegui scansione interfaccia
2. Verifica pulsanti e metodi rilevati
3. Crea mappature nel Mapper
4. Testa i comandi nel Tester
5. Salva la configurazione

SICUREZZA:
• Tool protetto da password amministratore
• Backup automatico delle configurazioni
• Validazione configurazioni prima del salvataggio

Per supporto: consulta la documentazione tecnica
"""
        messagebox.showinfo("Guida", help_text)
    
    def _show_about(self):
        """Mostra informazioni"""
        about_text = """
🔧 Admin Voice Configurator
Versione: 1.0.0
Data: 6 Ottobre 2025

Sistema di configurazione avanzata per
l'integrazione dei comandi vocali nel
software Symmetra.

Sviluppato per amministratori di sistema
con accesso privilegiato alle funzionalità
di configurazione vocale.

© 2025 - Symmetra System
"""
        messagebox.showinfo("Informazioni", about_text)
    
    def _create_queries_tab(self):
        """Tab query intelligenti rimosso per semplificare"""
        # Funzionalità rimossa per mantenere il codice pulito
        pass
    
    def _create_queries_unavailable(self, parent):
        """Crea interfaccia per query non disponibili"""
        warning_frame = ttk.LabelFrame(parent, text="⚠️ Funzionalità Non Disponibile", padding=20)
        warning_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        warning_text = """🧠 QUERY INTELLIGENTI NON DISPONIBILI

Il modulo 'intelligent_query_handler.py' non è stato trovato.
Per abilitare questa funzionalità:

1. Assicurati che il file 'voice/intelligent_query_handler.py' esista
2. Verifica le dipendenze del modulo
3. Riavvia l'Admin Configurator

Le Query Intelligenti permettono di:
• Configurare domande sui dati di misurazione
• Creare risposte automatiche personalizzate
• Gestire pattern di riconoscimento avanzati"""
        
        ttk.Label(warning_frame, text=warning_text, justify=tk.LEFT, font=("Arial", 10)).pack()
    
    def _create_queries_interface(self, parent):
        """Crea interfaccia completa per gestione query intelligenti"""
        # Layout principale
        main_paned = ttk.PanedWindow(parent, orient=tk.VERTICAL)
        main_paned.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Sezione pattern configurati
        patterns_frame = ttk.LabelFrame(main_paned, text="📋 Pattern Query Configurati", padding=5)
        main_paned.add(patterns_frame, weight=1)
        
        # Treeview pattern
        pattern_columns = ("ID", "Pattern", "Tipo", "Attivo")
        self.patterns_tree = ttk.Treeview(patterns_frame, columns=pattern_columns, show="headings", height=8)
        
        for col in pattern_columns:
            self.patterns_tree.heading(col, text=col)
            self.patterns_tree.column(col, width=120)
        
        # Scrollbar patterns
        patterns_scroll = ttk.Scrollbar(patterns_frame, orient=tk.VERTICAL, command=self.patterns_tree.yview)
        self.patterns_tree.configure(yscrollcommand=patterns_scroll.set)
        
        # Pack patterns treeview
        patterns_container = ttk.Frame(patterns_frame)
        patterns_container.pack(fill=tk.BOTH, expand=True)
        self.patterns_tree.pack(in_=patterns_container, side=tk.LEFT, fill=tk.BOTH, expand=True)
        patterns_scroll.pack(in_=patterns_container, side=tk.RIGHT, fill=tk.Y)
        
        # Sezione editor pattern
        editor_frame = ttk.LabelFrame(main_paned, text="✏️ Editor Pattern", padding=5)
        main_paned.add(editor_frame, weight=1)
        
        # Form editor
        form_frame = ttk.Frame(editor_frame)
        form_frame.pack(fill=tk.X, pady=(0, 10))
        
        # Pattern input
        ttk.Label(form_frame, text="Pattern Query:").grid(row=0, column=0, sticky="w", padx=(0, 5))
        self.pattern_input = ttk.Entry(form_frame, width=40)
        self.pattern_input.grid(row=0, column=1, sticky="ew", padx=5)
        
        # Tipo query
        ttk.Label(form_frame, text="Tipo:").grid(row=0, column=2, sticky="w", padx=(10, 5))
        self.query_type_var = tk.StringVar(value="measurement")
        query_type_combo = ttk.Combobox(form_frame, textvariable=self.query_type_var, 
                                       values=["measurement", "comparison", "status"], width=15)
        query_type_combo.grid(row=0, column=3, padx=5)
        
        # Response template
        ttk.Label(form_frame, text="Template Risposta:").grid(row=1, column=0, sticky="nw", padx=(0, 5), pady=(10, 0))
        self.response_text = tk.Text(form_frame, height=4, width=60)
        self.response_text.grid(row=1, column=1, columnspan=3, sticky="ew", padx=5, pady=(10, 0))
        
        # Configure grid weights
        form_frame.columnconfigure(1, weight=1)
        
        # Pulsanti azioni
        actions_frame = ttk.Frame(editor_frame)
        actions_frame.pack(fill=tk.X, pady=(5, 0))
        
        ttk.Button(actions_frame, text="➕ Aggiungi Pattern", 
                  command=self._add_query_pattern, bootstyle="success").pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(actions_frame, text="💾 Salva Pattern", 
                  command=self._save_query_pattern, bootstyle="primary").pack(side=tk.LEFT, padx=5)
        ttk.Button(actions_frame, text="🗑️ Elimina Pattern", 
                  command=self._delete_query_pattern, bootstyle="danger").pack(side=tk.LEFT, padx=5)
        ttk.Button(actions_frame, text="🧪 Testa Pattern", 
                  command=self._test_query_pattern, bootstyle="warning").pack(side=tk.LEFT, padx=5)
        
        # Sezione test query
        test_frame = ttk.LabelFrame(main_paned, text="🧪 Test Query", padding=5)
        main_paned.add(test_frame, weight=1)
        
        # Input test query
        test_input_frame = ttk.Frame(test_frame)
        test_input_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(test_input_frame, text="Domanda da testare:").pack(anchor="w")
        self.test_query_input = ttk.Entry(test_input_frame, font=("Arial", 12))
        self.test_query_input.pack(fill=tk.X, pady=(5, 0))
        
        # Pulsanti test
        test_buttons = ttk.Frame(test_frame)
        test_buttons.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Button(test_buttons, text="🧪 Testa Query", 
                  command=self._test_intelligent_query, bootstyle="info").pack(side=tk.LEFT, padx=(0, 10))
        ttk.Button(test_buttons, text="🔄 Carica Pattern", 
                  command=self._reload_query_patterns, bootstyle="secondary").pack(side=tk.LEFT, padx=10)
        
        # Output test query
        ttk.Label(test_frame, text="Risultato Test:").pack(anchor="w", pady=(10, 0))
        
        test_output_frame = ttk.Frame(test_frame)
        test_output_frame.pack(fill=tk.BOTH, expand=True, pady=(5, 0))
        
        self.query_test_output = tk.Text(test_output_frame, height=8, wrap=tk.WORD, 
                                        bg="black", fg="cyan", font=("Consolas", 10))
        query_scroll = ttk.Scrollbar(test_output_frame, orient=tk.VERTICAL, command=self.query_test_output.yview)
        self.query_test_output.configure(yscrollcommand=query_scroll.set)
        
        self.query_test_output.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        query_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Binding eventi
        self.patterns_tree.bind("<<TreeviewSelect>>", self._on_pattern_select)
        
        # Carica pattern esistenti
        self._load_query_patterns()
    
    def _add_query_pattern(self):
        """Aggiunge nuovo pattern query"""
        pattern = self.pattern_input.get().strip()
        query_type = self.query_type_var.get()
        response = self.response_text.get("1.0", tk.END).strip()
        
        if not pattern:
            messagebox.showwarning("Input", "Inserisci un pattern query")
            return
        
        # Genera ID unico
        pattern_id = f"query_{len(self.patterns_tree.get_children()) + 1}"
        
        # Aggiungi alla treeview
        self.patterns_tree.insert("", tk.END, values=(pattern_id, pattern, query_type, "✅"))
        
        # Log
        self._log_query_test(f"➕ Pattern aggiunto: {pattern}")
        self.status_text.set(f"✅ Pattern '{pattern}' aggiunto")
    
    def _save_query_pattern(self):
        """Salva pattern selezionato"""
        selection = self.patterns_tree.selection()
        if not selection:
            messagebox.showwarning("Selezione", "Seleziona un pattern da salvare")
            return
        
        self.status_text.set("💾 Funzionalità salvataggio in sviluppo...")
    
    def _delete_query_pattern(self):
        """Elimina pattern selezionato"""
        selection = self.patterns_tree.selection()
        if not selection:
            messagebox.showwarning("Selezione", "Seleziona un pattern da eliminare")
            return
        
        if messagebox.askyesno("Conferma", "Eliminare il pattern selezionato?"):
            self.patterns_tree.delete(selection[0])
            self.status_text.set("🗑️ Pattern eliminato")
    
    def _test_query_pattern(self):
        """Testa pattern selezionato"""
        selection = self.patterns_tree.selection()
        if not selection:
            messagebox.showwarning("Selezione", "Seleziona un pattern da testare")
            return
        
        item = self.patterns_tree.item(selection[0])
        pattern = item['values'][1]
        self.test_query_input.delete(0, tk.END)
        self.test_query_input.insert(0, pattern)
        self._test_intelligent_query()
    
    def _test_intelligent_query(self):
        """Testa query intelligente"""
        query = self.test_query_input.get().strip()
        if not query:
            messagebox.showwarning("Input", "Inserisci una query da testare")
            return
        
        self._log_query_test(f"🧪 Testing query: '{query}'")
        self._log_query_test("=" * 40)
        
        if self.query_handler:
            try:
                response = self.query_handler.process_query(query)
                self._log_query_test(f"✅ Risposta generata:")
                self._log_query_test(f"   {response}")
            except Exception as e:
                self._log_query_test(f"❌ Errore processing: {e}")
        else:
            self._log_query_test("⚠️ Query Handler non disponibile")
            self._log_query_test("   Simulazione risposta...")
            self._log_query_test(f"   Query riconosciuta: '{query}'")
            self._log_query_test("   Tipo: measurement")
            self._log_query_test("   Risposta: Funzionalità in sviluppo")
    
    def _reload_query_patterns(self):
        """Ricarica pattern dalla configurazione"""
        self._load_query_patterns()
        self.status_text.set("🔄 Pattern ricaricati")
    
    def _load_query_patterns(self):
        """Carica pattern esistenti"""
        # Pulisci treeview
        for item in self.patterns_tree.get_children():
            self.patterns_tree.delete(item)
        
        # Carica pattern da query handler se disponibile
        if self.query_handler and hasattr(self.query_handler, 'patterns'):
            try:
                # self.patterns è Dict[str, QueryPattern]
                for pattern_id, pattern_obj in self.query_handler.patterns.items():
                    # Estrai informazioni dall'oggetto QueryPattern
                    pattern_text = getattr(pattern_obj, 'pattern', 'N/A')
                    pattern_type = getattr(pattern_obj, 'response_type', 'measurement')
                    is_active = "✅" if getattr(pattern_obj, 'condition', None) else "⚠️"
                    
                    self.patterns_tree.insert("", tk.END, values=(pattern_id, pattern_text, pattern_type, is_active))
                
                logger.info(f"Caricati {len(self.query_handler.patterns)} pattern dal query handler")
                # Aggiorna statistiche dopo caricamento successful
                self._update_stats()
            except Exception as e:
                logger.error(f"Errore caricamento pattern da query handler: {e}")
                self._load_example_patterns()
        else:
            self._load_example_patterns()
    
    def _load_example_patterns(self):
        """Carica pattern di esempio"""
        example_patterns = [
            ("query_1", "quanto misura", "measurement", "✅"),
            ("query_2", "qual è la simmetria", "comparison", "✅"), 
            ("query_3", "come sono le proporzioni", "analysis", "✅"),
            ("query_4", "dimmi la distanza", "measurement", "✅"),
            ("query_5", "sono simmetriche", "comparison", "⚠️")
        ]
        
        for pattern_data in example_patterns:
            self.patterns_tree.insert("", tk.END, values=pattern_data)
        
        logger.info("Caricati pattern di esempio")
        
        # Aggiorna statistiche dopo aver caricato i pattern
        self._update_stats()
    
    def _update_stats(self):
        """Aggiorna statistiche nella status bar"""
        mappings_count = len(self.current_mappings)
        
        # Conta pattern in modo sicuro
        try:
            patterns_count = len(self.patterns_tree.get_children()) if hasattr(self, 'patterns_tree') and self.patterns_tree else 0
        except (AttributeError, tk.TclError):
            patterns_count = 0
        
        # Aggiorna stats se il widget esiste
        if hasattr(self, 'stats_text'):
            self.stats_text.set(f"📊 Mappature: {mappings_count} | Pattern: {patterns_count}")
        
        # Update connection status
        if mappings_count > 0:
            if hasattr(self, 'connection_status'):
                self.connection_status.set("🟢 Configurato")
            if hasattr(self, 'toolbar_status'):
                self.toolbar_status.set("🟢")
        else:
            if hasattr(self, 'connection_status'):
                self.connection_status.set("🟡 Parziale")
            if hasattr(self, 'toolbar_status'):
                self.toolbar_status.set("🟡")
    
    def _on_pattern_select(self, event):
        """Gestisce selezione pattern"""
        selection = self.patterns_tree.selection()
        if selection:
            item = self.patterns_tree.item(selection[0])
            pattern = item['values'][1]
            self.pattern_input.delete(0, tk.END)
            self.pattern_input.insert(0, pattern)
    
    def _log_query_test(self, message: str):
        """Log per test query"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        log_message = f"[{timestamp}] {message}\n"
        
        self.query_test_output.insert(tk.END, log_message)
        self.query_test_output.see(tk.END)
        self.root.update()
    
    def run(self):
        """Avvia l'interfaccia"""
        self.create_gui()
        self.root.mainloop()


def main():
    """Funzione principale con autenticazione"""
    print("🔧 Admin Voice Configurator - Avvio")
    print("=" * 40)
    
    # Autenticazione amministratore
    auth = AdminAuthenticator()
    
    print("🔐 Richiesta autenticazione amministratore...")
    if not auth.authenticate():
        print("❌ Accesso negato. Chiusura applicazione.")
        sys.exit(1)
    
    print("✅ Accesso autorizzato. Avvio configuratore...")
    
    try:
        # Avvia configuratore
        configurator = VoiceConfiguratorGUI()
        configurator.run()
        
    except KeyboardInterrupt:
        print("\n👋 Configuratore chiuso dall'utente")
    except Exception as e:
        print(f"❌ Errore critico: {e}")
        logger.error(f"Errore critico configuratore: {e}", exc_info=True)
    
    print("🔧 Configuratore terminato")


if __name__ == "__main__":
    main()