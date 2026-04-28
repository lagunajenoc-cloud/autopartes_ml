# app/models/producto.py
# ARCHIVO ACTUALIZADO PARA INCLUIR CAMPOS DE IGV

from app import db
from datetime import datetime
from decimal import Decimal

class Producto(db.Model):
    """Modelo para la tabla de productos (autopartes)."""
    __tablename__ = 'productos'
    
    id = db.Column(db.Integer, primary_key=True)
    codigo = db.Column(db.String(50), unique=True)
    categoria = db.Column(db.String(100), nullable=False)
    modelo_carro = db.Column(db.String(100), nullable=False)
    descripcion = db.Column(db.Text)
    precio_unitario = db.Column(db.Numeric(10, 2), nullable=False)
    es_producto_nuevo = db.Column(db.Boolean, default=False)
    fecha_creacion = db.Column(db.DateTime, default=datetime.utcnow)
    
    # NUEVOS CAMPOS PARA IGV
    incluye_igv = db.Column(db.Boolean, default=True)
    precio_sin_igv = db.Column(db.Numeric(10, 2))
    precio_con_igv = db.Column(db.Numeric(10, 2))
    
    # Relaciones
    inventario = db.relationship('Inventario', backref='producto', uselist=False)
    ventas = db.relationship('Venta', backref='producto', lazy='dynamic')
    predicciones = db.relationship('Prediccion', backref='producto', lazy='dynamic')
    
    def __repr__(self):
        return f'<Producto {self.codigo} - {self.categoria} para {self.modelo_carro}>'
    
    # MÉTODOS PARA MANEJAR IGV
    def calcular_precios_igv(self, igv_porcentaje=18):
        """Calcular precios con y sin IGV basado en precio_unitario."""
        if self.incluye_igv:
            # El precio_unitario YA incluye IGV
            self.precio_con_igv = self.precio_unitario
            self.precio_sin_igv = self.precio_unitario / Decimal(1 + igv_porcentaje / 100)
        else:
            # El precio_unitario NO incluye IGV
            self.precio_sin_igv = self.precio_unitario
            self.precio_con_igv = self.precio_unitario * Decimal(1 + igv_porcentaje / 100)
    
    def set_precio_con_igv(self, precio_final, igv_porcentaje=18):
        """Establecer precio cuando conoces el precio final CON IGV."""
        self.precio_con_igv = Decimal(str(precio_final))
        self.precio_sin_igv = self.precio_con_igv / Decimal(1 + igv_porcentaje / 100)
        self.precio_unitario = self.precio_con_igv
        self.incluye_igv = True
    
    def set_precio_sin_igv(self, precio_base, igv_porcentaje=18):
        """Establecer precio cuando conoces el precio base SIN IGV."""
        self.precio_sin_igv = Decimal(str(precio_base))
        self.precio_con_igv = self.precio_sin_igv * Decimal(1 + igv_porcentaje / 100)
        self.precio_unitario = self.precio_sin_igv
        self.incluye_igv = False
    
    def get_precio_venta(self):
        """Obtener el precio que se muestra al cliente (con IGV)."""
        if self.precio_con_igv:
            return self.precio_con_igv
        else:
            # Si no tiene precio_con_igv, asumir que precio_unitario incluye IGV
            return self.precio_unitario
    
    def get_precio_base(self):
        """Obtener el precio base para cálculos (sin IGV)."""
        if self.precio_sin_igv:
            return self.precio_sin_igv
        else:
            # Si no tiene precio_sin_igv, calcularlo
            return self.precio_unitario / Decimal('1.18')
    
    def to_dict(self):
        """Convertir objeto a diccionario para API/JSON."""
        base_dict = {
            'id': self.id,
            'codigo': self.codigo,
            'categoria': self.categoria,
            'modelo_carro': self.modelo_carro,
            'descripcion': self.descripcion,
            'precio_unitario': float(self.precio_unitario),
            'es_producto_nuevo': self.es_producto_nuevo,
            'stock_actual': self.inventario.stock_actual if self.inventario else 0,
            'incluye_igv': self.incluye_igv
        }
        
        # Agregar campos de IGV si existen
        if self.precio_sin_igv:
            base_dict['precio_sin_igv'] = float(self.precio_sin_igv)
        
        if self.precio_con_igv:
            base_dict['precio_con_igv'] = float(self.precio_con_igv)
        
        # Precios calculados
        base_dict['precio_venta'] = float(self.get_precio_venta())
        base_dict['precio_base'] = float(self.get_precio_base())
        
        return base_dict