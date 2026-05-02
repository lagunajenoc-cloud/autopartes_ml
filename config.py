import os

class Config:
    """Configuración base."""
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'tu_clave_secreta_super_segura_cambiar_en_produccion'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # ✅ SOLUCIÓN DEFINITIVA PARA EL ERROR DE SSL EN RENDER
    # pool_pre_ping: Verifica si la conexión está viva antes de usarla
    # pool_recycle: Recicla la conexión cada 1800 segundos (30 min) para evitar que se cierre
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_pre_ping": True,
        "pool_recycle": 1800
    }

class DevelopmentConfig(Config):
    """Configuración de desarrollo."""
    DEBUG = True
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or 'postgresql://postgres:12345678@localhost/autopartes_ML'

class ProductionConfig(Config):
    """Configuración de producción."""
    DEBUG = False
    # Render inyecta DATABASE_URL automáticamente
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL')
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'clave-super-secreta-para-produccion'

class TestingConfig(Config):
    """Configuración de pruebas."""
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'

config = {
    'default': DevelopmentConfig,
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig
}