from app import db, login_manager
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

class Usuario(UserMixin, db.Model):
    """Modelo para la tabla de usuarios del sistema."""
    __tablename__ = 'usuarios'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    nombre = db.Column(db.String(100))
    apellido = db.Column(db.String(100))
    email = db.Column(db.String(100), unique=True)
    rol = db.Column(db.String(20), nullable=False)  # 'admin', 'vendedor'
    activo = db.Column(db.Boolean, default=True)
    fecha_creacion = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relaciones
    ventas = db.relationship('Venta', backref='usuario', lazy='dynamic')
    
    def __repr__(self):
        return f'<Usuario {self.username} - {self.rol}>'
    
    def to_dict(self):
        """Convertir objeto a diccionario para API/JSON (sin incluir contraseña)."""
        return {
            'id': self.id,
            'username': self.username,
            'nombre': self.nombre,
            'apellido': self.apellido,
            'email': self.email,
            'rol': self.rol,
            'activo': self.activo,
            'fecha_creacion': self.fecha_creacion.isoformat()
        }
    
    def set_password(self, password):
        """Establecer contraseña encriptada."""
        print(f"🔐 Estableciendo contraseña para usuario: {self.username}")
        self.password_hash = generate_password_hash(password)
        print(f"✅ Hash generado: {self.password_hash[:20]}...")
    
    def check_password(self, password):
        """Verificar contraseña."""
        print(f"🔍 Verificando contraseña para usuario: {self.username}")
        print(f"📝 Password recibida: '{password}'")
        print(f"🔒 Hash almacenado: {self.password_hash[:20]}...")
        
        result = check_password_hash(self.password_hash, password)
        print(f"✅ Resultado verificación: {result}")
        return result
    
    def is_admin(self):
        """Verificar si el usuario es administrador."""
        return self.rol == 'admin'
    
    def is_vendedor(self):
        """Verificar si el usuario es vendedor."""
        return self.rol == 'vendedor'
    
    def is_active(self):
        """Flask-Login requiere este método para verificar si el usuario está activo."""
        return self.activo
    
    @classmethod
    def crear_usuario(cls, username, password, rol, email=None, nombre=None, apellido=None):
        """Crear un nuevo usuario."""
        usuario = cls(
            username=username,
            email=email,
            nombre=nombre,
            apellido=apellido,
            rol=rol,
            activo=True
        )
        usuario.set_password(password)
        db.session.add(usuario)
        db.session.commit()
        return usuario


@login_manager.user_loader
def load_user(id):
    """Función requerida por Flask-Login para cargar un usuario."""
    return Usuario.query.get(int(id))