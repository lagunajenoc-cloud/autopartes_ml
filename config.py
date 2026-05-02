import os

class Config:
    """Configuración base."""
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'tu_clave_secreta_super_segura_cambiar_en_produccion'
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # ✅ SOLUCIÓN GLOBAL (AFECTA TODOS LOS ENTORNOS)
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_pre_ping": True,   # 🔥 evita errores SSL
        "pool_recycle": 300      # 🔥 reinicia conexiones cada 5 min
    }


class DevelopmentConfig(Config):
    """Configuración de desarrollo."""
    DEBUG = True
    
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
        'postgresql://postgres:12345678@localhost/autopartes_ML'


class ProductionConfig(Config):
    """Configuración de producción."""
    DEBUG = False

    # ⚠️ IMPORTANTE: Render usa DATABASE_URL
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL')

    SECRET_KEY = os.environ.get('SECRET_KEY') or 'clave-super-secreta-para-produccion'


class TestingConfig(Config):
    """Configuración de pruebas."""
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    WTF_CSRF_ENABLED = False