from flask import Flask
from flask_migrate import Migrate
from flask_login import LoginManager
from app import db

migrate = Migrate()
login_manager = LoginManager()

def create_app(config_name='default'):
    app = Flask(
        __name__,
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

    # Registrar blueprints de forma segura
    with app.app_context():

        # AUTH
        try:
            from app.controllers.auth_controller import auth_bp
            app.register_blueprint(auth_bp)
            print("✅ auth_bp registrado")
        except ImportError as e:
            print(f"❌ Error auth_bp: {e}")

        # VENTAS
        try:
            from app.controllers.ventas_controller import ventas_bp
            app.register_blueprint(ventas_bp)
            print("✅ ventas_bp registrado")
        except ImportError as e:
            print(f"❌ Error ventas_bp: {e}")

        # INVENTARIO
        try:
            from app.controllers.inventario_controller import inventario_bp
            app.register_blueprint(inventario_bp)
            print("✅ inventario_bp registrado")
        except ImportError as e:
            print(f"❌ Error inventario_bp: {e}")

        # ML (opcional)
        try:
            import pandas  # valida dependencia
            from app.controllers.ml_controller import ml_bp
            app.register_blueprint(ml_bp)
            print("✅ ml_bp registrado")
        except Exception as e:
            print(f"❌ ML desactivado: {e}")

        # DASHBOARD
        try:
            from app.controllers.dashboard_controller import dashboard_bp
            app.register_blueprint(dashboard_bp)
            print("✅ dashboard_bp registrado")
        except ImportError as e:
            print(f"❌ Error dashboard_bp: {e}")

        # COMPROBANTE
        try:
            from app.controllers.comprobante_controller import comprobante_bp
            app.register_blueprint(comprobante_bp)
            print("✅ comprobante_bp registrado")
        except ImportError as e:
            print(f"❌ Error comprobante_bp: {e}")

    return app