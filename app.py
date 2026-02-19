import streamlit as st
from PIL import Image, ImageEnhance, ImageFilter, ImageOps
import pytesseract
import io
import base64
import os

# RUTA A TESSERACT INSTALADO EN TU PC
# IMPORTANTE: Asegúrate de que esta ruta sea correcta para tu sistema
# En entornos de despliegue (ej. Docker, servicios cloud), esta configuración es diferente.
if os.path.exists(r'C:\Program Files\Tesseract-OCR\tesseract.exe'):
    pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'


# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="Detector de Texto e Imágenes", layout="wide")

# --- FUNCIONES DE PROCESAMIENTO DE IMAGEN Y OCR ---

def preprocess_image(image, use_enhancement_local=True):
    """
    Preprocesa una imagen para optimizarla para el OCR.
    Convierte a escala de grises, aplica mejoras de contraste/brillo y umbral, y redimensiona.
    """
    # Convertir la imagen a escala de grises. Esto es fundamental para el OCR.
    img = image.convert('L')
    if use_enhancement_local:
        # Aplicar mejoras de contraste y brillo para resaltar el texto.
        img = ImageEnhance.Contrast(img).enhance(1.8)
        img = ImageEnhance.Brightness(img).enhance(1.3)
        # Aplicar un filtro de mediana para reducir el ruido (puntos o imperfecciones).
        img = img.filter(ImageFilter.MedianFilter(size=3))
        # Aplicar un umbral binario "suave": convierte los píxeles en blanco puro (si son claros)
        # o negro puro (si son oscuros), lo que ayuda a la detección de caracteres.
        img = img.point(lambda p: 255 if p > 180 else 0)
    # Redimensionar la imagen para duplicar su tamaño. Tesseract a menudo funciona mejor
    # con imágenes más grandes, especialmente si el texto original es pequeño.
    # Se usa Image.Resampling.LANCZOS para una interpolación de alta calidad.
    img = img.resize((img.width * 2, img.height * 2), Image.Resampling.LANCZOS)
    return img

def extract_text(image, use_enhancement_local=True):
    """
    Extrae texto de una imagen utilizando Tesseract OCR.
    Intenta primero con el preprocesamiento seleccionado y luego con un fallback.
    """
    # Procesar la imagen con las mejoras decididas (global o individualmente).
    processed_img = preprocess_image(image, use_enhancement_local)
    
    # Configuración personalizada para Tesseract:
    # --oem 3: Especifica el uso del motor de OCR de Tesseract 4 o 5 (LSTM),
    #          que es más preciso para muchos casos.
    # --psm 6: Indica a Tesseract que asuma que la imagen contiene un solo
    #          bloque de texto uniforme. Útil para documentos.
    custom_config = r'--oem 3 --psm 6'
    
    # Realizar el OCR en la imagen preprocesada.
    text = pytesseract.image_to_string(processed_img, lang='spa', config=custom_config)

    # Lógica de "fallback": si el texto extraído es muy corto, podría significar
    # que el preprocesamiento con mejoras fue contraproducente para esa imagen.
    # En ese caso, se intenta extraer texto de una versión de la imagen
    # redimensionada pero sin las mejoras adicionales (solo escala de grises y redimensionado).
    # Solo se aplica el fallback si `use_enhancement_local` era True inicialmente,
    # ya que si no se usaron mejoras, no hay un "fallback" a una versión "menos mejorada".
    if len(text.strip()) < 10 and use_enhancement_local:
        # Crear una imagen de fallback: solo redimensionada y en escala de grises, sin otros filtros.
        fallback_img = image.convert('L').resize((image.width * 2, image.height * 2), Image.Resampling.LANCZOS)
        text_fallback = pytesseract.image_to_string(fallback_img, lang='spa', config=custom_config)
        
        # Comparar la longitud del texto. Si el fallback produce más texto, usarlo.
        if len(text_fallback.strip()) > len(text.strip()):
            return text_fallback, fallback_img
        else:
            return text, processed_img
    
    return text, processed_img

def image_to_base64(image):
    """
    Convierte un objeto de imagen PIL (Pillow) a una cadena Base64 con formato PNG.
    Esto es necesario para incrustar la imagen directamente en HTML (y por ende, en Streamlit).
    """
    buffered = io.BytesIO()
    # Guardar la imagen en el buffer como PNG.
    image.save(buffered, format="PNG")
    # Codificar el contenido del buffer a Base64 y luego decodificar a una cadena UTF-8.
    return base64.b64encode(buffered.getvalue()).decode()

# --- INTERFAZ PRINCIPAL DE STREAMLIT ---
st.title("🧾 Procesador de Imágenes con OCR")

# Controles para la carga de archivos y la configuración global de mejora.
uploaded_files = st.file_uploader("Sube una o más imágenes", type=["png", "jpg", "jpeg"], accept_multiple_files=True)
global_use_enhancement = st.checkbox(
    "Aplicar mejora automática a todas las imágenes por defecto al cargar",
    value=False,
    help="Si marcas esta opción, todas las imágenes se intentarán mejorar al cargarlas por primera vez."
)

# Inicializar o recuperar el estado de los datos de la imagen en la sesión de Streamlit.
# 'all_image_data' almacenará la imagen original, el texto actual, la imagen procesada actual,
# y el estado del checkbox de mejora individual para cada fila.
if 'all_image_data' not in st.session_state:
    st.session_state.all_image_data = []

# Lógica para procesar las imágenes cuando se suben nuevos archivos o cambia la configuración global.
if uploaded_files:
    # Verificamos si los archivos han cambiado o si el estado global de mejora ha cambiado
    # para evitar reprocesar todas las imágenes en cada interacción con la UI (ej. filtrar).
    current_file_names = {f.name for f in uploaded_files}
    
    # Condición para reprocesar todas las imágenes:
    # 1. No hay datos previos en la sesión.
    # 2. Los nombres de archivo subidos no coinciden con los ya procesados.
    # 3. El estado del checkbox global de mejora ha cambiado desde la última carga.
    if not st.session_state.all_image_data or \
       {d['filename'] for d in st.session_state.all_image_data} != current_file_names or \
       'global_enhancement_applied_on_load' not in st.session_state or \
       st.session_state.global_enhancement_applied_on_load != global_use_enhancement:

        st.session_state.all_image_data = [] # Limpiar los datos anteriores para los nuevos archivos.
        # Guardar el estado global de mejora con el que se cargaron las imágenes.
        st.session_state.global_enhancement_applied_on_load = global_use_enhancement

        # --- MODIFICACIÓN CLAVE: Ordenar archivos subidos por nombre antes de procesar ---
        # Ordena la lista de archivos subidos alfabéticamente por su nombre.
        # Esto asegura que el procesamiento y los números "N°" reflejen este orden.
        uploaded_files.sort(key=lambda x: x.name.lower())

        # Mostrar un indicador de carga mientras se procesan las imágenes.
        with st.spinner("Procesando imágenes... Esto puede tomar un momento."):
            for idx, uploaded_file in enumerate(uploaded_files, start=1):
                image_bytes = uploaded_file.read()
                original_image = Image.open(io.BytesIO(image_bytes)).convert("RGB")

                # Realizar el procesamiento inicial de OCR basándose en el checkbox global.
                initial_text, initial_processed_img = extract_text(original_image, global_use_enhancement)
                initial_img_b64 = image_to_base64(initial_processed_img)

                # Almacenar los datos de cada imagen en session_state:
                # - 'n': Número de la imagen (para el orden y el filtro).
                # - 'filename': Nombre original del archivo.
                # - 'original_image': La imagen PIL original (sin preprocesar), necesaria para reprocesar.
                # - 'current_text': El texto extraído actualmente (se actualiza si se cambia la mejora).
                # - 'current_processed_image_b64': La imagen procesada actual en Base64.
                # - 'use_enhancement_for_this_row': El estado del checkbox de mejora para esta fila.
                st.session_state.all_image_data.append({
                    "n": idx,
                    "filename": uploaded_file.name,
                    "original_image": original_image, 
                    "current_text": initial_text,
                    "current_processed_image_b64": initial_img_b64,
                    "use_enhancement_for_this_row": global_use_enhancement 
                })
        st.success("¡Imágenes procesadas!")

    # --- FILTRADO DE RESULTADOS ---
    # Obtener todos los números "N°" disponibles para el filtro.
    all_n_numbers = [d['n'] for d in st.session_state.all_image_data]
    
    # --- MODIFICACIÓN CLAVE: Opciones de filtro incluyendo "Todas" y default [] ---
    # Crear la lista de opciones para el multiselect, incluyendo "Todas".
    filter_options = ['Todas'] + all_n_numbers
    
    selected_n_numbers = st.multiselect(
        "Filtrar por N° de imagen:",
        options=filter_options,
        default=[], # Por defecto, ninguna imagen está seleccionada para mostrar.
        help="Selecciona los números de las imágenes que deseas ver en la tabla de resultados, o 'Todas' para verlas todas."
    )
    
    # Este checkbox `sort_by_filename` ya no es necesario aquí porque el ordenamiento
    # principal por nombre de archivo se realiza al inicio del procesamiento.

    # --- MOSTRAR RESULTADOS EN TABLA ---
    st.subheader("📊 Resultados de OCR")

    # Lógica para determinar qué resultados se mostrarán.
    if st.session_state.all_image_data and selected_n_numbers:
        if 'Todas' in selected_n_numbers:
            # Si "Todas" está seleccionado, mostrar todos los resultados.
            filtered_results = st.session_state.all_image_data
        else:
            # Si "Todas" no está seleccionado, filtrar por los números específicos elegidos.
            filtered_results = [d for d in st.session_state.all_image_data if d['n'] in selected_n_numbers]
        
        # El ordenamiento por nombre de archivo ya se hizo al cargar los archivos.
        # Por lo tanto, `filtered_results` ya estará en el orden deseado.

        # Definir el encabezado de la tabla con 5 columnas.
        cols_header = st.columns([0.5, 2, 4, 2, 1])
        cols_header[0].markdown("**N°**")
        cols_header[1].markdown("**Archivo**")
        cols_header[2].markdown("**Texto extraído**")
        cols_header[3].markdown("**Imagen Procesada**")
        cols_header[4].markdown("**Mejorar**") # Columna para el checkbox individual
        st.markdown("---") # Separador visual para la tabla.

        # Función de callback para actualizar una fila cuando se cambia el checkbox de mejora individual.
        def update_row_enhancement_callback(idx_to_update):
            # Obtener el estado actual del checkbox de mejora para esta fila.
            current_state = st.session_state.all_image_data[idx_to_update]['use_enhancement_for_this_row']
            # Invertir el estado (si era True, ahora es False, y viceversa).
            new_state = not current_state
            # Actualizar el estado en session_state para esta fila.
            st.session_state.all_image_data[idx_to_update]['use_enhancement_for_this_row'] = new_state

            # Reprocesar la imagen original de esta fila con el nuevo estado de mejora.
            original_img = st.session_state.all_image_data[idx_to_update]['original_image']
            text, processed_img = extract_text(original_img, new_state)
            img_b64 = image_to_base64(processed_img)

            # Actualizar el texto y la imagen procesada en session_state para esta fila.
            st.session_state.all_image_data[idx_to_update]['current_text'] = text
            st.session_state.all_image_data[idx_to_update]['current_processed_image_b64'] = img_b64

        # Iterar sobre los resultados filtrados y mostrarlos.
        # Es importante notar que 'filtered_results' ya está ordenado por nombre de archivo
        # debido a la modificación en la sección de carga.
        for result_data in filtered_results:
            # `original_data_index` es el índice real de esta imagen en la lista `st.session_state.all_image_data`.
            # Se usa `result_data['n'] - 1` porque `n` es 1-based y los índices son 0-based,
            # y el orden de `st.session_state.all_image_data` es el mismo que el orden de `n`.
            original_data_index = result_data['n'] - 1
            
            # Crear una clave única para cada checkbox dentro del bucle.
            checkbox_key = f"enhance_checkbox_{original_data_index}"

            cols = st.columns([0.5, 2, 4, 2, 1]) # Columnas para cada fila de resultados.

            # Mostrar el número y el nombre del archivo.
            cols[0].markdown(f"**{result_data['n']}**")
            cols[1].markdown(f"**Archivo:** {result_data['filename']}")

            # Checkbox para activar/desactivar la mejora individualmente para esta fila.
            with cols[4]: # Ubicar el checkbox en la quinta columna.
                st.checkbox(
                    " ", # Etiqueta vacía, ya que el encabezado de la columna ya lo explica.
                    value=st.session_state.all_image_data[original_data_index]['use_enhancement_for_this_row'],
                    key=checkbox_key, # Clave única.
                    help="Activa/desactiva las mejoras de imagen para esta fila en particular.",
                    # Cuando el checkbox cambia, se llama a la función de callback para actualizar la fila.
                    on_change=lambda r_idx=original_data_index: update_row_enhancement_callback(r_idx)
                )

            # Mostrar el texto extraído y la imagen procesada actual de esta fila.
            cols[2].markdown(f"**Texto extraído:**\n{result_data['current_text']}")
            cols[3].image(f"data:image/png;base64,{result_data['current_processed_image_b64']}", width=200)

            st.markdown("---") # Separador entre filas de resultados.

    else:
        # Mensajes informativos si no hay archivos subidos o si no hay selecciones en el filtro.
        if uploaded_files and not selected_n_numbers:
            st.info("No hay imágenes seleccionadas para mostrar. Por favor, selecciona una o más imágenes en el filtro superior.")
        elif not uploaded_files:
            st.info("Sube una o más imágenes (PNG, JPG, JPEG) para comenzar a procesar con OCR.")


    # --- SECCIÓN PARA COPIAR RESULTADOS EN TABLA ---
    st.subheader("📋 Copiar resultados en tabla")

    # Construir el texto de la tabla para copiar, usando solo los resultados FILTRADOS actualmente visibles.
    table_text_filtered = "N°\tArchivo\tTexto extraído\n"
    for r in filtered_results: # Usar la lista de resultados ya filtrados.
        # Reemplazar saltos de línea con espacios para que el texto sea una sola línea en la celda de Excel.
        texto_plano = r['current_text'].replace('\n', ' ').strip()
        table_text_filtered += f"{r['n']}\t{r['filename']}\t{texto_plano}\n"

    # Mostrar un área de texto con el contenido de la tabla, que el usuario puede copiar manualmente.
    st.text_area("Tabla para copiar y pegar en Excel", table_text_filtered, height=300)
    
    # Agregar un botón para copiar automáticamente el texto de la tabla al portapapeles.
    # Se usa JavaScript directamente con st.markdown y `unsafe_allow_html=True`.
    # `navigator.clipboard.writeText` es el método moderno, con un fallback a `document.execCommand('copy')`
    # para mayor compatibilidad, especialmente en entornos de iframe.
    copy_button_js = f"""
    <script>
    function copyToClipboard(text) {{
        navigator.clipboard.writeText(text).then(function() {{
            console.log('Texto copiado al portapapeles exitosamente.');
            // Podrías añadir un pequeño mensaje de feedback visual al usuario aquí,
            // por ejemplo, cambiando el texto del botón temporalmente.
        }}, function(err) {{
            console.error('No se pudo copiar el texto usando navigator.clipboard: ', err);
            // Fallback para navegadores o entornos que no soporten navigator.clipboard.writeText
            var textArea = document.createElement("textarea");
            textArea.value = text;
            textArea.style.position = "fixed"; // Evita que cause scroll
            textArea.style.opacity = "0"; // Lo hace invisible
            document.body.appendChild(textArea);
            textArea.focus();
            textArea.select();
            try {{
                var successful = document.execCommand('copy');
                var msg = successful ? 'exitoso' : 'fallido';
                console.log('Fallback: Comando de copiado ' + msg);
            }} catch (err) {{
                console.error('Fallback: Error al intentar copiar', err);
            }}
            document.body.removeChild(textArea);
        }});
    }}
    </script>
    <button onclick="copyToClipboard(`{table_text_filtered.replace('`', '\\`')}`)" 
            style="padding:10px 20px; font-size:16px; border-radius: 8px; background-color: #4CAF50; color: white; border: none; cursor: pointer; transition: background-color 0.3s ease;">
        📋 Copiar tabla al portapapeles
    </button>
    """
    st.markdown(copy_button_js, unsafe_allow_html=True)
