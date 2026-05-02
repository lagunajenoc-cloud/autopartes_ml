from flask import Blueprint, render_template, jsonify, current_app
from flask_login import login_required
from datetime import datetime, timedelta
from werkzeug.routing import BuildError
import os

from app import db
from app.models.venta import Venta
from app.models.producto import Producto
from app.models.inventario import Inventario

dashboard_bp = Blueprint('dashboard', __name__, url_prefix='/dashboard')

@dashboard_bp.route('/')
@login_required
def index():
    try:
        print("🔍 Dashboard ejecutándose...")
        
        # ✅ VERIFICACIÓN DEFINITIVA DE ML EN PYTHON
        ml_disponible = False
        try:
            # 1. Verificar si el blueprint está registrado
            if 'ml' in current_app.blueprints:
                # 2. Intentar construir la URL internamente para confirmar que funciona
                with current_app.test_request_context():
                    current_app.url_map.build('ml.index')
                    ml_disponible = True
        except (BuildError, Exception) as e:
            print(f"⚠️ Módulo ML detectado como no funcional: {e}")
            ml_disponible = False

        # ✅ MÉTRICAS BÁSICAS CORREGIDAS
        total_ventas_count = Venta.query.count()
        suma_ventas = db.session.query(db.func.sum(Venta.precio_total)).scalar()
        suma_float = float(suma_ventas) if suma_ventas else 0.0
        
        promedio_ventas = db.session.query(db.func.avg(Venta.precio_total)).scalar()
        promedio_float = float(promedio_ventas) if promedio_ventas else 0.0
        
        total_productos = Producto.query.count()
        
        productos_stock_bajo = db.session.query(Inventario).filter(
            Inventario.stock_actual <= Inventario.stock_minimo
        ).count()
        
        productos_excedente = db.session.query(Inventario).filter(
            Inventario.stock_actual >= Inventario.stock_optimo
        ).count()
        
        estadisticas = {
            'total_ventas': total_ventas_count,
            'ventas_totales': suma_float,
            'venta_promedio': promedio_float,
            'total_productos': total_productos,
            'productos_stock_bajo': productos_stock_bajo,
            'productos_excedente': productos_excedente
        }
        
        ventas_categoria = db.session.query(
            Producto.categoria,
            db.func.sum(Venta.precio_total).label('monto_total')
        ).join(Venta, Producto.id == Venta.producto_id).group_by(
            Producto.categoria
        ).all()
        
        ventas_categoria_list = [
            {'categoria': v.categoria, 'monto_total': float(v.monto_total)}
            for v in ventas_categoria
        ]
        
        inventario_excedente_query = db.session.query(Producto, Inventario).join(
            Inventario, Producto.id == Inventario.producto_id
        ).filter(
            Inventario.stock_actual > Inventario.stock_optimo
        ).limit(10).all()
        
        inventario_excedente = []
        for producto, inventario in inventario_excedente_query:
            inventario_excedente.append({
                'codigo': producto.codigo,
                'categoria': producto.categoria,
                'excedente': inventario.stock_actual - inventario.stock_optimo,
                'precio_unitario': float(producto.precio_unitario)
            })
        
        fecha_limite = datetime.now() - timedelta(days=90)
        
        productos_baja_rotacion_query = db.session.query(
            Producto,
            db.func.coalesce(db.func.count(Venta.id), 0).label('total_ventas'),
            Inventario.stock_actual
        ).outerjoin(
            Venta, (Producto.id == Venta.producto_id) & (Venta.fecha_venta >= fecha_limite)
        ).outerjoin(
            Inventario, Producto.id == Inventario.producto_id
        ).group_by(
            Producto.id, Inventario.stock_actual
        ).having(
            db.func.count(Venta.id) < 5
        ).filter(
            Inventario.stock_actual > 10
        ).limit(10).all()
        
        productos_baja_rotacion = []
        for producto, total_ventas, stock_actual in productos_baja_rotacion_query:
            productos_baja_rotacion.append({
                'codigo': producto.codigo,
                'categoria': producto.categoria,
                'total_ventas': total_ventas,
                'stock_actual': stock_actual or 0
            })
        
        ultimas_ventas = Venta.query.order_by(Venta.fecha_venta.desc()).limit(5).all()
        
        modelo_path = os.path.join('instance', 'ml_models', 'extra_trees_model.joblib')
        modelo_entrenado = os.path.exists(modelo_path)
        
        print(f"✅ Estadísticas calculadas: {estadisticas}")
        print(f"🤖 ML Disponible: {ml_disponible}")
        
        return render_template(
            'dashboard/index.html',
            estadisticas=estadisticas,
            ventas_categoria=ventas_categoria_list,
            inventario_excedente=inventario_excedente,
            productos_baja_rotacion=productos_baja_rotacion,
            ultimas_ventas=ultimas_ventas,
            modelo_entrenado=modelo_entrenado,
            impacto_ml=None,
            datos_grafico_ventas={'fechas': [], 'totales': []},
            datos_grafico_predicciones=None,
            ml_disponible=ml_disponible,  # ✅ VARIABLE SEGURA PASADA AL TEMPLATE
            title='Dashboard'
        )
        
    except Exception as e:
        print(f"❌ ERROR EN DASHBOARD:")
        print(f"   Tipo: {type(e).__name__}")
        print(f"   Mensaje: {str(e)}")
        import traceback
        print(f"   Traceback: {traceback.format_exc()}")
        
        return f"<h1>Error en Dashboard</h1><p>{str(e)}</p><pre>{traceback.format_exc()}</pre>"

@dashboard_bp.route('/comparativo')
@login_required
def comparativo():
    return render_template(
        'dashboard/comparativo.html',
        resultados=[],
        ultimo_resultado=None,
        datos_inventario={'antes': 0, 'despues': 0, 'reduccion_porcentaje': 0},
        datos_ventas={'antes': 0, 'despues': 0, 'incremento_porcentaje': 0},
        title='Análisis Comparativo Pre/Post ML'
    )

# ===== RUTAS API PARA GRÁFICOS =====

@dashboard_bp.route('/api/ventas-por-dia')
@login_required
def api_ventas_por_dia():
    fecha_limite = datetime.now() - timedelta(days=30)
    
    try:
        ventas = db.session.query(
            db.func.date(Venta.fecha_venta).label('fecha'),
            db.func.sum(Venta.precio_total).label('total')
        ).filter(
            Venta.fecha_venta >= fecha_limite
        ).group_by(
            db.func.date(Venta.fecha_venta)
        ).order_by('fecha').all()
        
        datos = {
            'fechas': [venta.fecha.strftime('%Y-%m-%d') for venta in ventas],
            'totales': [float(venta.total) for venta in ventas]
        }
        
        return jsonify(datos)
        
    except Exception as e:
        print(f"❌ Error en API ventas por día: {e}")
        return jsonify({'fechas': [], 'totales': []})

@dashboard_bp.route('/api/ventas-por-categoria')
@login_required  
def api_ventas_por_categoria():
    try:
        ventas = db.session.query(
            Producto.categoria,
            db.func.sum(Venta.precio_total).label('total')
        ).join(Venta, Producto.id == Venta.producto_id).group_by(
            Producto.categoria
        ).all()
        
        datos = {
            'categorias': [venta.categoria for venta in ventas],
            'totales': [float(venta.total) for venta in ventas]
        }
        
        return jsonify(datos)
        
    except Exception as e:
        print(f"❌ Error en API ventas por categoría: {e}")
        return jsonify({'categorias': [], 'totales': []})