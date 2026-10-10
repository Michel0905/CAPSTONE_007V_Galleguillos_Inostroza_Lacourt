import sqlite3
import uuid
import bcrypt
from datetime import datetime
from contextlib import contextmanager

DB_NAME = "ticki_ti.db"

# =============================================
# Conexión segura
# =============================================
@contextmanager
def get_connection():
    conn = sqlite3.connect(DB_NAME)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.row_factory = sqlite3.Row  # Permite acceder por nombre de columna
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

# =============================================
# Crear la base de datos desde el schema
# =============================================
def inicializar_base_datos():
    """Ejecuta el schema_ticki_ti.sql y crea todas las tablas + datos semilla"""
    with get_connection() as conn:
        with open("schema_ticki_ti.sql", "r", encoding="utf-8") as f:
            conn.executescript(f.read())
    print("✅ Base de datos inicializada correctamente")

# =============================================
# Funciones de Usuario (Técnicos)
# =============================================
def crear_tecnico(nombre_completo: str, correo: str, password: str) -> str | None:
    """Crea un nuevo técnico."""
    
    # Transformar siempre a minúsculas y quitar espacios ocultos
    correo = correo.lower().strip()
    
    id_tecnico = str(uuid.uuid4())
    hash_credenciales = bcrypt.hashpw(
        password.encode("utf-8"), 
        bcrypt.gensalt()
    ).decode("utf-8")

    try:
        with get_connection() as conn:
            conn.execute("""
                INSERT INTO usuario_tecnico 
                (id_tecnico, nombre_completo, correo_electronico, hash_credenciales)
                VALUES (?, ?, ?, ?)
            """, (id_tecnico, nombre_completo, correo, hash_credenciales))
        return id_tecnico
    except sqlite3.IntegrityError:
        return None

def validar_login(correo: str, password: str) -> dict | None:
    """Valida las credenciales."""
    
    # Transformar a minúsculas para que coincida sin importar cómo escriba el usuario
    correo = correo.lower().strip()
    
    with get_connection() as conn:
        cursor = conn.execute("""
            SELECT id_tecnico, nombre_completo, hash_credenciales, activo
            FROM usuario_tecnico
            WHERE correo_electronico = ?
        """, (correo,))
        row = cursor.fetchone()

        if row is None:
            return None

        if row["activo"] != 1:
            return None  # Usuario desactivado

        # Verificar contraseña
        if bcrypt.checkpw(password.encode("utf-8"), row["hash_credenciales"].encode("utf-8")):
            ahora = datetime.now().isoformat()
            conn.execute("""
                UPDATE usuario_tecnico 
                SET fecha_ultima_sesion = ? 
                WHERE id_tecnico = ?
            """, (ahora, row["id_tecnico"]))

            return {
                "id_tecnico": row["id_tecnico"],
                "nombre_completo": row["nombre_completo"],
                "correo": correo
            }
        else:
            return None

def listar_tecnicos():
    """Devuelve todos los técnicos (para administración)"""
    with get_connection() as conn:
        cursor = conn.execute("""
            SELECT id_tecnico, nombre_completo, correo_electronico, activo, 
                   fecha_creacion, fecha_ultima_sesion
            FROM usuario_tecnico
            ORDER BY nombre_completo
        """)
        return [dict(row) for row in cursor.fetchall()]

def desactivar_tecnico(correo: str) -> bool:
    """Cambia el estado del técnico a inactivo (Soft Delete)."""
    
    
    correo = correo.lower().strip()
    
    with get_connection() as conn:
        cursor = conn.execute("""
            UPDATE usuario_tecnico 
            SET activo = 0 
            WHERE correo_electronico = ?
        """, (correo,))
        return cursor.rowcount > 0

def modificar_nombre_tecnico(correo: str, nuevo_nombre: str) -> bool:
    """Actualiza el nombre completo de un técnico."""
    
    
    correo = correo.lower().strip()
    
    with get_connection() as conn:
        cursor = conn.execute("""
            UPDATE usuario_tecnico 
            SET nombre_completo = ? 
            WHERE correo_electronico = ?
        """, (nuevo_nombre, correo))
        return cursor.rowcount > 0

def actualizar_password(correo: str, nueva_password: str) -> bool:
    """Genera un nuevo hash encriptado y actualiza la contraseña."""
    
    
    correo = correo.lower().strip()
    
    nuevo_hash = bcrypt.hashpw(nueva_password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
    with get_connection() as conn:
        cursor = conn.execute("""
            UPDATE usuario_tecnico 
            SET hash_credenciales = ? 
            WHERE correo_electronico = ?
        """, (nuevo_hash, correo))
        return cursor.rowcount > 0


def obtener_organizaciones():
    """Devuelve las organizaciones activas. Si no hay ninguna, crea una de prueba."""
    with get_connection() as conn:
        cursor = conn.execute("SELECT id_organizacion, nombre_organizacion FROM organizacion_cliente WHERE activa = 1")
        orgs = [dict(row) for row in cursor.fetchall()]
        
        if not orgs: # Si la tabla está vacía, inyectamos un cliente semilla para el MVP
            id_org = str(uuid.uuid4())
            conn.execute("INSERT INTO organizacion_cliente (id_organizacion, nombre_organizacion, codigo_cliente) VALUES (?, ?, ?)", 
                         (id_org, "Netmetrix", "NMX-001"))
            return [{"id_organizacion": id_org, "nombre_organizacion": "Netmetrix"}]
        return orgs

def guardar_ticket_completo(id_tecnico, id_organizacion, asunto, ruta_imagen, texto_ocr, texto_limpio, area_ia, prio_ia, area_final, prio_final, fecha_local):
    """Guarda el ticket, la predicción de IA y la validación final del humano en las 3 tablas."""
    id_ticket = str(uuid.uuid4())
    id_procesamiento = str(uuid.uuid4())
    id_validacion = str(uuid.uuid4())
    
    with get_connection() as conn:
        row_area_ia = conn.execute("SELECT id_area FROM catalogo_area WHERE nombre_area = ?", (area_ia,)).fetchone()
        id_area_ia = row_area_ia["id_area"] if row_area_ia else 1
        
        id_prio_ia = 2 if "Urgente" in prio_ia else 3

        row_area_fin = conn.execute("SELECT id_area FROM catalogo_area WHERE nombre_area = ?", (area_final,)).fetchone()
        id_area_fin = row_area_fin["id_area"] if row_area_fin else 1

        row_prio_fin = conn.execute("SELECT id_prioridad FROM catalogo_prioridad WHERE nombre_prioridad = ?", (prio_final,)).fetchone()
        id_prio_fin = row_prio_fin["id_prioridad"] if row_prio_fin else 3
        
        acepto = 1 if (id_area_ia == id_area_fin and id_prio_ia == id_prio_fin) else 0
        motivo = None if acepto == 1 else "Ajuste manual del técnico"

        conn.execute("""
            INSERT INTO ticket_requerimiento 
            (id_ticket, asunto, id_tecnico, id_organizacion, ruta_imagen_original, fecha_ingreso, estado)
            VALUES (?, ?, ?, ?, ?, ?, 'PENDIENTE')
        """, (id_ticket, asunto, id_tecnico, id_organizacion, ruta_imagen, fecha_local))

        conn.execute("""
            INSERT INTO procesamiento_ia 
            (id_procesamiento, id_ticket, texto_ocr_crudo, texto_anonimizado, id_area_sugerida, id_prioridad_sugerida, fecha_procesamiento)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (id_procesamiento, id_ticket, texto_ocr, texto_limpio, id_area_ia, id_prio_ia, fecha_local))
        
        conn.execute("""
            INSERT INTO validacion_humana
            (id_validacion, id_ticket, id_tecnico_validador, acepto_sugerencia_ia, id_area_final, id_prioridad_final, motivo_modificacion, fecha_validacion)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (id_validacion, id_ticket, id_tecnico, acepto, id_area_fin, id_prio_fin, motivo, fecha_local))
        
    return id_ticket