from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from flask_wtf import FlaskForm
from wtforms import StringField, IntegerField, DecimalField, TextAreaField, BooleanField, SubmitField
from wtforms.validators import DataRequired, Optional, NumberRange, Length

from app import db
from app.models.producto import Producto
from app.models.inventario import Inventario
from app.utils.auth_utils import admin_required, vendedor_required

inventario_bp = Blueprint('inventario', __name__, url_prefix='/inventario')

# ✅ AGREGAR FUNCIÓN hasattr AL CONTEXTO DE JINJA2
@inventario_bp.app_context_processor
def utility_processor():
    """Agregar funciones útiles al contexto de Jinja2"""
    return dict(
        hasattr=hasattr,
        getattr=getattr,
        isinstance=isinstance,
        len=len,
        str=str,
        int=int,
        float=float
    )

# Formularios
class ProductoForm(FlaskForm):
    codigo = StringField('Código', validators=[DataRequired(), Length(max=50)])
    categoria = StringField('Categoría', validators=[DataRequired(), Length(max=100)])
    modelo_carro = StringField('Modelo de Carro', validators=[DataRequired(), Length(max=100)])
    descripcion = TextAreaField('Descripción')
    precio_unitario = DecimalField('Precio Unitario', validators=[DataRequired(), NumberRange(min=0)])
    es_producto_nuevo = BooleanField('Es Producto Nuevo')
    submit = SubmitField('Guardar Producto')

class InventarioForm(FlaskForm):
    stock_actual = IntegerField('Stock Actual', validators=[DataRequired(), NumberRange(min=0)])
    stock_minimo = IntegerField('Stock Mínimo', validators=[Optional(), NumberRange(min=0)])
    stock_optimo = IntegerField('Stock Óptimo', validators=[Optional(), NumberRange(min=0)])
    ubicacion = StringField('Ubicación en Almacén', validators=[Optional(), Length(max=100)])
    submit = SubmitField('Actualizar Inventario')

# Rutas
@inventario_bp.route('/')
@login_required
@vendedor_required
def index():
    print("🔧 DEBUG: Iniciando función index()")
    
    # Filtros
    categoria = request.args.get('categoria', '')
    busqueda = request.args.get('busqueda', '')
    stock_bajo = request.args.get('stock_bajo', '')
    
    # ✅ INICIALIZAR ESTADÍSTICAS CON VALORES POR DEFECTO PRIMERO
    estadisticas = {
        'total_productos': 0,
        'stock_bajo': 0,
        'excedente': 0,
        'optimo': 0
    }
    
    # ✅ CALCULAR ESTADÍSTICAS PARA LAS TARJETAS SUPERIORES
    try:
        print("🔧 DEBUG: Calculando estadísticas...")
        
        # Obtener TODOS los inventarios para estadísticas (sin filtros)
        todos_inventarios = db.session.query(
            Inventario.stock_actual,
            Inventario.stock_minimo,
            Inventario.stock_optimo
        ).all()
        
        print(f"🔧 DEBUG: Encontrados {len(todos_inventarios)} inventarios en total")
        
        total_productos = len(todos_inventarios)
        
        # Calcular estadísticas correctas
        stock_bajo_count = 0
        excedente_count = 0
        optimo_count = 0
        
        for inv in todos_inventarios:
            try:
                stock_actual = int(inv.stock_actual or 0)
                stock_minimo = int(inv.stock_minimo or 10)  # ✅ Default 10 si es None
                stock_optimo = int(inv.stock_optimo or 120)  # ✅ Default 120 si es None
                
                if stock_actual < stock_minimo:
                    stock_bajo_count += 1
                elif stock_actual > stock_optimo:
                    excedente_count += 1
                else:
                    optimo_count += 1
                    
            except (ValueError, TypeError) as e:
                print(f"⚠️ Error procesando inventario: {e}")
                optimo_count += 1  # Default a óptimo si hay error
        
        # Actualizar estadísticas calculadas
        estadisticas = {
            'total_productos': total_productos,
            'stock_bajo': stock_bajo_count,
            'excedente': excedente_count,
            'optimo': optimo_count
        }
        
        # Debug - verificar cálculos
        print(f"📊 ESTADÍSTICAS CALCULADAS:")
        print(f"   Total productos: {estadisticas['total_productos']}")
        print(f"   Stock bajo: {estadisticas['stock_bajo']}")
        print(f"   Excedente: {estadisticas['excedente']}")
        print(f"   Óptimo: {estadisticas['optimo']}")
        
    except Exception as e:
        print(f" Error calculando estadísticas: {e}")
        import traceback
        traceback.print_exc()
    
    # Query principal para la tabla (CON filtros)
    try:
        query = db.session.query(
            Inventario.id,
            Inventario.stock_actual,
            Inventario.stock_minimo,
            Inventario.stock_optimo,
            Inventario.ubicacion,
            Producto.id.label('producto_id'),
            Producto.codigo,
            Producto.categoria,
            Producto.modelo_carro,
            Producto.descripcion,
            Producto.precio_unitario,
            Producto.es_producto_nuevo
        ).outerjoin(
            Producto, Inventario.producto_id == Producto.id
        )
        
        # Aplicar filtros
        if categoria:
            query = query.filter(Producto.categoria == categoria)
        if busqueda:
            query = query.filter(
                (Producto.codigo.ilike(f'%{busqueda}%')) | 
                (Producto.modelo_carro.ilike(f'%{busqueda}%')) |
                (Producto.descripcion.ilike(f'%{busqueda}%'))
            )
        if stock_bajo == 'true':
            query = query.filter(
                Inventario.stock_actual.isnot(None),
                Inventario.stock_minimo.isnot(None),
                db.func.cast(Inventario.stock_actual, db.Integer) <= db.func.cast(Inventario.stock_minimo, db.Integer)
            )
        
        # Ejecutar consulta
        inventario_raw = query.order_by(Producto.categoria, Producto.modelo_carro).all()
        
        print(f"🔧 DEBUG: Query principal retornó {len(inventario_raw)} productos")
        
    except Exception as e:
        print(f"❌ Error en query principal: {e}")
        inventario_raw = []
    
    # ✅ CONVERTIR A DICCIONARIOS SIMPLES PARA EVITAR PROBLEMAS CON JINJA2
    inventario = []
    for row in inventario_raw:
        try:
            stock_actual = int(row.stock_actual or 0)
            stock_minimo = int(row.stock_minimo or 10)
            stock_optimo = int(row.stock_optimo or 120)
            
            if stock_actual < stock_minimo:
                estado = 'bajo'
                estado_texto = 'Stock Bajo'
                estado_color = 'danger'
            elif stock_actual > stock_optimo:
                estado = 'excedente'
                estado_texto = 'Excedente'
                estado_color = 'warning'
            else:
                estado = 'optimo'
                estado_texto = 'Óptimo'
                estado_color = 'success'
            
            inventario.append({
                'id': row.id,
                'stock_actual': stock_actual,
                'stock_minimo': stock_minimo,
                'stock_optimo': stock_optimo,
                'ubicacion': row.ubicacion or '',
                'producto_id': row.producto_id,
                'codigo': row.codigo,
                'categoria': row.categoria,
                'modelo_carro': row.modelo_carro,
                'descripcion': row.descripcion,
                'precio_unitario': row.precio_unitario,
                'es_producto_nuevo': row.es_producto_nuevo,
                'estado': estado,
                'estado_texto': estado_texto,
                'estado_color': estado_color
            })
            
        except Exception as e:
            print(f"️ Error procesando fila inventario: {e}")
            continue
    
    # Obtener categorías para filtro
    try:
        categorias = db.session.query(Producto.categoria).distinct().all()
    except Exception as e:
        print(f"⚠️ Error obteniendo categorías: {e}")
        categorias = []
    
    print(f"🔧 DEBUG: Enviando al template:")
    print(f"   - Inventario: {len(inventario)} items")
    print(f"   - Estadísticas: {estadisticas}")
    print(f"   - Categorías: {len(categorias)}")
    
    return render_template(
        'inventario/index.html',
        inventario=inventario,
        estadisticas=estadisticas,
        categorias=[cat[0] for cat in categorias if cat and cat[0]],
        categoria_actual=categoria,
        busqueda=busqueda,
        stock_bajo=stock_bajo == 'true',
        title='Gestión de Inventario'
    )

@inventario_bp.route('/productos/nuevo', methods=['GET', 'POST'])
@login_required
@admin_required
def nuevo_producto():
    form = ProductoForm()
    
    if form.validate_on_submit():
        try:
            # Obtener categoría directamente del campo de texto
            categoria = form.categoria.data.strip()
            
            if not categoria:
                flash('La categoría no puede estar vacía', 'danger')
                return render_template('inventario/producto_form.html', form=form, title='Nuevo Producto')
            
            # Verificar si el código ya existe
            if Producto.query.filter_by(codigo=form.codigo.data).first():
                flash('El código de producto ya existe', 'danger')
                return render_template('inventario/producto_form.html', form=form, title='Nuevo Producto')
            
            # Crear producto
            producto = Producto(
                codigo=form.codigo.data,
                categoria=categoria,
                modelo_carro=form.modelo_carro.data,
                descripcion=form.descripcion.data or '',
                precio_unitario=form.precio_unitario.data,
                es_producto_nuevo=form.es_producto_nuevo.data
            )
            
            db.session.add(producto)
            db.session.commit()
            
            flash('Producto creado correctamente. Ahora registre su inventario inicial.', 'success')
            return redirect(url_for('inventario.editar_inventario', producto_id=producto.id))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error al crear el producto: {str(e)}', 'danger')
            print(f"Error en nuevo_producto: {e}")
    
    return render_template('inventario/producto_form.html', form=form, title='Nuevo Producto')

@inventario_bp.route('/productos/<int:producto_id>/editar', methods=['GET', 'POST'])
@login_required
@admin_required
def editar_producto(producto_id):
    try:
        producto = Producto.query.get_or_404(producto_id)
        form = ProductoForm(obj=producto)
        
        if form.validate_on_submit():
            categoria = form.categoria.data.strip()
            
            if not categoria:
                flash('La categoría no puede estar vacía', 'danger')
                return render_template('inventario/producto_form.html', form=form, producto=producto, title='Editar Producto')
            
            # Verificar si el código ya existe y no es este producto
            producto_existente = Producto.query.filter_by(codigo=form.codigo.data).first()
            if producto_existente and producto_existente.id != producto_id:
                flash('El código de producto ya existe', 'danger')
                return render_template('inventario/producto_form.html', form=form, producto=producto, title='Editar Producto')
            
            # Actualizar producto
            producto.codigo = form.codigo.data
            producto.categoria = categoria
            producto.modelo_carro = form.modelo_carro.data
            producto.descripcion = form.descripcion.data or ''
            producto.precio_unitario = form.precio_unitario.data
            producto.es_producto_nuevo = form.es_producto_nuevo.data
            
            db.session.commit()
            
            flash('Producto actualizado correctamente', 'success')
            return redirect(url_for('inventario.index'))
            
    except Exception as e:
        db.session.rollback()
        flash(f'Error al editar el producto: {str(e)}', 'danger')
        print(f"Error en editar_producto: {e}")
        return redirect(url_for('inventario.index'))
    
    return render_template(
        'inventario/producto_form.html',
        form=form,
        producto=producto,
        title='Editar Producto'
    )

@inventario_bp.route('/productos/<int:producto_id>/inventario', methods=['GET', 'POST'])
@login_required
@admin_required
def editar_inventario(producto_id):
    try:
        producto = Producto.query.get_or_404(producto_id)
        inventario = Inventario.query.filter_by(producto_id=producto_id).first()
        
        # Si no tiene registro de inventario, crear uno
        if not inventario:
            inventario = Inventario(producto_id=producto_id, stock_actual=0, stock_minimo=10, stock_optimo=120)
            db.session.add(inventario)
            db.session.commit()
        
        form = InventarioForm(obj=inventario)
        
        if form.validate_on_submit():
            inventario.stock_actual = form.stock_actual.data
            inventario.stock_minimo = form.stock_minimo.data or 10
            inventario.stock_optimo = form.stock_optimo.data or 120
            inventario.ubicacion = form.ubicacion.data or ''
            
            db.session.commit()
            
            flash('Inventario actualizado correctamente', 'success')
            return redirect(url_for('inventario.index'))
            
    except Exception as e:
        db.session.rollback()
        flash(f'Error al actualizar inventario: {str(e)}', 'danger')
        print(f"Error en editar_inventario: {e}")
        return redirect(url_for('inventario.index'))
    
    return render_template(
        'inventario/inventario_form.html',
        form=form,
        producto=producto,
        inventario=inventario,
        title='Actualizar Inventario'
    )

@inventario_bp.route('/excedente')
@login_required
@admin_required
def inventario_excedente():
    try:
        query = db.session.query(Producto, Inventario).join(
            Inventario, Producto.id == Inventario.producto_id
        ).filter(
            Inventario.stock_optimo.isnot(None),
            Inventario.stock_actual > Inventario.stock_optimo
        ).order_by(
            (Inventario.stock_actual - Inventario.stock_optimo).desc()
        )
        
        inventario_excedente = query.all()
        
        total_productos = len(inventario_excedente)
        total_excedente = sum(inv.stock_actual - inv.stock_optimo for _, inv in inventario_excedente)
        valor_excedente = sum(
            (inv.stock_actual - inv.stock_optimo) * float(prod.precio_unitario)
            for prod, inv in inventario_excedente
        )
        
        return render_template(
            'inventario/excedente.html',
            inventario=inventario_excedente,
            total_productos=total_productos,
            total_excedente=total_excedente,
            valor_excedente=valor_excedente,
            title='Inventario Excedente'
        )
    except Exception as e:
        flash(f'Error al cargar inventario excedente: {str(e)}', 'danger')
        return redirect(url_for('inventario.index'))

@inventario_bp.route('/bajo')
@login_required
@vendedor_required
def inventario_bajo():
    try:
        query = db.session.query(Producto, Inventario).join(
            Inventario, Producto.id == Inventario.producto_id
        ).filter(
            Inventario.stock_minimo.isnot(None),
            Inventario.stock_actual <= Inventario.stock_minimo
        ).order_by(
            (Inventario.stock_minimo - Inventario.stock_actual).desc()
        )
        
        inventario_bajo = query.all()
        
        total_productos = len(inventario_bajo)
        total_faltante = sum(max(0, inv.stock_minimo - inv.stock_actual) for _, inv in inventario_bajo)
        
        return render_template(
            'inventario/bajo.html',
            inventario=inventario_bajo,
            total_productos=total_productos,
            total_faltante=total_faltante,
            title='Inventario Bajo'
        )
    except Exception as e:
        flash(f'Error al cargar inventario bajo: {str(e)}', 'danger')
        return redirect(url_for('inventario.index'))

@inventario_bp.route('/importar', methods=['GET', 'POST'])
@login_required
@admin_required
def importar_inventario():
    if request.method == 'POST':
        if 'archivo_csv' not in request.files:
            flash('No se seleccionó ningún archivo', 'danger')
            return redirect(request.url)
        
        archivo = request.files['archivo_csv']
        if archivo.filename == '':
            flash('No se seleccionó ningún archivo', 'danger')
            return redirect(request.url)
        
        if archivo and archivo.filename.endswith('.csv'):
            try:
                import pandas as pd
                import io
                
                csv_data = archivo.read().decode('utf-8')
                df = pd.read_csv(io.StringIO(csv_data))
                
                required_columns = ['codigo', 'categoria', 'modelo_carro', 'precio_unitario', 'stock_actual']
                for col in required_columns:
                    if col not in df.columns:
                        flash(f'El archivo CSV no contiene la columna {col}', 'danger')
                        return redirect(request.url)
                
                productos_importados = 0
                inventarios_actualizados = 0
                errores = 0
                
                for _, row in df.iterrows():
                    try:
                        codigo = str(row['codigo']).strip()
                        categoria = str(row['categoria']).strip()
                        modelo_carro = str(row['modelo_carro']).strip()
                        precio_unitario = float(row['precio_unitario'])
                        stock_actual = int(row['stock_actual'])
                        
                        stock_minimo = int(row['stock_minimo']) if 'stock_minimo' in row and not pd.isna(row['stock_minimo']) else 10
                        stock_optimo = int(row['stock_optimo']) if 'stock_optimo' in row and not pd.isna(row['stock_optimo']) else 120
                        
                        producto = Producto.query.filter_by(codigo=codigo).first()
                        
                        if not producto:
                            producto = Producto(
                                codigo=codigo,
                                categoria=categoria,
                                modelo_carro=modelo_carro,
                                descripcion=row.get('descripcion', ''),
                                precio_unitario=precio_unitario,
                                es_producto_nuevo=bool(row.get('es_producto_nuevo', False))
                            )
                            db.session.add(producto)
                            db.session.flush()
                            productos_importados += 1
                        
                        inventario = Inventario.query.filter_by(producto_id=producto.id).first()
                        
                        if not inventario:
                            inventario = Inventario(
                                producto_id=producto.id,
                                stock_actual=stock_actual,
                                stock_minimo=stock_minimo,
                                stock_optimo=stock_optimo,
                                ubicacion=row.get('ubicacion', '')
                            )
                            db.session.add(inventario)
                        else:
                            inventario.stock_actual = stock_actual
                            inventario.stock_minimo = stock_minimo
                            inventario.stock_optimo = stock_optimo
                            if 'ubicacion' in row and not pd.isna(row['ubicacion']):
                                inventario.ubicacion = str(row['ubicacion'])
                        
                        inventarios_actualizados += 1
                        
                    except Exception as e:
                        errores += 1
                        print(f"Error procesando fila: {e}")
                
                db.session.commit()
                
                flash(f'Importación completada: {productos_importados} productos nuevos, {inventarios_actualizados} inventarios actualizados, {errores} errores', 'info')
                return redirect(url_for('inventario.index'))
                
            except Exception as e:
                flash(f'Error al procesar el archivo CSV: {str(e)}', 'danger')
                return redirect(request.url)
        else:
            flash('El archivo debe tener formato CSV', 'danger')
            return redirect(request.url)
    
    return render_template('inventario/importar.html', title='Importar Inventario')