# app/controllers/__init__.py

from .auth_controller import auth_bp
from .ventas_controller import ventas_bp
from .inventario_controller import inventario_bp
from .dashboard_controller import dashboard_bp
from .ml_controller import ml_bp
from .comprobante_controller import comprobante_bp  # NUEVO

__all__ = ['auth_bp', 'ventas_bp', 'inventario_bp', 'dashboard_bp', 'ml_bp', 'comprobante_bp']  # AGREGADO comprobante_bp