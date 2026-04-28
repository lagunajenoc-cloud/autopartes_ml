from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for
from flask_login import login_required, current_user
from app import db
from app.models.comprobante import Comprobante, ComprobanteDetalle
from app.models.producto import Producto
from app.models.inventario import Inventario
from app.models.venta import Venta
from datetime import datetime, timedelta
from decimal import Decimal
import json
import traceback

comprobante_bp = Blueprint('comprobantes', __name__, url_prefix='/comprobantes')

@comprobante_bp.route('/')
@login_required
def index():
    """Página principal de comprobantes."""
    try:
        total_proformas = Comprobante.query.filter_by(tipo='proforma').count()
        total_facturas = Comprobante.query.filter_by(tipo='factura').count()
        total_boletas = Comprobante.query.filter_by(tipo='boleta').count()
        
        tipo = request.args.get('tipo', '')
        estado = request.args.get('estado', '')
        fecha_inicio = request.args.get('fecha_inicio', '')
        fecha_fin = request.args.get('fecha_fin', '')
        
        query = Comprobante.query
        
        if tipo:
            query = query.filter(Comprobante.tipo == tipo)
        if estado:
            query = query.filter(Comprobante.estado == estado)
        if fecha_inicio:
            query = query.filter(Comprobante.fecha_emision >= datetime.strptime(fecha_inicio, '%Y-%m-%d'))
        if fecha_fin:
            query = query.filter(Comprobante.fecha_emision <= datetime.strptime(fecha_fin, '%Y-%m-%d'))
        
        comprobantes_recientes = query.order_by(Comprobante.fecha_emision.desc()).limit(10).all()
        
        return render_template('comprobantes/index.html', 
                             comprobantes=comprobantes_recientes,
                             total_proformas=total_proformas,
                             total_facturas=total_facturas,
                             total_boletas=total_boletas,
                             filtros={'tipo': tipo, 'estado': estado, 'fecha_inicio': fecha_inicio, 'fecha_fin': fecha_fin})
        
    except Exception as e:
        print(f"❌ Error en comprobantes: {e}")
        flash(f'Error cargando comprobantes: {str(e)}', 'error')
        return redirect(url_for('dashboard.index'))

@comprobante_bp.route('/listar')
@login_required
def listar():
    return redirect(url_for('comprobantes.index'))

@comprobante_bp.route('/nuevo/<tipo>')
@login_required
def nuevo_comprobante(tipo):
    if tipo not in ['proforma', 'factura', 'boleta']:
        flash('Tipo de comprobante no válido', 'error')
        return redirect(url_for('comprobantes.index'))
    
    try:
        print(f"🚀 Cargando formulario para {tipo}")
        
        productos_query = db.session.query(
            Producto.id,
            Producto.codigo,
            Producto.descripcion,
            Producto.precio_unitario,
            Producto.categoria,
            Producto.modelo_carro,
            Inventario.stock_actual
        ).join(
            Inventario, Producto.id == Inventario.producto_id
        ).filter(
            Inventario.stock_actual > 0
        ).order_by(
            Producto.categoria,
            Producto.codigo
        )
        
        productos_raw = productos_query.all()
        print(f"📦 {len(productos_raw)} productos con stock encontrados")
        
        productos_data = []
        for row in productos_raw:
            try:
                producto_data = {
                    'id': int(row.id),
                    'codigo': str(row.codigo or ''),
                    'descripcion': str(row.descripcion or ''),
                    'precio_unitario': float(row.precio_unitario) if row.precio_unitario else 0.0,
                    'stock_actual': int(row.stock_actual) if row.stock_actual else 0,
                    'categoria': str(row.categoria or 'General'),
                    'modelo_carro': str(row.modelo_carro or 'Universal')
                }
                
                if producto_data['codigo'] and producto_data['precio_unitario'] > 0:
                    productos_data.append(producto_data)
                
            except Exception as e:
                print(f"⚠️ Error procesando producto {getattr(row, 'id', 'unknown')}: {e}")
                continue
        
        print(f"✅ {len(productos_data)} productos preparados para template")
        
        return render_template('comprobantes/formulario.html', 
                             tipo=tipo, 
                             productos=productos_data,
                             comprobante=None)
    
    except Exception as e:
        print(f"❌ ERROR en nuevo_comprobante: {str(e)}")
        traceback.print_exc()
        flash(f'Error cargando productos: {str(e)}', 'error')
        return redirect(url_for('comprobantes.index'))

@comprobante_bp.route('/editar/<int:id>')
@login_required
def editar_comprobante(id):
    """Editar comprobante existente - Sin restricción de tipo"""
    
    comprobante = Comprobante.query.get_or_404(id)
    
    # Solo restringimos comprobantes anulados
    if comprobante.estado == 'anulado':
        flash('No se pueden editar comprobantes anulados', 'error')
        return redirect(url_for('comprobantes.ver_comprobante', id=id))
    
    try:
        productos_query = db.session.query(
            Producto.id,
            Producto.codigo,
            Producto.descripcion,
            Producto.precio_unitario,
            Producto.categoria,
            Producto.modelo_carro,
            Inventario.stock_actual
        ).join(
            Inventario, Producto.id == Inventario.producto_id
        ).filter(
            Inventario.stock_actual > 0
        ).order_by(
            Producto.categoria,
            Producto.codigo
        )
        
        productos_raw = productos_query.all()
        
        productos_data = []
        for row in productos_raw:
            try:
                producto_data = {
                    'id': int(row.id),
                    'codigo': str(row.codigo or ''),
                    'descripcion': str(row.descripcion or ''),
                    'precio_unitario': float(row.precio_unitario) if row.precio_unitario else 0.0,
                    'stock_actual': int(row.stock_actual) if row.stock_actual else 0,
                    'categoria': str(row.categoria or 'General'),
                    'modelo_carro': str(row.modelo_carro or 'Universal')
                }
                
                if producto_data['codigo'] and producto_data['precio_unitario'] > 0:
                    productos_data.append(producto_data)
                    
            except Exception as e:
                print(f"⚠️ Error procesando producto: {e}")
                continue
        
        return render_template('comprobantes/formulario.html', 
                             tipo=comprobante.tipo, 
                             productos=productos_data,
                             comprobante=comprobante)
    
    except Exception as e:
        print(f"❌ ERROR en editar_comprobante: {str(e)}")
        flash(f'Error cargando datos: {str(e)}', 'error')
        return redirect(url_for('comprobantes.ver_comprobante', id=id))

@comprobante_bp.route('/guardar', methods=['POST'])
@login_required
def guardar_comprobante():
    """Guardar comprobante CON SOPORTE PARA PRODUCTOS MANUALES"""
    
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'success': False, 'error': 'No se recibieron datos'})
        
        print(f"📝 Guardando comprobante: {data}")
        
        comprobante_id = data.get('comprobante_id')
        tipo = data.get('tipo')
        cliente_datos = data.get('cliente', {})
        detalles_data = data.get('detalles', [])
        
        if not tipo or tipo not in ['proforma', 'factura', 'boleta']:
            return jsonify({'success': False, 'error': 'Tipo de comprobante no válido'})
        
        if not cliente_datos.get('nombre'):
            return jsonify({'success': False, 'error': 'El nombre del cliente es obligatorio'})
        
        # ✅ CORRECCIÓN AQUÍ: Se completa la línea que estaba rota
        if not detalles_data:
            return jsonify({'success': False, 'error': 'Debe agregar al menos un producto'})
        
        try:
            if comprobante_id:
                comprobante = Comprobante.query.get(comprobante_id)
                if not comprobante:
                    return jsonify({'success': False, 'error': 'Comprobante no encontrado'})
                print(f"📝 Editando comprobante existente: {comprobante.numero}")
            else:
                comprobante = Comprobante()
                comprobante.tipo = tipo
                comprobante.usuario_id = current_user.id
                print(f"📝 Creando nuevo comprobante tipo: {tipo}")
            
            comprobante.cliente_nombre = str(cliente_datos.get('nombre', ''))
            comprobante.cliente_documento = str(cliente_datos.get('documento', ''))
            comprobante.cliente_direccion = str(cliente_datos.get('direccion', ''))
            comprobante.cliente_email = str(cliente_datos.get('email', ''))
            comprobante.cliente_telefono = str(cliente_datos.get('telefono', ''))
            comprobante.observaciones = str(data.get('observaciones', ''))
            comprobante.condiciones_pago = str(data.get('condiciones_pago', 'Contado'))
            
            if not comprobante_id:
                comprobante.generar_numero()
                print(f"📝 Número generado: {comprobante.numero}")
            
            db.session.add(comprobante)
            db.session.flush()
            
            if comprobante_id:
                ComprobanteDetalle.query.filter_by(comprobante_id=comprobante.id).delete()
                print("🗑️ Detalles anteriores eliminados")
            
            productos_inventario = []
            productos_manuales = []
            
            for detalle_data in detalles_data:
                es_manual = detalle_data.get('es_manual', False)
                
                if es_manual:
                    productos_manuales.append(detalle_data)
                    print(f"📝 Producto manual: {detalle_data.get('codigo_manual', 'Sin código')}")
                else:
                    productos_inventario.append(detalle_data)
                    print(f"📦 Producto inventario: ID {detalle_data.get('producto_id')}")
            
            for detalle_data in productos_inventario:
                try:
                    if not detalle_data.get('producto_id'):
                        return jsonify({'success': False, 'error': 'Producto de inventario sin ID válido'})
                    
                    producto_id = int(detalle_data['producto_id'])
                    cantidad_requerida = int(detalle_data['cantidad'])
                    
                    inventario = Inventario.query.filter_by(producto_id=producto_id).first()
                    if not inventario:
                        db.session.rollback()
                        return jsonify({
                            'success': False, 
                            'error': f'Producto ID {producto_id} no tiene inventario registrado'
                        })
                    
                    if inventario.stock_actual < cantidad_requerida:
                        producto = Producto.query.get(producto_id)
                        nombre_producto = producto.codigo if producto else f"ID {producto_id}"
                        db.session.rollback()
                        return jsonify({
                            'success': False,
                            'error': f'Stock insuficiente para {nombre_producto}. Disponible: {inventario.stock_actual}, Requerido: {cantidad_requerida}'
                        })
                        
                except (ValueError, TypeError) as e:
                    db.session.rollback()
                    return jsonify({
                        'success': False,
                        'error': f'Error en datos del producto de inventario: {str(e)}'
                    })
            
            productos_manuales_creados = {}
            
            for detalle_data in productos_manuales:
                try:
                    codigo_manual = str(detalle_data.get('codigo_manual', '')).strip()
                    descripcion_manual = str(detalle_data.get('descripcion_manual', '')).strip()
                    precio_unitario = Decimal(str(detalle_data['precio_unitario']))
                    
                    if not codigo_manual or not descripcion_manual:
                        db.session.rollback()
                        return jsonify({
                            'success': False,
                            'error': 'Productos manuales deben tener código y descripción'
                        })
                    
                    producto_existente = Producto.query.filter_by(codigo=codigo_manual).first()
                    
                    if producto_existente:
                        producto_manual = producto_existente
                        print(f"📦 Usando producto existente: {codigo_manual}")
                    else:
                        producto_manual = Producto(
                            codigo=codigo_manual,
                            categoria='',
                            modelo_carro='',
                            descripcion=descripcion_manual,
                            precio_unitario=precio_unitario,
                            es_producto_nuevo=True
                        )
                        db.session.add(producto_manual)
                        db.session.flush()
                        
                        inventario_manual = Inventario(
                            producto_id=producto_manual.id,
                            stock_actual=9999,
                            stock_minimo=0,
                            stock_optimo=9999
                        )
                        db.session.add(inventario_manual)
                        
                        print(f"✅ Producto manual creado: {codigo_manual}")
                    
                    productos_manuales_creados[codigo_manual] = producto_manual.id
                    
                except Exception as e:
                    db.session.rollback()
                    return jsonify({
                        'success': False,
                        'error': f'Error creando producto manual: {str(e)}'
                    })
            
            total_detalles = 0
            # ✅ CORRECCIÓN AQUÍ: El bucle estaba cortado, ahora está completo
            for detalle_data in detalles_data:
                try:
                    detalle = ComprobanteDetalle()
                    detalle.comprobante_id = comprobante.id
                    detalle.cantidad = int(detalle_data['cantidad'])
                    
                    detalle.precio_unitario = Decimal(str(detalle_data['precio_unitario']))
                    detalle.precio_original = Decimal(str(detalle_data.get('precio_original', detalle.precio_unitario)))
                    detalle.descuento_porcentaje = Decimal(str(detalle_data.get('descuento_porcentaje', 0)))
                    
                    if detalle_data.get('es_manual', False):
                        codigo_manual = detalle_data.get('codigo_manual')
                        if codigo_manual and codigo_manual in productos_manuales_creados:
                            detalle.producto_id = productos_manuales_creados[codigo_manual]
                        else:
                            db.session.rollback()
                            return jsonify({'success': False, 'error': f'Error creando producto manual: {codigo_manual}'})
                    else:
                        if detalle_data.get('producto_id'):
                            detalle.producto_id = int(detalle_data['producto_id'])
                        else:
                            db.session.rollback()
                            return jsonify({'success': False, 'error': 'Producto de inventario sin ID válido'})
                    
                    detalle.calcular_subtotal()
                    
                    db.session.add(detalle)
                    total_detalles += 1
                    
                    print(f"✅ Detalle agregado: Producto {detalle.producto_id}, Cantidad {detalle.cantidad}, Subtotal {detalle.subtotal}")
                    
                except Exception as e:
                    print(f"❌ Error procesando detalle: {e}")
                    db.session.rollback()
                    return jsonify({'success': False, 'error': f'Error en detalle: {str(e)}'})
            
            print(f"📊 {total_detalles} detalles procesados")
            
            comprobante.calcular_totales()
            print(f"💰 Total calculado: {comprobante.total}")
            
            if tipo in ['factura', 'boleta']:
                comprobante.estado = 'aprobado'
                print(f"🎯 Generando ventas para {tipo}")
                comprobante.generar_ventas()
                print("✅ Ventas generadas e inventario actualizado")
            
            db.session.commit()
            print(f"✅ Comprobante guardado exitosamente: {comprobante.numero}")
            
            return jsonify({
                'success': True, 
                'message': f'{tipo.title()} guardada exitosamente',
                'comprobante_id': comprobante.id,
                'numero': comprobante.numero
            })
            
        except Exception as e:
            db.session.rollback()
            print(f"❌ Error en operación: {str(e)}")
            traceback.print_exc()
            return jsonify({'success': False, 'error': f'Error guardando: {str(e)}'})
        
    except Exception as e:
        print(f"❌ ERROR general guardando comprobante: {str(e)}")
        traceback.print_exc()
        return jsonify({'success': False, 'error': f'Error del servidor: {str(e)}'})

@comprobante_bp.route('/ver/<int:id>')
@login_required
def ver_comprobante(id):
    comprobante = Comprobante.query.get_or_404(id)
    return render_template('comprobantes/ver.html', comprobante=comprobante)

@comprobante_bp.route('/convertir/<int:id>', methods=['POST'])
@login_required
def convertir_proforma(id):
    comprobante = Comprobante.query.get_or_404(id)
    tipo_destino = request.form.get('tipo_destino')
    
    if comprobante.tipo != 'proforma':
        flash('Solo las proformas se pueden convertir', 'error')
        return redirect(url_for('comprobantes.ver_comprobante', id=id))
    
    if tipo_destino not in ['factura', 'boleta']:
        flash('Tipo de destino no válido', 'error')
        return redirect(url_for('comprobantes.ver_comprobante', id=id))
    
    try:
        for detalle in comprobante.detalles:
            inventario = Inventario.query.filter_by(producto_id=detalle.producto_id).first()
            
            if inventario and inventario.stock_actual < 9999:
                if inventario.stock_actual < detalle.cantidad:
                    producto = Producto.query.get(detalle.producto_id)
                    nombre = producto.codigo if producto else f"ID {detalle.producto_id}"
                    flash(f'Stock insuficiente para {nombre}. Disponible: {inventario.stock_actual}, Requerido: {detalle.cantidad}', 'error')
                    return redirect(url_for('comprobantes.ver_comprobante', id=id))
        
        nuevo_comprobante = comprobante.convertir_a_factura_boleta(tipo_destino, current_user.id)
        nuevo_comprobante.generar_ventas()
        
        db.session.commit()
        
        flash(f'Proforma convertida exitosamente a {tipo_destino} {nuevo_comprobante.numero}', 'success')
        return redirect(url_for('comprobantes.ver_comprobante', id=nuevo_comprobante.id))
        
    except Exception as e:
        db.session.rollback()
        print(f"❌ Error convirtiendo: {e}")
        flash(f'Error al convertir: {str(e)}', 'error')
        return redirect(url_for('comprobantes.ver_comprobante', id=id))

@comprobante_bp.route('/anular/<int:id>', methods=['POST'])
@login_required
def anular_comprobante(id):
    comprobante = Comprobante.query.get_or_404(id)
    motivo = request.form.get('motivo', '')
    
    if comprobante.estado == 'anulado':
        flash('El comprobante ya está anulado', 'warning')
        return redirect(url_for('comprobantes.ver_comprobante', id=id))
    
    try:
        comprobante.estado = 'anulado'
        comprobante.observaciones = f"ANULADO: {motivo}\n{comprobante.observaciones or ''}"
        
        if comprobante.tipo in ['factura', 'boleta']:
            print(f"🔄 Revirtiendo inventario para {comprobante.numero}")
            
            for detalle in comprobante.detalles:
                inventario = Inventario.query.filter_by(producto_id=detalle.producto_id).first()
                if inventario:
                    if inventario.stock_actual < 9999:
                        inventario.stock_actual += detalle.cantidad
                        inventario.ultima_actualizacion = datetime.utcnow()
                        print(f"📦 Stock revertido: Producto {detalle.producto_id} +{detalle.cantidad}")
                    else:
                        print(f"📦 Producto manual detectado: {detalle.producto_id} - No se revierte stock")
                
                ventas = Venta.query.filter_by(comprobante_id=comprobante.id).all()
                for venta in ventas:
                    db.session.delete(venta)
                    print(f"🗑️ Venta eliminada: {venta.id}")
        
        db.session.commit()
        
        flash('Comprobante anulado exitosamente', 'success')
        return redirect(url_for('comprobantes.ver_comprobante', id=id))
        
    except Exception as e:
        db.session.rollback()
        print(f"❌ Error anulando: {e}")
        flash(f'Error al anular: {str(e)}', 'error')
        return redirect(url_for('comprobantes.ver_comprobante', id=id))

@comprobante_bp.route('/pdf/<int:id>')
@login_required
def generar_pdf(id):
    comprobante = Comprobante.query.get_or_404(id)
    return render_template('comprobantes/pdf.html', comprobante=comprobante)

@comprobante_bp.route('/buscar-producto/<int:producto_id>')
@login_required
def buscar_producto(producto_id):
    try:
        producto = Producto.query.get_or_404(producto_id)
        inventario = Inventario.query.filter_by(producto_id=producto_id).first()
        
        precio_unitario = float(producto.precio_unitario) if producto.precio_unitario else 0.0
        precio_con_igv = precio_unitario * 1.18
        precio_sin_igv = precio_unitario / 1.18
        
        return jsonify({
            'success': True,
            'producto': {
                'id': producto.id,
                'codigo': producto.codigo,
                'descripcion': producto.descripcion,
                'precio_unitario': precio_unitario,
                'precio_con_igv': round(precio_con_igv, 2),
                'precio_sin_igv': round(precio_sin_igv, 2),
                'stock_actual': inventario.stock_actual if inventario else 0,
                'categoria': getattr(producto, 'categoria', 'General'),
                'modelo_carro': getattr(producto, 'modelo_carro', 'Universal')
            }
        })
        
    except Exception as e:
        print(f"❌ Error buscando producto: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        })

@comprobante_bp.route('/api/productos')
@login_required
def api_productos():
    try:
        productos_query = db.session.query(
            Producto.id,
            Producto.codigo,
            Producto.descripcion,
            Producto.precio_unitario,
            Producto.categoria,
            Producto.modelo_carro,
            Inventario.stock_actual
        ).join(
            Inventario, Producto.id == Inventario.producto_id
        ).filter(
            Inventario.stock_actual > 0
        ).order_by(
            Producto.categoria,
            Producto.codigo
        )
        
        productos_raw = productos_query.all()
        
        productos_data = []
        for row in productos_raw:
            try:
                producto_data = {
                    'id': int(row.id),
                    'codigo': str(row.codigo or ''),
                    'descripcion': str(row.descripcion or ''),
                    'precio_unitario': float(row.precio_unitario) if row.precio_unitario else 0.0,
                    'stock_actual': int(row.stock_actual) if row.stock_actual else 0,
                    'categoria': str(row.categoria or 'General'),
                    'modelo_carro': str(row.modelo_carro or 'Universal')
                }
                
                if producto_data['codigo'] and producto_data['precio_unitario'] > 0:
                    productos_data.append(producto_data)
                    
            except Exception as e:
                print(f"⚠️ Error procesando producto API: {e}")
                continue
        
        return jsonify({
            'success': True,
            'productos': productos_data,
            'total': len(productos_data)
        })
        
    except Exception as e:
        print(f"❌ ERROR en API productos: {str(e)}")
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e),
            'productos': []
        })

@comprobante_bp.route('/api/dashboard')
@login_required
def dashboard_data():
    try:
        today = datetime.now().date()
        month_start = today.replace(day=1)
        
        stats = {
            'proformas_pendientes': Comprobante.query.filter_by(tipo='proforma', estado='pendiente').count(),
            'facturas_mes': Comprobante.query.filter(
                Comprobante.tipo == 'factura',
                Comprobante.fecha_emision >= month_start
            ).count(),
            'total_mes': 0
        }
        
        total_query = db.session.query(db.func.sum(Comprobante.total)).filter(
            Comprobante.tipo.in_(['factura', 'boleta']),
            Comprobante.fecha_emision >= month_start,
            Comprobante.estado != 'anulado'
        ).scalar()
        
        stats['total_mes'] = float(total_query) if total_query else 0
        
        return jsonify(stats)
        
    except Exception as e:
        print(f"❌ Error en dashboard: {e}")
        return jsonify({
            'error': str(e),
            'proformas_pendientes': 0,
            'facturas_mes': 0,
            'total_mes': 0
        })