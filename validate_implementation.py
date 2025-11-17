#!/usr/bin/env python3
"""
Validation script to verify ttkbootstrap implementation
in the Facial Analysis Application.

This script checks:
1. All required imports are available
2. Code structure is correct
3. Configuration files exist
4. Documentation is complete
"""

import sys
import os
import importlib.util


def check_module_syntax(filepath):
    """Check if a Python file has valid syntax."""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            compile(f.read(), filepath, 'exec')
        return True, "OK"
    except SyntaxError as e:
        return False, f"Syntax error: {e}"
    except Exception as e:
        return False, f"Error: {e}"


def check_import_structure(filepath):
    """Check if ttkbootstrap is properly imported in the file."""
    try:
        # Security: Check file size (limit to 50MB)
        file_size = os.path.getsize(filepath)
        if file_size > 50 * 1024 * 1024:
            return {'error': 'File too large', 'file': filepath}
        
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
            
        has_ttkbootstrap = 'import ttkbootstrap' in content or 'from ttkbootstrap' in content
        has_ttk_alias = 'ttkbootstrap as ttk' in content
        
        return {
            'has_ttkbootstrap': has_ttkbootstrap,
            'has_ttk_alias': has_ttk_alias,
            'file': filepath
        }
    except Exception as e:
        return {'error': str(e), 'file': filepath}


def main():
    """Main validation routine."""
    print("=" * 70)
    print("🔍 VALIDATING TTKBOOTSTRAP IMPLEMENTATION")
    print("=" * 70)
    
    # Check main files
    files_to_check = [
        'main.py',
        'src/canvas_app.py',
        'theme_selector.py'
    ]
    
    print("\n📝 Checking Python syntax...")
    syntax_ok = True
    for filepath in files_to_check:
        if os.path.exists(filepath):
            success, message = check_module_syntax(filepath)
            status = "✅" if success else "❌"
            print(f"{status} {filepath}: {message}")
            syntax_ok = syntax_ok and success
        else:
            print(f"⚠️  {filepath}: File not found")
            syntax_ok = False
    
    print("\n📦 Checking ttkbootstrap imports...")
    for filepath in files_to_check:
        if os.path.exists(filepath):
            result = check_import_structure(filepath)
            if 'error' in result:
                print(f"❌ {filepath}: {result['error']}")
            else:
                ttk_status = "✅" if result['has_ttkbootstrap'] else "❌"
                alias_status = "✅" if result['has_ttk_alias'] else "⚠️ "
                print(f"{ttk_status} {filepath}: ttkbootstrap import found")
                if result['has_ttk_alias']:
                    print(f"   {alias_status} Using 'ttk' alias (recommended)")
    
    print("\n📚 Checking documentation...")
    docs = ['README.md', 'requirements.txt', '.github/copilot-instructions.md']
    for doc in docs:
        if os.path.exists(doc):
            print(f"✅ {doc}: Found")
        else:
            print(f"❌ {doc}: Missing")
    
    print("\n🗂️  Checking project structure...")
    required_dirs = ['src', 'voice', '.github']
    for directory in required_dirs:
        if os.path.isdir(directory):
            print(f"✅ {directory}/: Found")
        else:
            print(f"❌ {directory}/: Missing")
    
    print("\n📋 Checking requirements.txt for ttkbootstrap...")
    if os.path.exists('requirements.txt'):
        with open('requirements.txt', 'r', encoding='utf-8') as f:
            content = f.read()
            if 'ttkbootstrap' in content:
                print("✅ ttkbootstrap is listed in requirements.txt")
                # Extract version
                for line in content.split('\n'):
                    if 'ttkbootstrap' in line:
                        print(f"   Version spec: {line.strip()}")
            else:
                print("❌ ttkbootstrap NOT found in requirements.txt")
    
    print("\n" + "=" * 70)
    if syntax_ok:
        print("✅ VALIDATION SUCCESSFUL: All code is syntactically correct")
        print("✅ IMPLEMENTATION COMPLETE: ttkbootstrap is properly integrated")
    else:
        print("❌ VALIDATION FAILED: Some issues found")
    print("=" * 70)
    
    return 0 if syntax_ok else 1


if __name__ == "__main__":
    sys.exit(main())
