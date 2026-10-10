from database import desactivar_tecnico, modificar_nombre_tecnico, actualizar_password

# Escribe aquí el correo del usuario que quieres modificar
correo_objetivo = "Correo@Objetivo" #Cambiar según corresponda

# EJEMPLO 1: Para cambiar el nombre (Borra el '#' al inicio de las dos líneas de abajo para activarlo)
#exito_nombre = modificar_nombre_tecnico(correo_objetivo, "nuevo nombre")
#print(f"Nombre modificado: {exito_nombre}")

# EJEMPLO 2: Para cambiar la contraseña (Borra el '#' de las dos líneas de abajo)
#exito_pass = actualizar_password(correo_objetivo, "nueva contraseña")
#print(f"Contraseña modificada: {exito_pass}")

# EJEMPLO 3: Para desactivar (eliminar acceso) al usuario (Borra el '#' de las dos líneas de abajo)
#exito_desactivar = desactivar_tecnico(correo_objetivo)
#print(f"Usuario desactivado: {exito_desactivar}")