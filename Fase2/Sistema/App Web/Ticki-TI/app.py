import streamlit as st
import os
import pytz
import joblib
import easyocr
import re
import pandas as pd
import io
from datetime import datetime
from database import inicializar_base_datos, validar_login, obtener_organizaciones, guardar_ticket_completo

# 1. Configuraciones iniciales
st.set_page_config(page_title="Ticki-TI", layout="wide")
inicializar_base_datos()
tz_chile = pytz.timezone('America/Santiago')

def cargar_css(archivo_css):
    if os.path.exists(archivo_css):
        with open(archivo_css) as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)
cargar_css("styles.css")

if os.path.exists("logo.png"):
    st.logo("logo.png")

# 2. Carga de Modelos e IA en memoria caché
@st.cache_resource
def cargar_motor_ocr():
    return easyocr.Reader(['es'], gpu=False)

@st.cache_resource
def cargar_modelos_ia():
    mod_area = joblib.load("modelos/modelo_area.joblib")
    mod_prio = joblib.load("modelos/modelo_prioridad_binaria.joblib")
    le_area = joblib.load("modelos/le_area.joblib")
    le_prio = joblib.load("modelos/le_prioridad_bin.joblib")
    return mod_area, mod_prio, le_area, le_prio

def limpiar_texto(texto):
    texto = str(texto).lower()
    texto = re.sub(r'http\S+|www\.\S+', ' ', texto)
    texto = re.sub(r'\S+@\S+', ' ', texto)
    texto = re.sub(r'\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b', ' ', texto)
    texto = re.sub(r'[^a-záéíóúñü0-9\s]', ' ', texto)
    return re.sub(r'\s+', ' ', texto).strip()

reader = cargar_motor_ocr()
mod_area, mod_prio, le_area, le_prio = cargar_modelos_ia()

# 3. Manejo de Variables de Sesión
if 'usuario' not in st.session_state:
    st.session_state.usuario = None
if 'ml_results' not in st.session_state:
    st.session_state.ml_results = None
if 'mensaje_exito' not in st.session_state:
    st.session_state.mensaje_exito = None
if 'form_key' not in st.session_state:
    st.session_state.form_key = 0 
if 'tickets_sesion' not in st.session_state:
    st.session_state.tickets_sesion = [] 

# ==========================================
# VISTA 1: INICIO DE SESIÓN
# ==========================================
if st.session_state.usuario is None:
    col_izq, col_centro, col_der = st.columns([1, 2, 1])
    with col_centro:
        st.title("Ticki-TI - Netmetrix")
        st.subheader("Portal de Acceso")

        correo_ingresado = st.text_input("Correo electrónico")
        password_ingresada = st.text_input("Contraseña", type="password") 

        if st.button("Iniciar Sesión"):
            usuario_valido = validar_login(correo=correo_ingresado, password=password_ingresada)
            if usuario_valido:
                st.session_state.usuario = usuario_valido
                st.rerun()
            else:
                st.error("❌ Correo o contraseña incorrectos. Intenta de nuevo.")

# ==========================================
# VISTA 2: PANEL DE PROCESAMIENTO (LOGUEADO)
# ==========================================
else:
    # PANEL LATERAL: Exportación y Reloj 
    with st.sidebar:
        st.header("Gestión de Sesión")
        st.markdown(f"**Usuario:** {st.session_state.usuario['nombre_completo']}")
        
        # Reloj estático en la barra lateral
        st.markdown(f"<div style='color: #0e73b5; font-weight: bold; margin-top: 5px; margin-bottom: 15px;'>Fecha y Hora: {datetime.now(tz_chile).strftime('%Y-%m-%d %H:%M:%S')}</div>", unsafe_allow_html=True)
        
        st.markdown("---")
        
        if len(st.session_state.tickets_sesion) > 0:
            st.success(f"Tickets guardados en esta sesión: {len(st.session_state.tickets_sesion)}")
            
            df_tickets = pd.DataFrame(st.session_state.tickets_sesion)
            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                df_tickets.to_excel(writer, index=False, sheet_name='Tickets')
            
            st.download_button(
                label="📥 Descargar Excel de Sesión",
                data=buffer.getvalue(),
                file_name=f"Tickets_{st.session_state.usuario['nombre_completo'].replace(' ', '_')}_{datetime.now(tz_chile).strftime('%Y%m%d_%H%M%S')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
        else:
            st.info("No has guardado tickets en esta sesión aún.")
            
        st.markdown("---")
        if st.button("Cerrar Sesión"):
            st.session_state.usuario = None
            st.session_state.ml_results = None
            st.session_state.form_key = 0
            st.session_state.tickets_sesion = [] 
            st.rerun()

    # PANEL CENTRAL
    st.title("Procesamiento de Tickets")
    
    col_form, col_visor = st.columns([1, 1])
    
    with col_form:
        if st.session_state.mensaje_exito:
            st.success(st.session_state.mensaje_exito)
            st.session_state.mensaje_exito = None
            
        organizaciones = obtener_organizaciones()
        opciones_org = {org["nombre_organizacion"]: org["id_organizacion"] for org in organizaciones}
        
        org_seleccionada = st.selectbox("Selección de la Organización (Cliente)", options=list(opciones_org.keys()), key=f"org_{st.session_state.form_key}")
        asunto_ticket = st.text_input("Asunto / Título del Ticket (Obligatorio)", key=f"asunto_{st.session_state.form_key}")
        
        metodo_ingreso = st.radio("¿Cómo ingresarás el detalle del ticket?", options=["Texto manual", "Subir imagen"], horizontal=True, key=f"metodo_{st.session_state.form_key}")
        
        texto_manual = ""
        imagen_cargada = None
        
        if metodo_ingreso == "Texto manual":
            texto_manual = st.text_area("Cuerpo del correo o descripción del ticket:", key=f"texto_{st.session_state.form_key}")
        else:
            imagen_cargada = st.file_uploader("Sube la imagen del ticket (JPG/PNG)", type=['png', 'jpg', 'jpeg'], key=f"img_{st.session_state.form_key}")
        
        # ESTADO A: Aún no se ha procesado
        if st.session_state.ml_results is None:
            col_btn1, col_btn2 = st.columns([1, 1])
            with col_btn1:
                btn_procesar = st.button("Procesar Ticket (Analizar)")
            with col_btn2:
                btn_borrar = st.button("Borrar Todo")

            if btn_borrar:
                st.session_state.form_key += 1
                st.rerun()

            if btn_procesar:
                if asunto_ticket and (texto_manual or imagen_cargada):
                    texto_extraido = ""
                    ruta_imagen = "Ingreso manual (sin imagen)"
                    
                    if metodo_ingreso == "Subir imagen" and imagen_cargada:
                        if not os.path.exists("uploads"):
                            os.makedirs("uploads")
                        ruta_imagen = f"uploads/{imagen_cargada.name}"
                        with open(ruta_imagen, "wb") as f:
                            f.write(imagen_cargada.getbuffer())
                        
                        with st.spinner('Extrayendo texto de la imagen (OCR)...'):
                            resultados_ocr = reader.readtext(ruta_imagen, detail=0)
                            texto_extraido = " ".join(resultados_ocr)
                            
                    elif metodo_ingreso == "Texto manual" and texto_manual:
                        texto_extraido = texto_manual
                    
                    with st.spinner('Clasificando incidencia...'):
                        texto_limpio = limpiar_texto(texto_extraido)
                        
                        if len(texto_limpio) < 25:
                            st.error("⚠️ El texto es demasiado corto para clasificarlo con seguridad.")
                        else:
                            pred_area_num = mod_area.predict([texto_limpio])[0]
                            pred_prio_num = mod_prio.predict([texto_limpio])[0]
                            
                            area_final = le_area.inverse_transform([pred_area_num])[0]
                            prio_final = le_prio.inverse_transform([pred_prio_num])[0]
                            
                            st.session_state.ml_results = {
                                "ruta_imagen": ruta_imagen,
                                "texto_ocr": texto_extraido,
                                "texto_limpio": texto_limpio,
                                "area_ia": area_final,
                                "prio_ia": prio_final
                            }
                            st.rerun()
                else:
                    st.warning("⚠️ Debes ingresar un Asunto y proveer el contenido.")

        # ESTADO B: Ya se procesó
        else:
            st.info("💡 La IA ha clasificado el ticket. Valida o modifica las opciones antes de guardar.")
            datos_ia = st.session_state.ml_results
            
            st.markdown(f"**Área Sugerida por IA:** {datos_ia['area_ia']}")
            cat_areas = list(le_area.classes_)
            idx_area = cat_areas.index(datos_ia['area_ia']) if datos_ia['area_ia'] in cat_areas else 0
            area_final = st.selectbox("Confirmar Área Definitiva:", options=cat_areas, index=idx_area)
            
            st.markdown(f"**Prioridad Sugerida por IA:** {datos_ia['prio_ia']}")
            cat_prios = ["Crítica", "Alta", "Media", "Baja"]
            idx_prio = 1 if "Urgente" in datos_ia['prio_ia'] else 2 
            prio_final = st.selectbox("Confirmar Prioridad Definitiva:", options=cat_prios, index=idx_prio)
            
            col_btn1, col_btn2 = st.columns(2)
            with col_btn1:
                if st.button("Guardar Ticket Definitivo"):
                    fecha_local = datetime.now(tz_chile).isoformat()
                    id_org = opciones_org[org_seleccionada]
                    
                    id_ticket_nuevo = guardar_ticket_completo(
                        id_tecnico=st.session_state.usuario["id_tecnico"],
                        id_organizacion=id_org,
                        asunto=asunto_ticket,
                        ruta_imagen=datos_ia["ruta_imagen"],
                        texto_ocr=datos_ia["texto_ocr"],
                        texto_limpio=datos_ia["texto_limpio"],
                        area_ia=datos_ia["area_ia"],
                        prio_ia=datos_ia["prio_ia"],
                        area_final=area_final,
                        prio_final=prio_final,
                        fecha_local=fecha_local
                    )
                    
                    st.session_state.tickets_sesion.append({
                        "ID": id_ticket_nuevo,
                        "Asunto": asunto_ticket,
                        "Técnico Analista": st.session_state.usuario['nombre_completo'],
                        "Descripción": datos_ia["texto_ocr"],
                        "Prioridad": prio_final,
                        "Area": area_final,
                        "fecha y hora": fecha_local
                    })
                    
                    st.session_state.ml_results = None
                    st.session_state.form_key += 1 
                    st.session_state.mensaje_exito = "✅ Ticket validado y guardado correctamente."
                    st.rerun()
            with col_btn2:
                if st.button("Cancelar Análisis"):
                    st.session_state.ml_results = None
                    st.rerun()
                
    with col_visor:
        if st.session_state.ml_results and st.session_state.ml_results["ruta_imagen"] != "Ingreso manual (sin imagen)":
            st.image(st.session_state.ml_results["ruta_imagen"], caption="Documento Analizado", use_container_width=True)
        elif metodo_ingreso == "Subir imagen" and imagen_cargada:
            st.image(imagen_cargada, caption="Vista previa del documento", use_container_width=True)