from flask import Flask
from flask_migrate import Migrate
from flask_login import LoginManager
from app import db

migrate = Migrate()
login_manager = LoginManager()

def create_app(config_name='default'):
app = Flask(
**name**,
template_folder='views',
static_folder='static'
)

# Configuración
if config_name == 'default':
    app.config.from_object('config.DevelopmentConfig')
elif config_name == 'production':
    app.config.from_object('config.ProductionConfig')
elif config_name == 'testing':
    app.config.from_object('config.TestingConfig')

# Inicializar extensiones
db.init_app(app)
migrate.init_app(app, db)
login_manager.init_app(app)
login_manager.login_view = 'auth.login'

# 🔥 IMPORTANTE: registrar blueprints SIN try/except
from app.controllers.auth_controller import auth_bp
from app.controllers.ventas_controller import ventas_bp
from app.controllers.inventario_controller import inventario_bp
from app.controllers.dashboard_controller import dashboard_bp
from app.controllers.ml_controller import ml_bp
from app.controllers.comprobante_controller import comprobante_bp

app.register_blueprint(auth_bp)
app.register_blueprint(ventas_bp)
app.register_blueprint(inventario_bp)
app.register_blueprint(dashboard_bp)
app.register_blueprint(ml_bp)  # ✅ ESTE ERA TU PROBLEMA
app.register_blueprint(comprobante_bp)

print("✅ Blueprints registrados correctamente")

return app