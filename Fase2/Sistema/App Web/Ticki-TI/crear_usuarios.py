from database import inicializar_base_datos, crear_tecnico


# leyendo archivo schema_ticki_ti.sql
print("Creando la base de datos y las tablas...")
inicializar_base_datos()


print("Creando técnico de prueba...")


id_nuevo = crear_tecnico(
    nombre_completo="Carlos Mendoza",
    correo="c.mendoza@ticki-nmx.cl",
    password="pass1234"
)

if id_nuevo:
    print(f"¡Éxito! El usuario fue creado. Su ID secreto es: {id_nuevo}")
else:
    print("El usuario ya existe en la base de datos o hubo un error.")