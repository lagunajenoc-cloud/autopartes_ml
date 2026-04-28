import os

class Config:
    """Configuración base."""
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'tu_clave_secreta_super_segura_cambiar_en_produccion'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    

class DevelopmentConfig(Config):
    """Configuración de desarrollo."""
    DEBUG = True
    # PostgreSQL - Cambia las credenciales por las tuyas
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or 'postgresql://postgres:12345678@localhost/autopartes_ML'
    # Alternativa con SQLite si no tienes PostgreSQL configurado:
    # SQLALCHEMY_DATABASE_URI = 'sqlite:///app.db'
    

class ProductionConfig(Config):
    """Configuración de producción."""
    DEBUG = False
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or 'postgresql://usuario:contraseña@localhost/autopartes_ml_prod'
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'clave-super-secreta-para-produccion'
    

class TestingConfig(Config):
    """Configuración de pruebas."""
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    WTF_CSRF_ENABLED = False