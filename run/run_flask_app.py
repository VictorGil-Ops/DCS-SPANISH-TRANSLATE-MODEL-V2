#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script de arranque para la aplicación Flask DCS Orquestador Traductor
"""
import os
import sys
from pathlib import Path

# Asegurar que estamos en el directorio correcto del proyecto
SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent
os.chdir(PROJECT_ROOT)

# Agregar el directorio del proyecto al path
sys.path.insert(0, str(PROJECT_ROOT))

def main():
    """Función principal para arrancar la aplicación Flask"""
    
    try:
        # Importar la aplicación Flask
        from app import create_app
        
        print("🚀 DCS Orquestador Traductor - Versión Flask Modular")
        print("=" * 60)
        print("📋 Información del servidor:")
        print("   📍 URL Local:    http://localhost:5000")
        print("   🌐 URL Red:      http://0.0.0.0:5000")  
        print("   ⚡ Modo:         Producción")
        print("   🔧 Threading:    Activado")
        print("   📁 Directorio:   " + str(PROJECT_ROOT))
        print("=" * 60)
        print("💡 Funcionalidades disponibles:")
        print("   ✅ Orquestador de traducciones DCS")
        print("   ✅ Integración con LM Studio")
        print("   ✅ Gestión de campañas y misiones")
        print("   ✅ Presets de configuración")
        print("   ✅ API RESTful")
        print("   ✅ Interface web moderna")
        print("=" * 60)
        print("🎯 Presiona Ctrl+C para detener el servidor")
        print("")
        
        # Crear y configurar la aplicación
        app = create_app()
        
        # Configuración del servidor
        app.run(
            host='0.0.0.0',         # Accesible desde la red
            port=5000,              # Puerto estándar
            debug=False,            # Modo producción
            threaded=True,          # Soporte multi-thread
            use_reloader=False      # Sin auto-reload en producción
        )
        
    except ImportError as e:
        print("❌ Error de importación:")
        print(f"   {e}")
        print("\n🔧 Soluciones posibles:")
        print("   1. Verificar que todos los archivos estén presentes")
        print("   2. Ejecutar desde el directorio correcto")
        print("   3. Verificar dependencias: pip install flask")
        sys.exit(1)
        
    except KeyboardInterrupt:
        print("\n")
        print("👋 Servidor detenido por el usuario")
        print("💾 Todos los datos han sido guardados")
        
    except OSError as e:
        if "Address already in use" in str(e):
            print("❌ Error: Puerto 5000 ya está en uso")
            print("\n🔧 Soluciones:")
            print("   1. Detener el proceso que usa el puerto 5000")
            print("   2. Cambiar el puerto en este script")
            print("   3. Usar: netstat -ano | findstr :5000 (Windows)")
        else:
            print(f"❌ Error del sistema: {e}")
        sys.exit(1)
        
    except Exception as e:
        print(f"💥 Error inesperado al arrancar la aplicación:")
        print(f"   {e}")
        print("\n🔍 Para más detalles:")
        import traceback
        traceback.print_exc()
        sys.exit(1)

def check_requirements():
    """Verificar que los requisitos básicos estén presentes"""
    
    # Verificar estructura de directorios
    required_dirs = [
        'app',
        'app/routes', 
        'app/services',
        'app/templates',
        'app/static',
        'config'
    ]
    
    missing_dirs = []
    for dir_name in required_dirs:
        if not (PROJECT_ROOT / dir_name).exists():
            missing_dirs.append(dir_name)
    
    if missing_dirs:
        print("❌ Faltan directorios requeridos:")
        for dir_name in missing_dirs:
            print(f"   - {dir_name}")
        print("\n🔧 Ejecuta el script de migración o verifica la estructura")
        return False
    
    # Verificar archivos clave
    required_files = [
        'app/__init__.py',
        'app/routes/main.py', 
        'app/routes/api.py',
        'config/settings.py'
    ]
    
    missing_files = []
    for file_name in required_files:
        if not (PROJECT_ROOT / file_name).exists():
            missing_files.append(file_name)
    
    if missing_files:
        print("❌ Faltan archivos requeridos:")
        for file_name in missing_files:
            print(f"   - {file_name}")
        return False
    
    return True

if __name__ == "__main__":
    print("🔍 Verificando requisitos...")
    
    if not check_requirements():
        print("\n❌ Verificación de requisitos falló")
        sys.exit(1)
    
    print("✅ Requisitos verificados")
    print()
    
    main()