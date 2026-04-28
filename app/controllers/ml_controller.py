from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from flask_wtf import FlaskForm
from wtforms import SelectField, DateField, IntegerField, SubmitField, FileField
from wtforms.validators import DataRequired, Optional
from flask_wtf.file import FileAllowed, FileRequired
from werkzeug.utils import secure_filename

from app import db
from app.models.producto import Producto
from app.models.venta import Venta
from app.models.inventario import Inventario
from app.models.prediccion import Prediccion
from app.models.resultado import ResultadoComparativo
from app.utils.auth_utils import admin_required
from app.utils.date_utils import str_a_fecha

from datetime import datetime, timedelta
import joblib
import os
import pandas as pd
import numpy as np
from sklearn.ensemble import ExtraTreesRegressor
from sklearn.preprocessing import RobustScaler
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

ml_bp = Blueprint('ml', __name__, url_prefix='/ml')

# ===== FUNCIONES ML INTEGRADAS Y SEGURAS =====

def preparar_datos_seguro(ventas_df, inventario_df):
    """Preparar datos de forma segura, evitando infinitos"""
    
    # Crear características básicas
    data = ventas_df.copy()
    
    # Agregar información de inventario
    data = data.merge(inventario_df, on='producto_id', how='left')
    
    # Rellenar valores nulos con valores seguros
    data['stock_actual'] = data['stock_actual'].fillna(0)
    data['stock_minimo'] = data['stock_minimo'].fillna(0)
    data['stock_optimo'] = data['stock_optimo'].fillna(data['stock_actual'])
    
    return data

def crear_features_seguro(data):
    """Crear características de forma segura (versión básica) - CORREGIDA"""
    
    epsilon = 1e-8  # Para evitar división por cero
    
    # Características básicas
    features = data.copy()
    
    # ✅ CONVERSIÓN A FLOAT PARA EVITAR ERROR DECIMAL
    features['precio_unitario'] = features['precio_unitario'].astype(float)
    features['cantidad'] = features['cantidad'].astype(float)
    
    # Encoding de categorías
    features['categoria_encoded'] = features['categoria'].astype('category').cat.codes
    
    # Características temporales
    features['mes'] = features['fecha'].dt.month
    features['dia_semana'] = features['fecha'].dt.weekday
    features['es_fin_semana'] = (features['dia_semana'] >= 5).astype(int)
    
    # ✅ CARACTERÍSTICAS DE PRECIO (SEGURAS CON FLOAT)
    features['precio_por_cantidad'] = features['precio_unitario'] / (features['cantidad'] + epsilon)
    
    # ✅ CARACTERÍSTICAS DE STOCK (SEGURAS)
    features['ratio_stock_actual'] = features['stock_actual'] / (features['stock_actual'] + epsilon)
    features['deficit_stock'] = np.maximum(0, features['stock_minimo'] - features['stock_actual'])
    
    # ✅ USAR CANTIDAD CORRECTA (de ventas, no de inventario)
    # Si hay conflicto de merge, usar cantidad_x (que viene de ventas)
    if 'cantidad_x' in features.columns:
        features['cantidad'] = features['cantidad_x'].astype(float)
    elif 'cantidad' not in features.columns:
        # Fallback si no existe cantidad
        features['cantidad'] = features['stock_actual'].astype(float)
    
    # Seleccionar características numéricas para el modelo
    feature_columns = [
        'producto_id', 'cantidad', 'precio_unitario', 'categoria_encoded',
        'mes', 'dia_semana', 'es_fin_semana', 'precio_por_cantidad',
        'stock_actual', 'ratio_stock_actual', 'deficit_stock'
    ]
    
    # ✅ VERIFICAR QUE TODAS LAS COLUMNAS EXISTEN
    features_disponibles = []
    for col in feature_columns:
        if col in features.columns:
            features_disponibles.append(col)
        else:
            print(f"⚠️ Columna {col} no disponible, omitiendo...")
    
    X = features[features_disponibles].values
    y = features['cantidad'].values
    
    # ✅ LIMPIEZA CRÍTICA PARA EVITAR ERROR
    # Reemplazar infinitos con valores finitos
    X = np.where(np.isinf(X), np.nan, X)
    
    # Reemplazar NaN con mediana por columna
    for i in range(X.shape[1]):
        col_data = X[:, i]
        if np.any(np.isnan(col_data)):
            median_val = np.nanmedian(col_data)
            if np.isnan(median_val):
                median_val = 0  # Fallback si todo es NaN
            X[:, i] = np.where(np.isnan(col_data), median_val, col_data)
    
    # Recortar valores extremos
    for i in range(X.shape[1]):
        p1, p99 = np.percentile(X[:, i], [1, 99])
        X[:, i] = np.clip(X[:, i], p1, p99)
    
    # ✅ VERIFICACIÓN FINAL MÁS ROBUSTA
    if np.any(np.isinf(X)) or np.any(np.isnan(X)):
        print("⚠️ Aún hay valores problemáticos, aplicando limpieza adicional...")
        X = np.nan_to_num(X, nan=0.0, posinf=1e6, neginf=-1e6)
    
    print(f"✅ Features creadas exitosamente: {X.shape[1]} características")
    print(f"✅ Muestras: {X.shape[0]}")
    
    return X, y, features_disponibles

# ===== FUNCIONES ESPECÍFICAS PARA EXCEL =====

def mapear_columnas_excel_autopartes(df):
    """Mapeo específico para tu archivo Excel a formato BD"""
    
    mapeo = {
        'Fecha': 'fecha_venta',
        'Código de Producto': 'codigo_producto', 
        'Categoría': 'categoria',
        'Cantidad': 'cantidad',
        'Precio Unitario': 'precio_unitario',
        'venta_total': 'precio_total',
        # Características ML ya calculadas
        'Año': 'anio',
        'Mes': 'mes',
        'Dia ': 'dia',
        'Dia_Semana ': 'dia_semana',
        'Trimestre': 'trimestre',
        'Mes_Seno (CRÍTICA PARA ML)': 'mes_seno',
        'Mes_Coseno (CRÍTICA PARA ML)': 'mes_coseno',
        'Dia_Semana_Seno': 'dia_semana_seno',
        'Dia_Semana_Coseno': 'dia_semana_coseno',
        'Rango_Precio': 'rango_precio',
        'Es_Fin_Semana': 'es_fin_semana',
        'Es_Inicio_Mes': 'es_inicio_mes',
        'Es_Fin_Mes': 'es_fin_mes',
        'Frecuencia_Producto': 'frecuencia_producto'
    }
    
    return df.rename(columns=mapeo)

def limpiar_datos_autopartes(df):
    """Limpieza específica para datos autopartes"""
    
    df_clean = df.copy()
    
    # 1. Convertir fecha
    df_clean['fecha_venta'] = pd.to_datetime(df_clean['fecha_venta'])
    
    # 2. Validar cantidad
    df_clean = df_clean[df_clean['cantidad'] > 0]
    
    # 3. Validar precios
    df_clean = df_clean[df_clean['precio_unitario'] > 0]
    
    # 4. Limpiar strings
    df_clean['codigo_producto'] = df_clean['codigo_producto'].str.strip()
    df_clean['categoria'] = df_clean['categoria'].str.strip()
    
    # 5. Convertir rango_precio a numérico para ML
    rango_mapping = {
        'ECONOMICO': 1,
        'MEDIO': 2, 
        'ALTO': 3,
        'PREMIUM': 4
    }
    df_clean['rango_precio_num'] = df_clean['rango_precio'].map(rango_mapping).fillna(2)
    
    return df_clean

def crear_producto_id_desde_codigo(codigos):
    """Crear producto_id numérico desde código de producto"""
    
    # Crear mapeo único de código → ID
    codigos_unicos = codigos.unique()
    mapeo_id = {codigo: idx + 1 for idx, codigo in enumerate(codigos_unicos)}
    
    return codigos.map(mapeo_id)

def procesar_excel_autopartes_historico(archivo_path):
    """Procesar específicamente tu archivo de ventas históricas"""
    
    try:
        # Leer Excel
        df = pd.read_excel(archivo_path)
        print(f"📊 Archivo leído: {df.shape[0]} registros, {df.shape[1]} columnas")
        
        # Mapear columnas
        df_mapeado = mapear_columnas_excel_autopartes(df)
        
        # Limpiar datos específicos
        df_limpio = limpiar_datos_autopartes(df_mapeado)
        
        # Crear producto_id desde código_producto
        df_limpio['producto_id'] = crear_producto_id_desde_codigo(df_limpio['codigo_producto'])
        
        print(f"✅ Procesamiento exitoso: {len(df_limpio)} registros válidos")
        return df_limpio, f"✅ {len(df_limpio)} registros procesados correctamente"
        
    except Exception as e:
        return None, f"❌ Error procesando archivo: {str(e)}"

# ===== FUNCIÓN CORREGIDA 1: INSERCIÓN DE VENTAS =====
def insertar_ventas_historicas_autopartes(df):
    """FUNCIÓN CORREGIDA - Insertar TODAS las ventas del Excel"""
    
    registros_insertados = 0
    productos_creados = 0
    errores = 0
    
    print(f"🚀 PROCESANDO {len(df)} REGISTROS DEL EXCEL")
    
    # Crear mapeo de códigos a productos existentes
    productos_existentes = {p.codigo: p.id for p in Producto.query.all()}
    print(f"📦 Productos existentes: {len(productos_existentes)}")

    for index, row in df.iterrows():
        try:
            codigo_producto = row['codigo_producto']

            # Buscar o crear producto
            if codigo_producto in productos_existentes:
                producto_id = productos_existentes[codigo_producto]
            else:
                # ✅ CREAR PRODUCTO CON CAMPOS CORRECTOS
                nuevo_producto = Producto(
                    codigo=codigo_producto,
                    categoria=row.get('categoria', 'General'),
                    modelo_carro=codigo_producto,  # ✅ Usar código como modelo
                    precio_unitario=float(row.get('precio_unitario', 0))  # ✅ CAMPO CORRECTO
                )
                db.session.add(nuevo_producto)
                db.session.flush()

                producto_id = nuevo_producto.id
                productos_existentes[codigo_producto] = producto_id
                productos_creados += 1

            # Procesar fecha correctamente
            fecha_venta = row.get('fecha_venta')
            if pd.isna(fecha_venta):
                fecha_venta = datetime.now()
            elif isinstance(fecha_venta, str):
                try:
                    fecha_venta = pd.to_datetime(fecha_venta).to_pydatetime()
                except:
                    fecha_venta = datetime.now()
            elif not isinstance(fecha_venta, datetime):
                try:
                    fecha_venta = pd.to_datetime(fecha_venta).to_pydatetime()
                except:
                    fecha_venta = datetime.now()

            # Verificar duplicados
            venta_existe = Venta.query.filter_by(
                producto_id=producto_id,
                fecha_venta=fecha_venta,  # ✅ CAMPO CORRECTO
                cantidad=int(row.get('cantidad', 1))
            ).first()
            
            if venta_existe:
                continue

            # ✅ CREAR VENTA CON CAMPOS CORRECTOS
            venta = Venta(
                producto_id=producto_id,
                cantidad=int(row.get('cantidad', 1)),
                precio_unitario=float(row.get('precio_unitario', 0)),
                precio_total=float(row.get('precio_total', 0)) or (int(row.get('cantidad', 1)) * float(row.get('precio_unitario', 0))),
                fecha_venta=fecha_venta,  # ✅ CAMPO CORRECTO
                usuario_id=current_user.id
            )

            db.session.add(venta)
            registros_insertados += 1
            
            # Commit cada 100 registros
            if registros_insertados % 100 == 0:
                db.session.commit()
                print(f"   ✅ Procesados: {registros_insertados} registros...")

        except Exception as e:
            print(f"❌ Error en registro {index}: {e}")
            errores += 1
            if errores > 50:
                break
            continue

    # Commit final
    try:
        db.session.commit()
        print(f"✅ COMMIT FINAL EXITOSO")
    except Exception as e:
        print(f"❌ Error en commit final: {e}")
        db.session.rollback()
        return 0
    
    # ✅ CREAR INVENTARIOS CON CAMPOS CORRECTOS
    try:
        for producto in Producto.query.all():
            inventario_existe = Inventario.query.filter_by(producto_id=producto.id).first()
            if not inventario_existe:
                inventario = Inventario(
                    producto_id=producto.id,
                    stock_actual=100,    # ✅ CAMPO CORRECTO
                    stock_minimo=10,     # ✅ CAMPO CORRECTO
                    stock_optimo=120     # ✅ CAMPO CORRECTO
                )
                db.session.add(inventario)
        
        db.session.commit()
    except Exception as e:
        print(f"⚠️ Error creando inventarios: {e}")
    
    print(f"\n🎯 RESUMEN FINAL:")
    print(f"✅ Productos creados: {productos_creados}")
    print(f"✅ Ventas insertadas: {registros_insertados}")
    print(f"❌ Errores: {errores}")
    
    return registros_insertados

def entrenar_modelo_seguro(X, y):
    """Entrenar modelo de forma segura"""
    
    try:
        print("🤖 Entrenando modelo...")
        
        # Dividir datos
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42
        )
        
        # ✅ USAR ROBUSTSCALER (más seguro que StandardScaler)
        scaler = RobustScaler()
        X_train_scaled = scaler.fit_transform(X_train)
        X_test_scaled = scaler.transform(X_test)
        
        # Verificación post-escalado
        if np.any(np.isinf(X_train_scaled)) or np.any(np.isnan(X_train_scaled)):
            raise ValueError("Escalado generó infinitos o NaN")
        
        # ✅ MODELO CON PARÁMETROS CONSERVADORES
        modelo = ExtraTreesRegressor(
            n_estimators=50,  # Reducido
            max_depth=8,      # Limitado
            min_samples_split=5,
            min_samples_leaf=3,
            random_state=42,
            n_jobs=1
        )
        
        # Entrenar
        modelo.fit(X_train_scaled, y_train)
        
        # Evaluar
        y_pred = modelo.predict(X_test_scaled)
        mae = mean_absolute_error(y_test, y_pred)
        rmse = np.sqrt(mean_squared_error(y_test, y_pred))
        r2 = r2_score(y_test, y_pred)
        
        metricas = {
            'mae': mae,
            'rmse': rmse,
            'r2': r2
        }
        
        # Importancias de características
        importancias = modelo.feature_importances_
        
        return modelo, scaler, importancias, metricas
        
    except Exception as e:
        print(f"Error en entrenamiento: {e}")
        raise

# ===== FORMULARIOS =====

class EntrenamientoForm(FlaskForm):
    fecha_inicio = DateField('Fecha Inicio', validators=[DataRequired()])
    fecha_fin = DateField('Fecha Fin', validators=[DataRequired()])
    submit = SubmitField('Entrenar Modelo')

class PrediccionForm(FlaskForm):
    categoria = SelectField('Categoría de Productos', validators=[Optional()])
    periodo_prediccion = SelectField('Período de Predicción', 
                                    choices=[
                                        ('7', 'Próximos 7 días'),
                                        ('14', 'Próximos 14 días'),
                                        ('30', 'Próximos 30 días'),
                                    ],
                                    validators=[DataRequired()])
    submit = SubmitField('Generar Predicciones')

class EvaluacionForm(FlaskForm):
    metrica = SelectField('Métrica de Evaluación', 
                         choices=[
                             ('mae', 'Error Absoluto Medio (MAE)'),
                             ('rmse', 'Error Cuadrático Medio (RMSE)'),
                             ('r2', 'Coeficiente de Determinación (R²)')
                         ],
                         validators=[DataRequired()])
    periodo_evaluacion = SelectField('Período de Evaluación',
                                   choices=[
                                       ('7', 'Últimos 7 días'),
                                       ('30', 'Últimos 30 días'),
                                       ('90', 'Últimos 90 días'),
                                       ('custom', 'Personalizado')
                                   ],
                                   validators=[DataRequired()])
    fecha_inicio = DateField('Fecha Inicio', validators=[Optional()])
    fecha_fin = DateField('Fecha Fin', validators=[Optional()])
    submit = SubmitField('Evaluar Resultados')

class CargaDatosForm(FlaskForm):
    archivo_historicos = FileField('Archivo de Ventas Históricas', 
                                  validators=[
                                      FileRequired(),
                                      FileAllowed(['xlsx', 'xls', 'csv'], 'Solo archivos Excel o CSV')
                                  ])
    submit = SubmitField('Cargar Datos Históricos')

# ===== RUTAS =====

@ml_bp.route('/')
@login_required
@admin_required
def index():
    # Obtener estado del modelo
    modelo_path = os.path.join('instance', 'ml_models', 'extra_trees_model.joblib')
    modelo_entrenado = os.path.exists(modelo_path)
    
    # Obtener fecha de última actualización del modelo
    ultima_actualizacion = None
    if modelo_entrenado:
        ultima_actualizacion = datetime.fromtimestamp(os.path.getmtime(modelo_path))
    
    # Obtener métricas del modelo si existen
    metricas = None
    resultado = ResultadoComparativo.obtener_ultimo_resultado()
    if resultado:
        metricas = {
            'mae': float(resultado.mae) if resultado.mae else None,
            'reduccion_inventario': float(resultado.reduccion_inventario_excedente) if resultado.reduccion_inventario_excedente else None,
            'incremento_ventas': float(resultado.incremento_ventas) if resultado.incremento_ventas else None
        }
    
    # ✅ CORREGIDO: Usar solo campos existentes
    ultimas_predicciones = Prediccion.query.order_by(Prediccion.fecha_prediccion.desc()).limit(5).all()
    
    return render_template(
        'ml/index.html',
        modelo_entrenado=modelo_entrenado,
        ultima_actualizacion=ultima_actualizacion,
        metricas=metricas,
        predicciones=ultimas_predicciones,
        title='Machine Learning Dashboard'
    )

# ✅ RUTA ESPECÍFICA PARA TU EXCEL
@ml_bp.route('/cargar-historicos', methods=['GET', 'POST'])
@login_required
@admin_required
def cargar_historicos():
    """Ruta específica para cargar tu archivo de ventas históricas"""
    
    form = CargaDatosForm()
    
    if form.validate_on_submit():
        try:
            archivo = form.archivo_historicos.data
            if not archivo:
                flash('No se seleccionó archivo', 'warning')
                return redirect(url_for('ml.cargar_historicos'))
            
            # Guardar archivo temporal
            os.makedirs('temp_uploads', exist_ok=True)
            filename = secure_filename(archivo.filename)
            filepath = os.path.join('temp_uploads', filename)
            archivo.save(filepath)
            
            # Procesar con función específica
            df_historicos, mensaje = procesar_excel_autopartes_historico(filepath)
            
            if df_historicos is not None:
                # Insertar en BD
                registros = insertar_ventas_historicas_autopartes(df_historicos)
                
                flash(f'{mensaje}. {registros} registros insertados.', 'success')
                os.remove(filepath)  # Limpiar
                
                return redirect(url_for('ml.entrenamiento'))
            else:
                flash(mensaje, 'danger')
                
        except Exception as e:
            flash(f'Error: {str(e)}', 'danger')
    
    return render_template('ml/cargar_historicos.html', form=form, title='Cargar Ventas Históricas')

# ===== FUNCIÓN CORREGIDA 2: ENTRENAMIENTO =====
@ml_bp.route('/entrenamiento', methods=['GET', 'POST'])
@login_required
@admin_required
def entrenamiento():
    """FUNCIÓN CORREGIDA - Entrenamiento funciona con datos Excel + datos normales"""
    
    form = EntrenamientoForm()
    
    # Establecer fechas predeterminadas
    if not form.fecha_inicio.data:
        form.fecha_inicio.data = datetime.today() - timedelta(days=180)
    if not form.fecha_fin.data:
        form.fecha_fin.data = datetime.today()
    
    if form.validate_on_submit():
        fecha_inicio = form.fecha_inicio.data
        fecha_fin = form.fecha_fin.data
        
        try:
            print("🤖 INICIANDO ENTRENAMIENTO ML")
            
            # ✅ CONSULTA CORREGIDA - CAMPOS EXISTENTES
            ventas_query = db.session.query(
                Venta.id,
                Venta.producto_id,
                Venta.cantidad,
                Venta.precio_unitario,
                Venta.fecha_venta,  # ✅ CAMPO CORRECTO
                Producto.categoria,
                Producto.codigo,
                Producto.modelo_carro
            ).join(
                Producto, Venta.producto_id == Producto.id
            ).filter(
                Venta.fecha_venta >= fecha_inicio,  # ✅ CAMPO CORRECTO
                Venta.fecha_venta <= fecha_fin      # ✅ CAMPO CORRECTO
            ).all()
            
            print(f"📊 DATOS DISPONIBLES: {len(ventas_query)} ventas")
            
            if len(ventas_query) < 10:
                flash('Necesitas al menos 10 ventas para entrenar el modelo', 'warning')
                return redirect(url_for('ml.entrenamiento'))

            # ✅ DATAFRAME CORREGIDO
            ventas_df = pd.DataFrame([{
                'id': v.id,
                'producto_id': v.producto_id,
                'cantidad': v.cantidad,
                'precio_unitario': v.precio_unitario,
                'fecha': v.fecha_venta,  # ✅ CAMPO CORRECTO
                'categoria': v.categoria,
                'codigo': v.codigo,
                'modelo_carro': v.modelo_carro
            } for v in ventas_query])

            # ✅ INVENTARIO CORREGIDO
            inventario_query = Inventario.query.all()
            inventario_df = pd.DataFrame([{
                'producto_id': inv.producto_id,
                'stock_minimo': inv.stock_minimo, # ✅ CAMPO CORRECTO
                'stock_actual': inv.stock_actual, # ✅ CAMPO CORRECTO
                'stock_optimo': inv.stock_optimo  # ✅ CAMPO CORRECTO
            } for inv in inventario_query])

            print(f"📦 INVENTARIO: {len(inventario_df)} productos")

            # ✅ DETECTAR AUTOMÁTICAMENTE tipo de datos
            tiene_datos_excel = len(ventas_query) > 500
            
            print(f"🎯 TIPO DE DATOS: {'Excel (históricos)' if tiene_datos_excel else 'App (normales)'}")

            # Preparar datos según el tipo
            data_procesada = preparar_datos_seguro(ventas_df, inventario_df)
            X, y, feature_columns = crear_features_seguro(data_procesada)

            # Entrenar modelo
            model, scaler, importancias_features, metricas = entrenar_modelo_seguro(X, y)

            # Guardar modelo y scaler
            os.makedirs(os.path.join('instance', 'ml_models'), exist_ok=True)
            joblib.dump(model, os.path.join('instance', 'ml_models', 'extra_trees_model.joblib'))
            joblib.dump(scaler, os.path.join('instance', 'ml_models', 'scaler.joblib'))
            
            # Guardar metadatos
            metadata = {
                'fecha_entrenamiento': datetime.now().isoformat(),
                'periodo_inicio': fecha_inicio.isoformat(),
                'periodo_fin': fecha_fin.isoformat(),
                'num_muestras': len(data_procesada),
                'metricas': metricas,
                'feature_columns': feature_columns,
                'importancias': importancias_features.tolist(),
                'tipo_datos': 'excel' if tiene_datos_excel else 'app'
            }
            
            import json
            with open(os.path.join('instance', 'ml_models', 'model_metadata.json'), 'w') as f:
                json.dump(metadata, f)

            print(f"✅ MODELO ENTRENADO EXITOSAMENTE")
            print(f"   📊 Datos: {len(X)} registros")
            print(f"   🎯 Features: {len(feature_columns)}")
            print(f"   📈 R² Score: {metricas.get('r2', 'N/A')}")
            
            flash(f'¡Modelo entrenado exitosamente! R² Score: {metricas.get("r2", 0):.3f}', 'success')
            return redirect(url_for('ml.prediccion'))

        except Exception as e:
            print(f"❌ ERROR EN ENTRENAMIENTO: {str(e)}")
            import traceback
            traceback.print_exc()
            flash(f'Error entrenando modelo: {str(e)}', 'danger')
    
    # GET request - mostrar página
    total_ventas = Venta.query.count()
    total_productos = Producto.query.count()
    modelo_existe = os.path.exists(os.path.join('instance', 'ml_models', 'extra_trees_model.joblib'))
    
    # Determinar estado del sistema
    if total_ventas >= 500:
        estado = "🚀 Excelente - Datos históricos cargados"
        color = "success"
    elif total_ventas >= 50:
        estado = "✅ Bueno - Suficientes datos para ML"
        color = "info"  
    elif total_ventas >= 10:
        estado = "⚠️ Básico - Datos mínimos para entrenar"
        color = "warning"
    else:
        estado = "❌ Insuficiente - Necesitas más datos"
        color = "danger"

    return render_template('ml/entrenamiento.html', 
                          form=form,
                          title='Entrenamiento ML',
                          total_ventas=total_ventas,
                          total_productos=total_productos,
                          modelo_existe=modelo_existe,
                          estado=estado,
                          color=color)

# ===== FUNCIÓN CORREGIDA 3: PREDICCIONES ACTIVADAS =====
@ml_bp.route('/prediccion', methods=['GET', 'POST'])
@login_required
@admin_required
def prediccion():
    """FUNCIÓN CORREGIDA - Predicciones funcionales"""
    
    form = PrediccionForm()
    
    # Cargar categorías para el formulario
    categorias = db.session.query(Producto.categoria).distinct().all()
    opciones_categoria = [('', 'Todas las categorías')] + [(cat[0], cat[0]) for cat in categorias]
    form.categoria.choices = opciones_categoria
    
    predicciones_generadas = []
    
    if form.validate_on_submit():
        try:
            # Verificar si existe modelo entrenado
            modelo_path = os.path.join('instance', 'ml_models', 'extra_trees_model.joblib')
            scaler_path = os.path.join('instance', 'ml_models', 'scaler.joblib')
            
            if not os.path.exists(modelo_path) or not os.path.exists(scaler_path):
                flash('Primero debes entrenar el modelo antes de hacer predicciones', 'warning')
                return redirect(url_for('ml.entrenamiento'))
            
            # Cargar modelo y scaler
            modelo = joblib.load(modelo_path)
            scaler = joblib.load(scaler_path)
            
            # Obtener parámetros del formulario
            categoria_filtro = form.categoria.data
            dias_prediccion = int(form.periodo_prediccion.data)
            
            print(f"🔮 GENERANDO PREDICCIONES para {dias_prediccion} días")
            
            # Obtener productos para predicción
            if categoria_filtro:
                productos_query = Producto.query.filter_by(categoria=categoria_filtro).all()
            else:
                productos_query = Producto.query.all()

            if len(productos_query) == 0:
                flash('No se encontraron productos para la categoría seleccionada', 'warning')
                return redirect(url_for('ml.prediccion'))

            # Generar predicciones para cada producto
            fecha_actual = datetime.now()
            
            for producto in productos_query[:10]:  # Limitar a 10 productos
                try:
                    # Obtener datos históricos del producto
                    ventas_historicas = Venta.query.filter_by(
                        producto_id=producto.id
                    ).order_by(Venta.fecha_venta.desc()).limit(30).all()
                    
                    if len(ventas_historicas) == 0:
                        continue
                    
                    # Calcular características básicas
                    cantidad_promedio = np.mean([v.cantidad for v in ventas_historicas])
                    precio_promedio = np.mean([float(v.precio_unitario) for v in ventas_historicas])
                    
                    # Obtener inventario
                    inventario = Inventario.query.filter_by(producto_id=producto.id).first()
                    stock_actual = inventario.stock_actual if inventario else 0
                    
                    # Crear características para predicción
                    mes_actual = fecha_actual.month
                    dia_semana = fecha_actual.weekday()
                    es_fin_semana = 1 if dia_semana >= 5 else 0
                    
                    # Preparar datos para el modelo
                    features = np.array([[
                        producto.id,                    # producto_id
                        cantidad_promedio,              # cantidad promedio
                        precio_promedio,                # precio_unitario
                        hash(producto.categoria) % 100, # categoria_encoded
                        mes_actual,                     # mes
                        dia_semana,                     # dia_semana
                        es_fin_semana,                  # es_fin_semana
                        precio_promedio / (cantidad_promedio + 1e-8),  # precio_por_cantidad
                        stock_actual,                   # stock_actual
                        stock_actual / (stock_actual + 1e-8),  # ratio_stock_actual
                        max(0, 10 - stock_actual)      # deficit_stock
                    ]])
                    
                    # Escalar características
                    features_scaled = scaler.transform(features)
                    
                    # Hacer predicción
                    prediccion_cantidad = modelo.predict(features_scaled)[0]
                    prediccion_cantidad = max(0, round(prediccion_cantidad))
                    
                    # Calcular confianza
                    confianza = min(95, max(60, 100 - abs(prediccion_cantidad - cantidad_promedio) * 5))
                    
                    # ✅ CREAR REGISTRO CON CAMPO CORRECTO
                    nueva_prediccion = Prediccion(
                        producto_id=producto.id,
                        fecha_prediccion=fecha_actual,
                        cantidad_predicha=prediccion_cantidad,  # ✅ CAMPO CORRECTO
                        fecha_inicio=fecha_actual.date(),
                        fecha_fin=(fecha_actual + timedelta(days=dias_prediccion)).date(),
                        confianza=confianza/100,
                        modelo_version='ExtraTreesRegressor'
                    )
                    
                    db.session.add(nueva_prediccion)
                    
                    # Agregar a resultados
                    predicciones_generadas.append({
                        'producto': producto.codigo,
                        'codigo': producto.codigo,
                        'categoria': producto.categoria,
                        'prediccion': prediccion_cantidad,
                        'confianza': confianza,
                        'stock_actual': stock_actual,
                        'promedio_historico': round(cantidad_promedio, 1)
                    })
                    
                except Exception as e:
                    print(f"Error prediciendo para producto {producto.id}: {e}")
                    continue
            
            # Guardar predicciones en BD
            db.session.commit()
            
            if predicciones_generadas:
                flash(f'¡Predicciones generadas exitosamente! {len(predicciones_generadas)} productos analizados.', 'success')
            else:
                flash('No se pudieron generar predicciones. Verifica que tengas datos históricos.', 'warning')
                
        except Exception as e:
            print(f"Error en predicciones: {e}")
            flash(f'Error generando predicciones: {str(e)}', 'danger')
    
    return render_template('ml/prediccion.html', 
                          form=form, 
                          predicciones=predicciones_generadas,
                          title='Generación de Predicciones')


@ml_bp.route('/resultados-prediccion')  # ← CORREGIDO
@login_required
@admin_required
def resultados_prediccion():
    # Obtener predicciones recientes
    predicciones = Prediccion.query.order_by(
        Prediccion.fecha_prediccion.desc()
    ).limit(20).all()
    
    # ✅ CREAR DATOS COMPLETOS PARA EL TEMPLATE
    datos_predicciones = []
    
    for pred in predicciones:
        # Obtener producto relacionado
        producto = Producto.query.get(pred.producto_id)
        if not producto:
            continue
            
        # Obtener inventario actual
        inventario = Inventario.query.filter_by(producto_id=pred.producto_id).first()
        stock_actual = inventario.stock_actual if inventario else 0
        
        datos_predicciones.append({
            'prediccion': pred,
            'codigo': producto.codigo,
            'categoria': producto.categoria,
            'modelo_carro': producto.modelo_carro,
            'stock_actual': stock_actual
        })
    
    return render_template('ml/resultados_prediccion.html', 
                          predicciones=datos_predicciones,  # ✅ DATOS COMPLETOS
                          title='Resultados de Predicciones')

@ml_bp.route('/evaluacion', methods=['GET', 'POST'])
@login_required
@admin_required
def evaluacion():
    form = EvaluacionForm()
    
    if form.validate_on_submit():
        try:
            # Obtener parámetros
            metrica = form.metrica.data
            periodo = form.periodo_evaluacion.data
            
            # Calcular fechas
            fecha_fin = datetime.now()
            if periodo == '7':
                fecha_inicio = fecha_fin - timedelta(days=7)
            elif periodo == '30':
                fecha_inicio = fecha_fin - timedelta(days=30)
            elif periodo == '90':
                fecha_inicio = fecha_fin - timedelta(days=90)
            else:
                fecha_inicio = form.fecha_inicio.data
                fecha_fin = form.fecha_fin.data
            
            # Obtener predicciones del período
            predicciones = Prediccion.query.filter(
                Prediccion.fecha_prediccion >= fecha_inicio,
                Prediccion.fecha_prediccion <= fecha_fin
            ).all()
            
            if not predicciones:
                flash('No hay predicciones en el período seleccionado', 'warning')
                return redirect(url_for('ml.evaluacion'))
            
            # Calcular métricas de evaluación
            errores = []
            for pred in predicciones:
                # Buscar ventas reales posteriores a la predicción
                ventas_reales = Venta.query.filter(
                    Venta.producto_id == pred.producto_id,
                    Venta.fecha_venta >= pred.fecha_prediccion,
                    Venta.fecha_venta <= pred.fecha_prediccion + timedelta(days=7)  # Usar período fijo
                ).all()
                
                demanda_real = sum(v.cantidad for v in ventas_reales)
                # ✅ USAR CAMPO CORRECTO
                error = abs(pred.cantidad_predicha - demanda_real)
                errores.append(error)
            
            if errores:
                if metrica == 'mae':
                    resultado = np.mean(errores)
                    metrica_nombre = 'Error Absoluto Medio'
                elif metrica == 'rmse':
                    resultado = np.sqrt(np.mean([e**2 for e in errores]))
                    metrica_nombre = 'Error Cuadrático Medio'
                else:  # r2
                    # ✅ USAR CAMPO CORRECTO
                    resultado = max(0, 1 - (np.var(errores) / np.var([p.cantidad_predicha for p in predicciones])))
                    metrica_nombre = 'Coeficiente de Determinación'
                
                flash(f'{metrica_nombre}: {resultado:.3f} (basado en {len(predicciones)} predicciones)', 'info')
            else:
                flash('No se pudieron calcular métricas con los datos disponibles', 'warning')
                
        except Exception as e:
            flash(f'Error evaluando resultados: {str(e)}', 'danger')
    
    return render_template('ml/evaluacion.html', form=form, title='Evaluación de Resultados')

@ml_bp.route('/resultados/evaluacion')
@login_required
@admin_required
def resultados_evaluacion():
    # Obtener estadísticas de evaluación
    total_predicciones = Prediccion.query.count()
    predicciones_recientes = Prediccion.query.filter(
        Prediccion.fecha_prediccion >= datetime.now() - timedelta(days=30)
    ).count()
    
    # Calcular precisión promedio
    predicciones_con_confianza = Prediccion.query.filter(
        Prediccion.confianza.isnot(None)
    ).all()
    
    precision_promedio = 0
    if predicciones_con_confianza:
        precision_promedio = np.mean([float(p.confianza) * 100 for p in predicciones_con_confianza])
    
    estadisticas = {
        'total_predicciones': total_predicciones,
        'predicciones_recientes': predicciones_recientes,
        'precision_promedio': round(precision_promedio, 1)
    }
    
    return render_template('ml/resultados_evaluacion.html', 
                          estadisticas=estadisticas,
                          title='Evaluación de Impacto del ML')

# ===== RUTAS API ADICIONALES =====

@ml_bp.route('/api/predicciones/<int:producto_id>')
@login_required
def api_predicciones_producto(producto_id):
    """API para obtener predicciones de un producto específico"""
    try:
        predicciones = Prediccion.query.filter_by(
            producto_id=producto_id
        ).order_by(Prediccion.fecha_prediccion.desc()).limit(10).all()
        
        return jsonify({
            'success': True,
            'predicciones': [pred.to_dict() for pred in predicciones]
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@ml_bp.route('/api/modelo/estado')
@login_required
@admin_required
def api_estado_modelo():
    """API para obtener el estado del modelo ML"""
    try:
        modelo_path = os.path.join('instance', 'ml_models', 'extra_trees_model.joblib')
        metadata_path = os.path.join('instance', 'ml_models', 'model_metadata.json')
        
        estado = {
            'modelo_entrenado': os.path.exists(modelo_path),
            'ultima_actualizacion': None,
            'metricas': None
        }
        
        if os.path.exists(modelo_path):
            estado['ultima_actualizacion'] = datetime.fromtimestamp(
                os.path.getmtime(modelo_path)
            ).isoformat()
        
        if os.path.exists(metadata_path):
            import json
            with open(metadata_path, 'r') as f:
                metadata = json.load(f)
                estado['metricas'] = metadata.get('metricas', {})
        
        return jsonify({
            'success': True,
            'estado': estado
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@ml_bp.route('/api/reentrenar', methods=['POST'])
@login_required
@admin_required
def api_reentrenar():
    """API para reentrenar el modelo automáticamente"""
    try:
        # Usar últimos 6 meses de datos
        fecha_fin = datetime.now()
        fecha_inicio = fecha_fin - timedelta(days=180)
        
        # Verificar datos suficientes
        total_ventas = Venta.query.filter(
            Venta.fecha_venta >= fecha_inicio,
            Venta.fecha_venta <= fecha_fin
        ).count()
        
        if total_ventas < 10:
            return jsonify({
                'success': False,
                'error': 'Datos insuficientes para reentrenamiento'
            }), 400
        
        return jsonify({
            'success': True,
            'mensaje': f'Modelo listo para reentrenamiento con {total_ventas} registros'
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500