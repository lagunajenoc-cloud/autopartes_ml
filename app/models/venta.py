# app/models/venta.py

from app import db
from datetime import datetime

class Venta(db.Model):
    """Modelo para la tabla de registro de ventas."""
    __tablename__ = 'ventas'
    
    id = db.Column(db.Integer, primary_key=True)
    producto_id = db.Column(db.Integer, db.ForeignKey('productos.id'), nullable=False)
    cantidad = db.Column(db.Integer, nullable=False)
    precio_unitario = db.Column(db.Numeric(10, 2), nullable=False)
    precio_total = db.Column(db.Numeric(10, 2), nullable=False)
    fecha_venta = db.Column(db.DateTime, default=datetime.utcnow)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=False)
    
    # CAMPO AGREGADO para trazabilidad
    comprobante_id = db.Column(db.Integer, db.ForeignKey('comprobantes.id'))
    
    # ✅ SOLUCIÓN: Se elimina la relación 'comprobante' para evitar el error de carga circular.
    # SQLAlchemy no puede resolver 'Comprobante' al iniciar. 
    # Si necesitas el comprobante desde una venta, usa: Comprobante.query.get(venta.comprobante_id)

    @property
    def fecha(self):
        """Alias para fecha_venta."""
        return self.fecha_venta
    
    @property
    def total(self):
        """Calcula el total de la venta."""
        return self.precio_total if self.precio_total else (self.cantidad * self.precio_unitario)
    
    def __repr__(self):
        return f'<Venta {self.id} - Producto: {self.producto_id}>'
    
    def to_dict(self):
        """Convertir objeto a diccionario."""
        return {
            'id': self.id,
            'producto_id': self.producto_id,
            'cantidad': self.cantidad,
            'precio_unitario': float(self.precio_unitario) if self.precio_unitario else 0.0,
            'precio_total': float(self.precio_total) if self.precio_total else 0.0,
            'fecha_venta': self.fecha_venta.isoformat() if self.fecha_venta else None,
            'usuario_id': self.usuario_id,
            'comprobante_id': self.comprobante_id
        }