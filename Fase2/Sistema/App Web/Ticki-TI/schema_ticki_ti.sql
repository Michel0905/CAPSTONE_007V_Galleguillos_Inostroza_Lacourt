-- =============================================
-- Activar Foreign Keys (OBLIGATORIO en SQLite)
-- =============================================
PRAGMA foreign_keys = ON;

-- =============================================
-- 1. Tablas maestras y catálogos
-- =============================================

-- 1.1 Usuario_Tecnico
CREATE TABLE IF NOT EXISTS usuario_tecnico (
    id_tecnico          TEXT PRIMARY KEY,                     -- UUID como TEXT
    nombre_completo     TEXT NOT NULL,
    correo_electronico  TEXT NOT NULL UNIQUE,
    hash_credenciales   TEXT NOT NULL,
    activo              INTEGER NOT NULL DEFAULT 1,            -- 1 = TRUE, 0 = FALSE
    fecha_creacion      TEXT NOT NULL DEFAULT (datetime('now')),
    fecha_ultima_sesion TEXT
);

-- 1.2 Organizacion_Cliente
CREATE TABLE IF NOT EXISTS organizacion_cliente (
    id_organizacion     TEXT PRIMARY KEY,
    nombre_organizacion TEXT NOT NULL UNIQUE,
    codigo_cliente      TEXT UNIQUE,
    activa              INTEGER NOT NULL DEFAULT 1,
    fecha_alta          TEXT NOT NULL DEFAULT (date('now'))
);

-- 1.3 Catalogo_Area
CREATE TABLE IF NOT EXISTS catalogo_area (
    id_area             INTEGER PRIMARY KEY AUTOINCREMENT,
    codigo_area         TEXT NOT NULL UNIQUE,
    nombre_area         TEXT NOT NULL,
    descripcion         TEXT,
    activa              INTEGER NOT NULL DEFAULT 1
);

-- 1.4 Catalogo_Prioridad
CREATE TABLE IF NOT EXISTS catalogo_prioridad (
    id_prioridad        INTEGER PRIMARY KEY AUTOINCREMENT,
    codigo_prioridad    TEXT NOT NULL UNIQUE,
    nombre_prioridad    TEXT NOT NULL,
    nivel_numerico      INTEGER NOT NULL UNIQUE,
    sla_horas           INTEGER
);

-- =============================================
-- 2. Ticket_Requerimiento (núcleo)
-- =============================================
CREATE TABLE IF NOT EXISTS ticket_requerimiento (
    id_ticket               TEXT PRIMARY KEY,
    id_referencia_externa   TEXT UNIQUE,
    asunto                  TEXT NOT NULL,
    id_tecnico              TEXT NOT NULL,
    id_organizacion         TEXT NOT NULL,
    reportante_original     TEXT,
    ruta_imagen_original    TEXT NOT NULL,
    fecha_ingreso           TEXT NOT NULL DEFAULT (datetime('now')),
    fecha_resolucion        TEXT,
    estado                  TEXT NOT NULL DEFAULT 'PENDIENTE'
                            CHECK (estado IN ('PENDIENTE', 'VALIDADO', 'EXPORTADO', 'ANULADO')),
    observaciones_tecnico   TEXT,

    FOREIGN KEY (id_tecnico) REFERENCES usuario_tecnico(id_tecnico) ON DELETE RESTRICT,
    FOREIGN KEY (id_organizacion) REFERENCES organizacion_cliente(id_organizacion) ON DELETE RESTRICT
);

-- =============================================
-- 3. Procesamiento_IA (relación 1:1)
-- =============================================
CREATE TABLE IF NOT EXISTS procesamiento_ia (
    id_procesamiento        TEXT PRIMARY KEY,
    id_ticket               TEXT NOT NULL UNIQUE,              -- UNIQUE → 1:1
    texto_ocr_crudo         TEXT NOT NULL,
    texto_anonimizado       TEXT NOT NULL,
    id_area_sugerida        INTEGER NOT NULL,
    id_prioridad_sugerida  INTEGER NOT NULL,
    confianza_area          REAL,
    confianza_prioridad     REAL,
    modelo_version          TEXT,
    fecha_procesamiento     TEXT NOT NULL DEFAULT (datetime('now')),

    FOREIGN KEY (id_ticket) REFERENCES ticket_requerimiento(id_ticket) ON DELETE CASCADE,
    FOREIGN KEY (id_area_sugerida) REFERENCES catalogo_area(id_area) ON DELETE RESTRICT,
    FOREIGN KEY (id_prioridad_sugerida) REFERENCES catalogo_prioridad(id_prioridad) ON DELETE RESTRICT
);

-- =============================================
-- 4. Validacion_Humana (relación 1:1)
-- =============================================
CREATE TABLE IF NOT EXISTS validacion_humana (
    id_validacion           TEXT PRIMARY KEY,
    id_ticket               TEXT NOT NULL UNIQUE,              -- UNIQUE → 1:1
    id_tecnico_validador    TEXT NOT NULL,
    acepto_sugerencia_ia    INTEGER NOT NULL,                  -- 1 = TRUE, 0 = FALSE
    id_area_final           INTEGER NOT NULL,
    id_prioridad_final      INTEGER NOT NULL,
    motivo_modificacion     TEXT,
    fecha_validacion        TEXT NOT NULL DEFAULT (datetime('now')),
    tiempo_revision_segundos INTEGER,

    FOREIGN KEY (id_ticket) REFERENCES ticket_requerimiento(id_ticket) ON DELETE CASCADE,
    FOREIGN KEY (id_tecnico_validador) REFERENCES usuario_tecnico(id_tecnico) ON DELETE RESTRICT,
    FOREIGN KEY (id_area_final) REFERENCES catalogo_area(id_area) ON DELETE RESTRICT,
    FOREIGN KEY (id_prioridad_final) REFERENCES catalogo_prioridad(id_prioridad) ON DELETE RESTRICT,

    -- Regla de negocio
    CHECK (
        (acepto_sugerencia_ia = 1 AND motivo_modificacion IS NULL) OR
        (acepto_sugerencia_ia = 0 AND motivo_modificacion IS NOT NULL)
    )
);

-- =============================================
-- 5. Índices recomendados
-- =============================================
CREATE INDEX IF NOT EXISTS idx_ticket_tecnico_fecha 
    ON ticket_requerimiento (id_tecnico, fecha_ingreso);

CREATE INDEX IF NOT EXISTS idx_ticket_organizacion_estado 
    ON ticket_requerimiento (id_organizacion, estado);

CREATE INDEX IF NOT EXISTS idx_procesamiento_area_prioridad 
    ON procesamiento_ia (id_area_sugerida, id_prioridad_sugerida);

CREATE INDEX IF NOT EXISTS idx_validacion_fecha_acepto 
    ON validacion_humana (fecha_validacion, acepto_sugerencia_ia);

-- =============================================
-- 6. Datos semilla (catálogos)
-- =============================================

INSERT OR IGNORE INTO catalogo_area (codigo_area, nombre_area, descripcion) VALUES
('DEV', 'DevOps', ''),
('GSN', 'Gerencia de Seguridad y Networking', ''),
('PV',  'Post Venta', ''),
('SO',  'Soporte Observabilidad', ''),
('SPS', 'Soporte Plataformas y Soluciones', '');

INSERT OR IGNORE INTO catalogo_prioridad (codigo_prioridad, nombre_prioridad, nivel_numerico, sla_horas) VALUES
('CRITICA', 'Crítica', 1, 4),
('ALTA',    'Alta',    2, 8),
('MEDIA',   'Media',   3, 24),
('BAJA',    'Baja',    4, 72);