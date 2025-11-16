#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script de verificación de integridad de archivos críticos
Verifica que los archivos esenciales del sistema estén presentes
"""

import os
import sys

def check_critical_files():
    """Verifica que todos los archivos críticos estén presentes"""
    
    # Directorio base del proyecto
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    run_dir = os.path.join(base_dir, "run")
    
    # Archivos críticos que deben existir
    critical_files = {
        "VERSION": os.path.join(run_dir, "VERSION"),
        ".gitkeep": os.path.join(run_dir, ".gitkeep"),
        "run_flask_app.py": os.path.join(run_dir, "run_flask_app.py"),
        "README.md": os.path.join(run_dir, "README.md")
    }
    
    missing_files = []
    
    print("🔍 Verificando archivos críticos del sistema...")
    
    for name, path in critical_files.items():
        if os.path.exists(path):
            print(f"✅ {name}: OK")
        else:
            print(f"❌ {name}: FALTA")
            missing_files.append(name)
    
    if missing_files:
        print(f"\n⚠️  ADVERTENCIA: Faltan {len(missing_files)} archivo(s) crítico(s):")
        for file in missing_files:
            print(f"   - {file}")
        print("\n🛠️  Soluciones:")
        print("   1. Restaurar archivos desde el repositorio Git")
        print("   2. Contactar con el desarrollador")
        print("   3. Re-clonar el repositorio si es necesario")
        return False
    else:
        print("\n✅ Todos los archivos críticos están presentes")
        return True

def restore_version_file():
    """Restaura el archivo VERSION si falta"""
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    version_file = os.path.join(base_dir, "run", "VERSION")
    
    if not os.path.exists(version_file):
        print("🛠️  Restaurando archivo VERSION...")
        try:
            with open(version_file, "w", encoding="utf-8") as f:
                f.write("2.0")
            print("✅ Archivo VERSION restaurado exitosamente")
            return True
        except Exception as e:
            print(f"❌ Error al restaurar VERSION: {e}")
            return False
    return True

if __name__ == "__main__":
    print("=" * 50)
    print("🔒 Verificador de Integridad - DCS Traductor Español")
    print("=" * 50)
    
    # Verificar archivos críticos
    integrity_ok = check_critical_files()
    
    if not integrity_ok:
        print("\n🛠️  ¿Intentar restaurar archivo VERSION automáticamente? (s/n): ", end="")
        response = input().lower().strip()
        if response in ['s', 'si', 'y', 'yes']:
            restore_version_file()
            # Verificar nuevamente
            print("\n🔄 Verificando nuevamente...")
            check_critical_files()
    
    print("\n" + "=" * 50)
    print("Verificación completada.")
    print("=" * 50)