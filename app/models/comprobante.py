# app/models/comprobante.py
# VERSIÓN CORREGIDA - SOLUCIONA ERROR DECIMAL/FLOAT Y MEJORA INTEGRACIÓN

from app import db
from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Text, Boolean, Numeric
from sqlalchemy.orm import relationship
from decimal import Decimal

class Comprobante(db.Model):
    """Modelo para comprobantes (proformas, facturas, boletas)"""
    __tablename__ = 'comprobantes'
    
    id = db.Column(db.Integer, primary_key=True)
    tipo = db.Column(db.String(20), nullable=False)  # proforma, factura, boleta
    numero = db.Column(db.String(50), unique=True, nullable=False)
    serie = db.Column(db.String(10), default='001')
    
    # Datos del cliente
    cliente_nombre = db.Column(db.String(200), nullable=False)
    cliente_documento = db.Column(db.String(20))
    cliente_direccion = db.Column(db.Text)
    cliente_email = db.Column(db.String(100))
    cliente_telefono = db.Column(db.String(20))
    
    # Fechas
    fecha_emision = db.Column(db.DateTime, default=datetime.utcnow)
    fecha_vencimiento = db.Column(db.DateTime)
    
    # ✅ CORREGIDO: Totales - Usar Decimal para todos los cálculos
    subtotal = db.Column(db.Numeric(10, 2), default=Decimal('0.00'))
    igv_porcentaje = db.Column(db.Numeric(5, 2), default=Decimal('18.00'))
    igv_monto = db.Column(db.Numeric(10, 2), default=Decimal('0.00'))
    total = db.Column(db.Numeric(10, 2), default=Decimal('0.00'))
    
    # Estado y seguimiento
    estado = db.Column(db.String(20), default='pendiente')  # pendiente, aprobado, facturado, anulado
    proforma_origen_id = db.Column(db.Integer, db.ForeignKey('comprobantes.id'))
    comprobante_destino_id = db.Column(db.Integer, db.ForeignKey('comprobantes.id'))
    
    # Usuario que crea el comprobante
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=False)
    
    # Observaciones
    observaciones = db.Column(db.Text)
    condiciones_pago = db.Column(db.Text, default='Contado')
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relaciones
    detalles = db.relationship('ComprobanteDetalle', backref='comprobante', lazy='dynamic', cascade='all, delete-orphan')
    usuario = db.relationship('Usuario', backref='comprobantes')
    
    def generar_numero(self):
        """Genera el número del comprobante según el tipo"""
        try:
            # Obtener el último número del mismo tipo usando consulta SQL raw para evitar problemas
            ultimo_query = db.session.execute(
                db.text("SELECT numero FROM comprobantes WHERE tipo = :tipo ORDER BY id DESC LIMIT 1"),
                {'tipo': self.tipo}
            ).fetchone()
            
            if ultimo_query and ultimo_query[0]:
                # Extraer el número y sumar 1
                numero_str = ultimo_query[0]
                partes = numero_str.split('-')
                if len(partes) >= 3:
                    try:
                        numero = int(partes[-1]) + 1
                    except ValueError:
                        numero = 1
                else:
                    numero = 1
            else:
                numero = 1
            
            # Formatear según el tipo
            prefijos = {
                'proforma': 'PRF',
                'factura': 'FAC',
                'boleta': 'BOL'
            }
            
            prefijo = prefijos.get(self.tipo, 'DOC')
            self.numero = f"{self.serie}-{prefijo}-{numero:08d}"
            
            return self.numero
            
        except Exception as e:
            print(f"❌ Error generando número: {e}")
            # Fallback: usar timestamp
            import time
            timestamp = int(time.time() * 1000) % 100000000  # Últimos 8 dígitos
            prefijo = {'proforma': 'PRF', 'factura': 'FAC', 'boleta': 'BOL'}.get(self.tipo, 'DOC')
            self.numero = f"{self.serie}-{prefijo}-{timestamp:08d}"
            return self.numero
    
    def calcular_totales(self):
        """✅ CORREGIDO: Calcula los totales usando Decimal para evitar errores de tipo"""
        try:
            # Inicializar con Decimal
            self.subtotal = Decimal('0.00')
            
            # Sumar todos los subtotales de los detalles
            for detalle in self.detalles:
                if detalle.subtotal:
                    # Asegurar que sea Decimal
                    detalle_subtotal = Decimal(str(detalle.subtotal)) if not isinstance(detalle.subtotal, Decimal) else detalle.subtotal
                    self.subtotal += detalle_subtotal
            
            # Calcular IGV (asegurar que sea Decimal)
            igv_porcentaje = Decimal(str(self.igv_porcentaje)) if not isinstance(self.igv_porcentaje, Decimal) else self.igv_porcentaje
            self.igv_monto = self.subtotal * (igv_porcentaje / Decimal('100'))
            
            # Calcular total
            self.total = self.subtotal + self.igv_monto
            
            print(f"✅ Totales calculados: Subtotal={self.subtotal}, IGV={self.igv_monto}, Total={self.total}")
            return self.total
            
        except Exception as e:
            print(f"❌ Error calculando totales: {e}")
            # Valores por defecto seguros
            self.subtotal = Decimal('0.00')
            self.igv_monto = Decimal('0.00')
            self.total = Decimal('0.00')
            return self.total
    
    def generar_ventas(self):
        """✅ CORREGIDO: Genera las ventas asociadas al comprobante con validaciones"""
        if self.tipo not in ['factura', 'boleta']:
            print(f"ℹ️ Comprobante tipo '{self.tipo}' no genera ventas automáticas")
            return
        
        from app.models.venta import Venta
        from app.models.inventario import Inventario
        
        try:
            print(f"🔄 Generando ventas para {self.tipo} {self.numero}")
            ventas_creadas = 0
            
            for detalle in self.detalles:
                # Validar stock antes de crear venta
                inventario = Inventario.query.filter_by(producto_id=detalle.producto_id).first()
                
                if not inventario:
                    print(f"⚠️ Producto {detalle.producto_id} sin inventario - creando registro")
                    inventario = Inventario(
                        producto_id=detalle.producto_id,
                        stock_actual=0,
                        stock_minimo=10,
                        stock_optimo=120
                    )
                    db.session.add(inventario)
                    db.session.flush()
                
                # Verificar stock suficiente
                if inventario.stock_actual < detalle.cantidad:
                    print(f"⚠️ Stock insuficiente para producto {detalle.producto_id}: Disponible={inventario.stock_actual}, Requerido={detalle.cantidad}")
                    # Continuar pero registrar la situación
                
                # Crear venta con valores Decimal
                venta = Venta(
                    fecha_venta=self.fecha_emision,
                    producto_id=detalle.producto_id,
                    cantidad=detalle.cantidad,
                    precio_unitario=Decimal(str(detalle.precio_unitario)),
                    precio_total=Decimal(str(detalle.subtotal)),
                    usuario_id=self.usuario_id,
                    comprobante_id=self.id
                )
                db.session.add(venta)
                
                # Actualizar inventario
                inventario.stock_actual = max(0, inventario.stock_actual - detalle.cantidad)
                inventario.ultima_actualizacion = datetime.utcnow()
                
                ventas_creadas += 1
                print(f"✅ Venta creada: Producto {detalle.producto_id}, Cantidad {detalle.cantidad}")
            
            print(f"✅ {ventas_creadas} ventas generadas exitosamente")
            
        except Exception as e:
            print(f"❌ Error generando ventas: {e}")
            db.session.rollback()
            raise e
    
    def convertir_a_factura_boleta(self, tipo_destino, usuario_id):
        """✅ CORREGIDO: Convierte una proforma a factura o boleta con manejo mejorado"""
        if self.tipo != 'proforma':
            raise ValueError("Solo las proformas pueden ser convertidas")
        
        if tipo_destino not in ['factura', 'boleta']:
            raise ValueError("Tipo destino debe ser 'factura' o 'boleta'")
        
        try:
            # Crear nuevo comprobante
            nuevo = Comprobante()
            nuevo.tipo = tipo_destino
            nuevo.usuario_id = usuario_id
            nuevo.cliente_nombre = self.cliente_nombre
            nuevo.cliente_documento = self.cliente_documento
            nuevo.cliente_direccion = self.cliente_direccion
            nuevo.cliente_email = self.cliente_email
            nuevo.cliente_telefono = self.cliente_telefono
            nuevo.observaciones = f"Generado desde {self.numero}\n{self.observaciones or ''}"
            nuevo.condiciones_pago = self.condiciones_pago
            nuevo.proforma_origen_id = self.id
            nuevo.igv_porcentaje = self.igv_porcentaje
            
            # Generar número
            nuevo.generar_numero()
            
            db.session.add(nuevo)
            db.session.flush()  # Para obtener el ID
            
            # Actualizar referencia en proforma original
            self.comprobante_destino_id = nuevo.id
            
            # Copiar detalles
            for detalle_original in self.detalles:
                detalle_nuevo = ComprobanteDetalle()
                detalle_nuevo.comprobante_id = nuevo.id
                detalle_nuevo.producto_id = detalle_original.producto_id
                detalle_nuevo.cantidad = detalle_original.cantidad
                detalle_nuevo.precio_unitario = Decimal(str(detalle_original.precio_unitario))
                detalle_nuevo.precio_original = Decimal(str(detalle_original.precio_original)) if detalle_original.precio_original else detalle_nuevo.precio_unitario
                detalle_nuevo.descuento_porcentaje = Decimal(str(detalle_original.descuento_porcentaje or 0))
                detalle_nuevo.calcular_subtotal()
                
                db.session.add(detalle_nuevo)
            
            # Calcular totales
            nuevo.calcular_totales()
            
            # Marcar proforma como convertida
            self.estado = 'facturado'
            self.observaciones = f"Convertido a {tipo_destino} {nuevo.numero}\n{self.observaciones or ''}"
            
            return nuevo
            
        except Exception as e:
            print(f"❌ Error convirtiendo comprobante: {e}")
            raise e
    
    def to_dict(self):
        """Convertir a diccionario para API/JSON"""
        return {
            'id': self.id,
            'tipo': self.tipo,
            'numero': self.numero,
            'serie': self.serie,
            'cliente_nombre': self.cliente_nombre,
            'cliente_documento': self.cliente_documento,
            'fecha_emision': self.fecha_emision.isoformat() if self.fecha_emision else None,
            'subtotal': float(self.subtotal) if self.subtotal else 0,
            'igv_monto': float(self.igv_monto) if self.igv_monto else 0,
            'total': float(self.total) if self.total else 0,
            'estado': self.estado,
            'observaciones': self.observaciones
        }
    
    def __repr__(self):
        return f'<Comprobante {self.numero}>'


class ComprobanteDetalle(db.Model):
    """✅ CORREGIDO: Modelo para los detalles de comprobantes con manejo Decimal"""
    __tablename__ = 'comprobante_detalles'
    
    id = db.Column(db.Integer, primary_key=True)
    comprobante_id = db.Column(db.Integer, db.ForeignKey('comprobantes.id'), nullable=False)
    producto_id = db.Column(db.Integer, db.ForeignKey('productos.id'), nullable=False)
    cantidad = db.Column(db.Integer, nullable=False)
    precio_unitario = db.Column(db.Numeric(10, 2), nullable=False)
    precio_original = db.Column(db.Numeric(10, 2))
    descuento_porcentaje = db.Column(db.Numeric(5, 2), default=Decimal('0.00'))
    subtotal = db.Column(db.Numeric(10, 2), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relaciones
    producto = db.relationship('Producto', backref='comprobante_detalles')
    
    def calcular_subtotal(self):
        """✅ CORREGIDO: Calcula el subtotal usando Decimal"""
        try:
            # Asegurar que todos los valores sean Decimal
            precio_unitario = Decimal(str(self.precio_unitario)) if not isinstance(self.precio_unitario, Decimal) else self.precio_unitario
            descuento_porcentaje = Decimal(str(self.descuento_porcentaje or 0)) if not isinstance(self.descuento_porcentaje, Decimal) else (self.descuento_porcentaje or Decimal('0'))
            cantidad = Decimal(str(self.cantidad))
            
            # Calcular descuento
            if descuento_porcentaje > 0:
                descuento = precio_unitario * (descuento_porcentaje / Decimal('100'))
                precio_con_descuento = precio_unitario - descuento
            else:
                precio_con_descuento = precio_unitario
            
            # Calcular subtotal
            self.subtotal = cantidad * precio_con_descuento
            
            print(f"✅ Subtotal calculado: {cantidad} x {precio_con_descuento} = {self.subtotal}")
            return self.subtotal
            
        except Exception as e:
            print(f"❌ Error calculando subtotal: {e}")
            # Fallback seguro
            self.subtotal = Decimal('0.00')
            return self.subtotal
    
    def to_dict(self):
        """Convertir a diccionario para API/JSON"""
        return {
            'id': self.id,
            'producto_id': self.producto_id,
            'cantidad': self.cantidad,
            'precio_unitario': float(self.precio_unitario) if self.precio_unitario else 0,
            'descuento_porcentaje': float(self.descuento_porcentaje) if self.descuento_porcentaje else 0,
            'subtotal': float(self.subtotal) if self.subtotal else 0
        }
    
    def __repr__(self):
        return f'<ComprobanteDetalle {self.id} - Producto: {self.producto_id}>'