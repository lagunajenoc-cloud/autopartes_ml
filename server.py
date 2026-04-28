from waitress import serve
from app import create_app
import os

# Asegurarse de que el entorno sea de producción
os.environ['FLASK_ENV'] = 'production'

# Tu IP fija configurada
IP_SERVIDOR = "192.168.18.5"
PUERTO = 5000

if __name__ == '__main__':
    try:
        app = create_app()
        
        print("="*50)
        print(f"🚀 SISTEMA INICIADO - AutoPartes ML")
        print(f"📡 IP del Servidor: {IP_SERVIDOR}")
        print(f"🌐 URL para otras PC: http://{IP_SERVIDOR}:{PUERTO}")
        print("="*50)
        print("⏳ Presiona Ctrl+C para detener el servidor")
        
        # host='0.0.0.0' permite conexiones desde toda la red local
        serve(app, host='0.0.0.0', port=PUERTO, threads=10)
        
    except Exception as e:
        print(f"❌ Error al iniciar el servidor: {e}")
        input("Presiona Enter para salir...")