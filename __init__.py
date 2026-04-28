migrate = Migrate()
login_manager = LoginManager()

def create_app(config_name='default'):
    app = Flask(__name__, 
                template_folder='views',
                static_folder='static')
    
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
    
    # Registrar blueprints
    with app.app_context():
        try:
            from app.controllers.auth_controller import auth_bp
            from app.controllers.ventas_controller import ventas_bp
            from app.controllers.inventario_controller import inventario_bp
            from app.controllers.ml_controller import ml_bp
            from app.controllers.dashboard_controller import dashboard_bp
            # ✅ CORREGIDO: Importar blueprint de comprobantes
            from app.controllers.comprobante_controller import comprobante_bp
            
            app.register_blueprint(auth_bp)
            app.register_blueprint(ventas_bp)
            app.register_blueprint(inventario_bp)
            app.register_blueprint(ml_bp)
            app.register_blueprint(dashboard_bp)
            # ✅ CORREGIDO: Registrar blueprint de comprobantes (esto solucionaba el error 404)
            app.register_blueprint(comprobante_bp)
        except ImportError as e:
            print(f"Error al importar blueprints: {e}")
    
    return app