# buscar_funcion_insercion.py
# Encontrar la función insertar_ventas_historicas_autopartes que causa el problema
import os

def buscar_funcion_insercion():
    """Buscar la función que inserta las ventas en BD"""
    print("🔍 BUSCANDO FUNCIÓN DE INSERCIÓN PROBLEMÁTICA")
    print("="*60)
    
    archivo_ml = 'app/controllers/ml_controller.py'
    
    if os.path.exists(archivo_ml):
        with open(archivo_ml, 'r', encoding='utf-8') as f:
            contenido = f.read()
            lineas = contenido.split('\n')
            
            # Buscar la función insertar_ventas_historicas_autopartes
            for i, linea in enumerate(lineas, 1):
                if 'def insertar_ventas_historicas_autopartes' in linea:
                    print(f"✅ FUNCIÓN PROBLEMÁTICA ENCONTRADA - Línea {i}")
                    print(f"   {linea.strip()}")
                    
                    print(f"\n📝 CÓDIGO COMPLETO DE LA FUNCIÓN:")
                    print("="*50)
                    
                    # Mostrar función completa
                    nivel_indent = len(linea) - len(linea.lstrip())
                    linea_inicio = i
                    
                    for j in range(i-1, min(len(lineas), i+100)):
                        linea_actual = lineas[j]
                        
                        # Mostrar línea con número
                        print(f"   {j+1:3d}: {linea_actual}")
                        
                        # Parar si encontramos otra función al mismo nivel
                        if (j > i and linea_actual.strip().startswith('def ') and 
                            len(linea_actual) - len(linea_actual.lstrip()) <= nivel_indent):
                            break
                            
                        # Parar si encontramos el final lógico de la función
                        if (j > i+20 and linea_actual.strip() == "" and 
                            j+1 < len(lineas) and 
                            (lineas[j+1].strip().startswith('def ') or 
                             lineas[j+1].strip().startswith('@') or
                             lineas[j+1].strip().startswith('class '))):
                            break
                    
                    print("\n" + "="*60)
                    break
            else:
                print("❌ Función insertar_ventas_historicas_autopartes NO encontrada")
                
                # Buscar funciones similares
                print("\n🔍 BUSCANDO FUNCIONES SIMILARES:")
                for i, linea in enumerate(lineas, 1):
                    if ('def ' in linea and 
                        ('insertar' in linea.lower() or 'insert' in linea.lower())):
                        print(f"   Línea {i}: {linea.strip()}")
                        
                        # Mostrar algunas líneas de contexto
                        for j in range(i, min(len(lineas), i+10)):
                            if lineas[j].strip() and not lineas[j].strip().startswith('#'):
                                print(f"      {j+1}: {lineas[j]}")
                            if lineas[j].strip().startswith('def ') and j > i:
                                break
                        print()
    else:
        print("❌ ml_controller.py no encontrado")
    
    # Verificar si existe en otros archivos
    print(f"\n🔍 BÚSQUEDA EN OTROS ARCHIVOS:")
    print("-" * 30)
    
    for root, dirs, files in os.walk('app'):
        for file in files:
            if file.endswith('.py'):
                filepath = os.path.join(root, file)
                try:
                    with open(filepath, 'r', encoding='utf-8') as f:
                        contenido = f.read()
                        if 'insertar_ventas_historicas' in contenido:
                            print(f"📄 {filepath} - Contiene función de inserción")
                            
                            # Mostrar líneas relevantes
                            lineas = contenido.split('\n')
                            for i, linea in enumerate(lineas, 1):
                                if 'insertar_ventas_historicas' in linea:
                                    print(f"   Línea {i}: {linea.strip()}")
                except:
                    pass

if __name__ == "__main__":
    buscar_funcion_insercion()