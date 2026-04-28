-- MIGRACIÓN PARA CREAR TABLAS DE COMPROBANTES
-- Ejecutar en PostgreSQL

-- 1. Primero agregar campos a tabla productos (para IGV)
ALTER TABLE productos ADD COLUMN IF NOT EXISTS incluye_igv BOOLEAN DEFAULT true;
ALTER TABLE productos ADD COLUMN IF NOT EXISTS precio_sin_igv NUMERIC(10,2);
ALTER TABLE productos ADD COLUMN IF NOT EXISTS precio_con_igv NUMERIC(10,2);

-- Actualizar productos existentes (asumir que precios incluyen IGV)
UPDATE productos SET 
    incluye_igv = true,
    precio_con_igv = precio_unitario,
    precio_sin_igv = precio_unitario / 1.18
WHERE precio_con_igv IS NULL;

-- 2. Crear tabla comprobantes
CREATE TABLE IF NOT EXISTS comprobantes (
    id SERIAL PRIMARY KEY,
    tipo VARCHAR(20) NOT NULL CHECK (tipo IN ('proforma', 'factura', 'boleta')),
    numero VARCHAR(50) UNIQUE NOT NULL,
    serie VARCHAR(10) DEFAULT '001',
    
    -- Datos del cliente
    cliente_nombre VARCHAR(200) NOT NULL,
    cliente_documento VARCHAR(20),
    cliente_direccion TEXT,
    cliente_email VARCHAR(100),
    cliente_telefono VARCHAR(20),
    
    -- Fechas
    fecha_emision TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    fecha_vencimiento TIMESTAMP,
    
    -- Totales
    subtotal NUMERIC(10,2) DEFAULT 0,
    igv_porcentaje NUMERIC(5,2) DEFAULT 18,
    igv_monto NUMERIC(10,2) DEFAULT 0,
    total NUMERIC(10,2) DEFAULT 0,
    
    -- Estado y seguimiento
    estado VARCHAR(20) DEFAULT 'pendiente' CHECK (estado IN ('pendiente', 'aprobado', 'facturado', 'anulado')),
    proforma_origen_id INTEGER REFERENCES comprobantes(id),
    comprobante_destino_id INTEGER REFERENCES comprobantes(id),
    
    -- Usuario que crea el comprobante
    usuario_id INTEGER NOT NULL REFERENCES usuarios(id),
    
    -- Observaciones
    observaciones TEXT,
    condiciones_pago TEXT DEFAULT 'Contado',
    
    -- Campos SUNAT (para implementación futura)
    enviado_sunat BOOLEAN DEFAULT false,
    fecha_envio_sunat TIMESTAMP,
    codigo_sunat VARCHAR(10),
    hash_cpe VARCHAR(100),
    numero_cdr VARCHAR(50),
    observaciones_sunat TEXT,
    
    -- Timestamps
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 3. Crear tabla detalles de comprobantes
CREATE TABLE IF NOT EXISTS comprobante_detalles (
    id SERIAL PRIMARY KEY,
    comprobante_id INTEGER NOT NULL REFERENCES comprobantes(id) ON DELETE CASCADE,
    producto_id INTEGER NOT NULL REFERENCES productos(id),
    
    cantidad INTEGER NOT NULL CHECK (cantidad > 0),
    precio_unitario NUMERIC(10,2) NOT NULL,
    precio_original NUMERIC(10,2), -- Precio del inventario
    descuento_porcentaje NUMERIC(5,2) DEFAULT 0,
    subtotal NUMERIC(10,2) NOT NULL,
    
    -- Timestamps
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 4. Agregar campo comprobante_id a tabla ventas (opcional, para trazabilidad)
ALTER TABLE ventas ADD COLUMN IF NOT EXISTS comprobante_id INTEGER REFERENCES comprobantes(id);

-- 5. Crear índices para optimizar consultas
CREATE INDEX IF NOT EXISTS idx_comprobantes_tipo ON comprobantes(tipo);
CREATE INDEX IF NOT EXISTS idx_comprobantes_numero ON comprobantes(numero);
CREATE INDEX IF NOT EXISTS idx_comprobantes_fecha ON comprobantes(fecha_emision);
CREATE INDEX IF NOT EXISTS idx_comprobantes_cliente ON comprobantes(cliente_documento);
CREATE INDEX IF NOT EXISTS idx_comprobante_detalles_comprobante ON comprobante_detalles(comprobante_id);
CREATE INDEX IF NOT EXISTS idx_comprobante_detalles_producto ON comprobante_detalles(producto_id);

-- 6. Crear secuencias para numeración automática
CREATE SEQUENCE IF NOT EXISTS seq_proforma START 1;
CREATE SEQUENCE IF NOT EXISTS seq_factura START 1;
CREATE SEQUENCE IF NOT EXISTS seq_boleta START 1;

-- 7. Función para generar número automático
CREATE OR REPLACE FUNCTION generar_numero_comprobante(tipo_doc VARCHAR, serie_doc VARCHAR DEFAULT '001')
RETURNS VARCHAR AS $$
DECLARE
    prefijo VARCHAR(3);
    siguiente_numero INTEGER;
    numero_final VARCHAR(50);
BEGIN
    -- Determinar prefijo según tipo
    CASE tipo_doc
        WHEN 'proforma' THEN prefijo := 'PRF';
        WHEN 'factura' THEN prefijo := 'FAC';
        WHEN 'boleta' THEN prefijo := 'BOL';
        ELSE prefijo := 'DOC';
    END CASE;
    
    -- Obtener siguiente número
    SELECT COALESCE(MAX(CAST(SPLIT_PART(numero, '-', 3) AS INTEGER)), 0) + 1
    INTO siguiente_numero
    FROM comprobantes 
    WHERE tipo = tipo_doc AND numero LIKE serie_doc || '-' || prefijo || '-%';
    
    -- Construir número final
    numero_final := serie_doc || '-' || prefijo || '-' || LPAD(siguiente_numero::TEXT, 8, '0');
    
    RETURN numero_final;
END;
$$ LANGUAGE plpgsql;

-- 8. Trigger para actualizar updated_at
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER update_comprobantes_updated_at 
    BEFORE UPDATE ON comprobantes 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- 9. Datos iniciales de ejemplo (opcional)
INSERT INTO comprobantes (tipo, numero, cliente_nombre, cliente_documento, subtotal, igv_monto, total, usuario_id, estado)
VALUES 
    ('proforma', '001-PRF-00000001', 'Cliente Ejemplo', '12345678', 100.00, 18.00, 118.00, 1, 'pendiente')
ON CONFLICT (numero) DO NOTHING;