import os
import sys
from pathlib import Path

# Añadir directorio raíz al path
current_dir = Path(__file__).parent.absolute()
sys.path.insert(0, str(current_dir))

from app import create_app, db
from app.models.usuario import Usuario

# Crear una instancia de la aplicación
app = create_app()

# Crear el usuario admin dentro del contexto de la aplicación
with app.app_context():
    try:
        # Verificar si ya existe el usuario admin
        admin = Usuario.query.filter_by(username='admin').first()
        if admin:
            print("✅ El usuario admin ya existe.")
            print(f"   Username: {admin.username}")
            print(f"   Email: {admin.email}")
            print(f"   Nombre: {admin.nombre} {admin.apellido}")
            print(f"   Rol: {admin.rol}")
            print("   🔑 Usa tu contraseña actual para hacer login")
        else:
            # Crear usuario admin
            admin = Usuario(
                username='admin',
                email='admin@autopartes.com',
                nombre='Administrador',
                apellido='Sistema',
                rol='admin',
                activo=True
            )
            admin.set_password('admin123')  # ¡Cambia esta contraseña en producción!
                    
            # Guardar en la base de datos
            db.session.add(admin)
            db.session.commit()
            
            print("✅ Usuario admin creado exitosamente.")
            print("")
            print("🔑 CREDENCIALES DE LOGIN:")
            print("   Username: admin")
            print("   Password: admin123")
            print("   Email: admin@autopartes.com")
            print("")
            print("🌐 AHORA PUEDES HACER LOGIN EN:")
            print("   http://127.0.0.1:5000/auth/login")
            print("")
            print("📄 DESPUÉS IR A COMPROBANTES:")
            print("   http://127.0.0.1:5000/comprobantes")
        
    except Exception as e:
        print(f"❌ Error al crear/verificar usuario admin: {e}")
        db.session.rollback()
        import traceback
        traceback.print_exc()