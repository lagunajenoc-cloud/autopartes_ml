from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from flask_wtf import FlaskForm
from wtforms import StringField, IntegerField, DecimalField, SelectField, DateField, SubmitField
from wtforms.validators import DataRequired, Optional, NumberRange, Length
from datetime import datetime, timedelta
import csv
from io import TextIOWrapper
import os

from app import db
from app.models.producto import Producto
from app.models.venta import Venta
from app.models.inventario import Inventario
from app.utils.auth_utils import admin_required, vendedor_required

# Definir formulario para nueva venta
class VentaForm(FlaskForm):
    producto_id = SelectField('Producto', validators=[DataRequired()], coerce=int)
    cantidad = IntegerField('Cantidad', validators=[DataRequired(), NumberRange(min=1)], default=1)
    precio_unitario = DecimalField('Precio Unitario', validators=[DataRequired(), NumberRange(min=0)])
    submit = SubmitField('Registrar Venta')

# Crear blueprint de ventas
ventas_bp = Blueprint('ventas', __name__, url_prefix='/ventas')

@ventas_bp.route('/')
@login_required
@vendedor_required
def index():
    try:
        form = VentaForm()
        
        # Cargar opciones de productos para el formulario
        try:
            productos = db.session.query(Producto).all()
            opciones_productos = []
            for p in productos:
                codigo = getattr(p, 'codigo', 'Sin código')
                modelo = getattr(p, 'modelo_carro', '')
                categoria = getattr(p, 'categoria', '')
                
                etiqueta = f"{codigo}"
                if modelo: etiqueta += f" - {modelo}"
                if categoria: etiqueta += f" ({categoria})"
                
                opciones_productos.append((p.id, etiqueta))
            
            form.producto_id.choices = opciones_productos
        except Exception as e:
            form.producto_id.choices = []
            print(f"Error al cargar productos: {str(e)}")
        
        # Obtener parámetros de filtro
        categoria = request.args.get('categoria', '')
        modelo = request.args.get('modelo', '')
        
        # ✅ CORRECCIÓN: Ya no ponemos fechas por defecto de hace 30 días.
        # Esto permite ver TODO el historial si el usuario no filtra.
        fecha_inicio_str = request.args.get('fecha_inicio', '')
        fecha_fin_str = request.args.get('fecha_fin', '')
        
        # Consulta base de ventas
        query = db.session.query(
            Venta, Producto
        ).join(
            Producto, Venta.producto_id == Producto.id
        )
        
        # ✅ Solo aplicamos filtro de fecha SI el usuario seleccionó una fecha
        if fecha_inicio_str and fecha_fin_str:
            try:
                fecha_inicio = datetime.strptime(fecha_inicio_str, '%Y-%m-%d')
                fecha_fin = datetime.strptime(fecha_fin_str, '%Y-%m-%d')
                # Ajustar fecha_fin para incluir todo el día
                fecha_fin = fecha_fin.replace(hour=23, minute=59, second=59)
                query = query.filter(Venta.fecha_venta.between(fecha_inicio, fecha_fin))
            except ValueError:
                pass # Si hay error de formato, no filtrar por fecha
        
        # Aplicar filtros adicionales
        if hasattr(Producto, 'categoria') and categoria:
            query = query.filter(Producto.categoria == categoria)
        if hasattr(Producto, 'modelo_carro') and modelo:
            query = query.filter(Producto.modelo_carro.ilike(f'%{modelo}%'))
        
        # Obtener ventas
        ventas = query.order_by(Venta.fecha_venta.desc()).all()
        
        # Calcular totales
        total_ventas = sum(float(venta.total) for venta, _ in ventas)
        total_productos = sum(venta.cantidad for venta, _ in ventas)
        total_transacciones = len(ventas)
        
        # Obtener categorías y modelos para filtros
        categorias = []
        modelos = []
        
        if hasattr(Producto, 'categoria'):
            categorias = db.session.query(Producto.categoria).distinct().all()
        
        if hasattr(Producto, 'modelo_carro'):
            modelos = db.session.query(Producto.modelo_carro).distinct().all()
        
        return render_template(
            'ventas/index.html',
            ventas=ventas,
            total_ventas=total_ventas,
            total_productos=total_productos,
            total_transacciones=total_transacciones,
            categorias=[cat[0] for cat in categorias] if categorias else [],
            modelos=[m[0] for m in modelos] if modelos else [],
            categoria_actual=categoria,
            modelo_actual=modelo,
            fecha_inicio=fecha_inicio_str,
            fecha_fin=fecha_fin_str,
            title='Gestión de Ventas',
            form=form
        )
        
    except Exception as e:
        flash(f'Error al cargar las ventas: {str(e)}', 'danger')
        
        form = VentaForm()
        form.producto_id.choices = []
            
        return render_template(
            'ventas/index.html',
            ventas=[],
            total_ventas=0,
            total_productos=0,
            total_transacciones=0,
            categorias=[],
            modelos=[],
            categoria_actual='',
            modelo_actual='',
            fecha_inicio='',
            fecha_fin='',
            title='Gestión de Ventas',
            error=str(e),
            form=form
        )

@ventas_bp.route('/nueva', methods=['GET', 'POST'])
@login_required
@vendedor_required
def nueva_venta():
    form = VentaForm()
    productos = db.session.query(Producto).all()
    form.producto_id.choices = [(p.id, f'{p.codigo} - {p.modelo_carro} ({p.categoria})') for p in productos]
    
    if form.validate_on_submit():
        try:
            producto = db.session.query(Producto).get(form.producto_id.data)
            if not producto:
                flash('Producto no encontrado', 'danger')
                return redirect(url_for('ventas.nueva_venta'))
            
            inventario = Inventario.query.filter_by(producto_id=producto.id).first()
            
            # ✅ CORRECCIÓN AQUÍ: Se agregó '.data:' que faltaba
            if inventario and inventario.stock_actual < form.cantidad.data:
                flash(f'No hay suficiente stock disponible. Stock actual: {inventario.stock_actual}', 'warning')
                return redirect(url_for('ventas.nueva_venta'))
            
            nueva_venta = Venta(
                fecha_venta=datetime.now(),
                producto_id=producto.id,
                cantidad=form.cantidad.data,
                precio_unitario=form.precio_unitario.data,
                precio_total=form.cantidad.data * form.precio_unitario.data,
                usuario_id=current_user.id
            )
            
            db.session.add(nueva_venta)
            
            if inventario:
                inventario.stock_actual -= form.cantidad.data
            
            db.session.commit()
            
            flash('Venta registrada correctamente', 'success')
            return redirect(url_for('ventas.index'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error al registrar la venta: {str(e)}', 'danger')
    
    return render_template(
        'ventas/nueva_venta.html',
        form=form,
        title='Registrar Nueva Venta'
    )

@ventas_bp.route('/registrar', methods=['GET', 'POST'])
@login_required
@vendedor_required
def registrar():
    return nueva_venta()

@ventas_bp.route('/<int:venta_id>/detalle')
@login_required
@vendedor_required
def detalle_venta(venta_id):
    try:
        venta, producto = db.session.query(Venta, Producto).join(
            Producto, Venta.producto_id == Producto.id
        ).filter(Venta.id == venta_id).first_or_404()
        
        return render_template(
            'ventas/detalle_venta.html',
            venta=venta,
            producto=producto,
            title='Detalle de Venta'
        )
    except Exception as e:
        flash(f'Error al cargar el detalle de la venta: {str(e)}', 'danger')
        return redirect(url_for('ventas.index'))

@ventas_bp.route('/<int:venta_id>/eliminar', methods=['POST'])
@login_required
@admin_required
def eliminar_venta(venta_id):
    try:
        venta = db.session.query(Venta).get_or_404(venta_id)
        
        inventario = Inventario.query.filter_by(producto_id=venta.producto_id).first()
        if inventario:
            inventario.stock_actual += venta.cantidad
        
        db.session.delete(venta)
        db.session.commit()
        
        flash('Venta eliminada correctamente', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error al eliminar la venta: {str(e)}', 'danger')
    
    return redirect(url_for('ventas.index'))

@ventas_bp.route('/bulk-import', methods=['GET', 'POST'])
@login_required
@admin_required
def importar_ventas():
    class ImportForm(FlaskForm):
        pass
    
    form = ImportForm()
    
    if request.method == 'POST':
        try:
            if 'archivo_csv' not in request.files:
                flash('No se seleccionó ningún archivo', 'danger')
                return redirect(request.url)
                
            archivo = request.files['archivo_csv']
            
            if archivo.filename == '':
                flash('No se seleccionó ningún archivo', 'danger')
                return redirect(request.url)
                
            if not archivo.filename.endswith('.csv'):
                flash('El archivo debe tener extensión .csv', 'danger')
                return redirect(request.url)
            
            ignorar_encabezados = 'ignorar_encabezados' in request.form
            
            filas_procesadas = 0
            ventas_creadas = 0
            errores = 0
            
            codificaciones = ['utf-8', 'latin-1', 'ISO-8859-1', 'windows-1252']
            contenido = archivo.read()
            procesado = False
            
            for codificacion in codificaciones:
                try:
                    archivo.seek(0)
                    csv_data = contenido.decode(codificacion)
                    
                    import io
                    
                    csv_io = io.StringIO(csv_data)
                    csv_reader = csv.reader(csv_io, delimiter=',')
                    
                    if ignorar_encabezados:
                        next(csv_reader, None)
                    
                    for row in csv_reader:
                        try:
                            if len(row) < 5:
                                errores += 1
                                continue
                            
                            fecha_str, codigo_producto, categoria, cantidad_str, precio_str = row[0], row[1], row[2], row[3], row[4]
                            
                            fecha = None
                            formatos_fecha = ['%d/%m/%Y', '%Y-%m-%d', '%d-%m-%Y']
                            for formato in formatos_fecha:
                                try:
                                    fecha = datetime.strptime(fecha_str, formato)
                                    break
                                except ValueError:
                                    continue
                            
                            if fecha is None:
                                errores += 1
                                continue
                            
                            try:
                                cantidad = int(cantidad_str)
                                precio_unitario = float(precio_str.replace(',', '.'))
                            except ValueError:
                                errores += 1
                                continue
                            
                            codigo_solo = codigo_producto.split(' - ')[0] if ' - ' in codigo_producto else codigo_producto
                            producto = db.session.query(Producto).filter_by(codigo=codigo_solo).first()
                            if not producto:
                                errores += 1
                                continue
                            
                            nueva_venta = Venta(
                                fecha_venta=fecha,
                                producto_id=producto.id,
                                cantidad=cantidad,
                                precio_unitario=precio_unitario,
                                precio_total=cantidad * precio_unitario,
                                usuario_id=current_user.id
                            )
                            
                            db.session.add(nueva_venta)
                            ventas_creadas += 1
                            filas_procesadas += 1
                            
                            try:
                                inventario = Inventario.query.filter_by(producto_id=producto.id).first()
                                if inventario:
                                    inventario.stock_actual -= cantidad
                            except Exception as e:
                                print(f"Error al actualizar inventario: {str(e)}")
                            
                        except Exception as e:
                            errores += 1
                            print(f"Error procesando fila: {str(e)}")
                            continue
                    
                    procesado = True
                    break
                
                except UnicodeDecodeError:
                    continue
            
            if not procesado:
                flash('No se pudo decodificar el archivo CSV. Intente guardarlo como UTF-8.', 'danger')
                return redirect(request.url)
            
            db.session.commit()
            
            flash(f'Importación completada: {filas_procesadas} filas procesadas, {ventas_creadas} ventas creadas, {errores} errores.', 'success')
            return redirect(url_for('ventas.index'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error al importar ventas: {str(e)}', 'danger')
            return redirect(request.url)
    
    return render_template('ventas/importar.html', 
                          title='Importar Ventas Históricas',
                          form=form)

@ventas_bp.route('/reporte')
@login_required
@vendedor_required
def reporte_ventas():
    try:
        periodo = request.args.get('periodo', 'mensual')
        categoria = request.args.get('categoria', '')
        año = request.args.get('año', str(datetime.now().year))
        
        datos_ventas = []
        etiquetas = []
        
        if periodo == 'mensual':
            etiquetas = ['Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun', 'Jul', 'Ago', 'Sep', 'Oct', 'Nov', 'Dic']
            
            for mes in range(1, 13):
                fecha_inicio = datetime(int(año), mes, 1)
                if mes == 12:
                    fecha_fin = datetime(int(año) + 1, 1, 1) - timedelta(days=1)
                else:
                    fecha_fin = datetime(int(año), mes + 1, 1) - timedelta(days=1)
                
                query = db.session.query(
                    db.func.sum(Venta.precio_total)
                ).join(
                    Producto, Venta.producto_id == Producto.id
                ).filter(
                    Venta.fecha_venta.between(fecha_inicio, fecha_fin)
                )
                
                if categoria:
                    query = query.filter(Producto.categoria == categoria)
                
                total_mes = query.scalar() or 0
                datos_ventas.append(float(total_mes))
        
        elif periodo == 'diario':
            for dia in range(30, 0, -1):
                fecha = datetime.now() - timedelta(days=dia)
                etiquetas.append(fecha.strftime('%d/%m'))
                
                query = db.session.query(
                    db.func.sum(Venta.precio_total)
                ).join(
                    Producto, Venta.producto_id == Producto.id
                ).filter(
                    db.func.date(Venta.fecha_venta) == fecha.date()
                )
                
                if categoria:
                    query = query.filter(Producto.categoria == categoria)
                
                total_dia = query.scalar() or 0
                datos_ventas.append(float(total_dia))
        
        categorias = db.session.query(Producto.categoria).distinct().all()
        
        años = db.session.query(
            db.func.extract('year', Venta.fecha_venta).distinct()
        ).order_by(
            db.func.extract('year', Venta.fecha_venta).desc()
        ).all()
        
        return render_template(
            'ventas/reporte.html',
            datos_ventas=datos_ventas,
            etiquetas=etiquetas,
            categorias=[cat[0] for cat in categorias],
            años=[int(a[0]) for a in años],
            categoria_actual=categoria,
            periodo_actual=periodo,
            año_actual=int(año),
            title='Reporte de Ventas'
        )
    except Exception as e:
        flash(f'Error al generar el reporte: {str(e)}', 'danger')
        return redirect(url_for('ventas.index'))

@ventas_bp.route('/api/productos/<int:producto_id>')
@login_required
def api_producto_info(producto_id):
    try:
        producto = db.session.query(Producto).get_or_404(producto_id)
        inventario = Inventario.query.filter_by(producto_id=producto_id).first()
        
        return jsonify({
            'id': producto.id,
            'codigo': producto.codigo,
            'modelo': producto.modelo_carro,
            'categoria': producto.categoria,
            'precio': float(producto.precio_unitario),
            'stock_actual': inventario.stock_actual if inventario else 0
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500