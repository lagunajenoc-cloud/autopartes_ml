#!/usr/bin/env python3
"""
Archivo principal para ejecutar la aplicación AutoPartes ML
"""

import os
import sys
from pathlib import Path

# Obtener directorios
current_dir = Path(__file__).parent.absolute()
sys.path.insert(0, str(current_dir))

print(f"🚀 Iniciando AutoPartes ML...")
print(f"📁 Directorio actual: {current_dir}")

try:
    # Importar create_app
    from app import create_app
    print("✅ Módulo app importado correctamente")
    
    # Crear aplicación
    app = create_app()
    print("✅ Aplicación creada correctamente")
    
    if __name__ == '__main__':
        print("🌐 Iniciando servidor de desarrollo...")
        print("📍 URL: http://127.0.0.1:5000")
        print("🔗 Comprobantes: http://127.0.0.1:5000/comprobantes")
        print("⏹️  Presiona Ctrl+C para detener")
        
        app.run(
            debug=True,
            host='127.0.0.1',
            port=5000
        )
        
except ImportError as e:
    print(f"❌ Error al importar app: {e}")
    print("\n🔍 Verificando estructura de archivos...")
    
    # Verificar archivos críticos
    archivos_criticos = [
        'app/__init__.py',
        'app/models/__init__.py',
        'app/controllers/__init__.py',
        'config.py'
    ]
    
    for archivo in archivos_criticos:
        ruta = current_dir / archivo
        if ruta.exists():
            print(f"✅ {archivo}")
        else:
            print(f"❌ {archivo} - NO ENCONTRADO")
    
    print(f"\n📋 Contenido de app/:")
    try:
        app_dir = current_dir / 'app'
        if app_dir.exists():
            for item in app_dir.iterdir():
                print(f"   - {item.name}")
        else:
            print("   ❌ Carpeta app/ no encontrada")
    except Exception as e:
        print(f"   ❌ Error listando app/: {e}")
    
    print(f"\n📋 Contenido de app/controllers/:")
    try:
        controllers_dir = current_dir / 'app' / 'controllers'
        if controllers_dir.exists():
            for item in controllers_dir.iterdir():
                if item.name.endswith('.py'):
                    print(f"   - {item.name}")
        else:
            print("   ❌ Carpeta app/controllers/ no encontrada")
    except Exception as e:
        print(f"   ❌ Error listando controllers/: {e}")
    
    # Fallback básico
    print("\n🚨 Iniciando en modo fallback...")
    from flask import Flask
    app = Flask(__name__)
    
    @app.route('/')
    def index():
        return """
        <h1>🚨 Aplicación en modo fallback</h1>
        <p>Hubo errores al configurar la aplicación.</p>
        <p>Revisa los mensajes de error en la consola.</p>
        <hr>
        <p>Pasos para solucionar:</p>
        <ol>
            <li>Verifica que todos los archivos estén creados</li>
            <li>Revisa los imports en app/__init__.py</li>
            <li>Ejecuta: python inicializar_comprobantes.py</li>
        </ol>
        """
    
    if __name__ == '__main__':
        print("🌐 Servidor fallback en: http://127.0.0.1:5000")
        app.run(debug=True, host='127.0.0.1', port=5000)

except Exception as e:
    print(f"❌ Error inesperado: {e}")
    import traceback
    traceback.print_exc()