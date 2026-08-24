import streamlit as st
from PIL import Image, ImageEnhance, ImageFilter
import pytesseract
import io
import base64
import os
import json
# mod por claude 230826
# RUTA A TESSERACT INSTALADO EN TU PC
if os.path.exists(r'C:\Program Files\Tesseract-OCR\tesseract.exe'):
    # Si la ruta de Windows existe, la usamos
    pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
else:
    # En la nube (Linux), Tesseract se instala en el PATH automáticamente,
    # así que no necesitamos asignar una ruta manual.
    pass

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="OCR Inteligente Pro", layout="wide")

# --- FUNCIONES DE PROCESAMIENTO ---

def process_with_filters(image):
    """Aplica filtros de mejora y extrae texto."""
    img = image.convert('L')
    img = ImageEnhance.Contrast(img).enhance(1.8)
    img = ImageEnhance.Brightness(img).enhance(1.3)
    img = img.filter(ImageFilter.MedianFilter(size=3))
    img = img.point(lambda p: 255 if p > 180 else 0)
    img = img.resize((img.width * 2, img.height * 2), Image.Resampling.LANCZOS)

    config = r'--oem 3 --psm 6'
    text = pytesseract.image_to_string(img, lang='spa', config=config)
    return text, img

def process_simple(image):
    """Extrae texto sin filtros (solo escala de grises básica y redimensionado)."""
    img = image.convert('L').resize((image.width * 2, image.height * 2), Image.Resampling.LANCZOS)
    config = r'--oem 3 --psm 6'
    text = pytesseract.image_to_string(img, lang='spa', config=config)
    return text, img

def image_to_base64(image):
    buffered = io.BytesIO()
    image.save(buffered, format="PNG")
    return base64.b64encode(buffered.getvalue()).decode()

# --- INTERFAZ PRINCIPAL ---
st.title("🧾 Procesador OCR con Selección Automática")
st.markdown("La aplicación procesa cada imagen con y sin mejoras, eligiendo automáticamente el resultado con más contenido.")

uploaded_files = st.file_uploader("Sube tus imágenes", type=["png", "jpg", "jpeg"], accept_multiple_files=True)

if 'all_image_data' not in st.session_state:
    st.session_state.all_image_data = []

if uploaded_files:
    current_file_names = {f.name for f in uploaded_files}

    # Reprocesar solo si cambian los archivos
    if not st.session_state.all_image_data or {d['filename'] for d in st.session_state.all_image_data} != current_file_names:
        st.session_state.all_image_data = []
        uploaded_files.sort(key=lambda x: x.name.lower())

        with st.spinner("Analizando imágenes con doble método para optimizar resultados..."):
            for idx, uploaded_file in enumerate(uploaded_files, start=1):
                try:
                    image_bytes = uploaded_file.read()
                    original_image = Image.open(io.BytesIO(image_bytes)).convert("RGB")

                    # PROCESAR DE AMBAS FORMAS
                    text_enhanced, img_enhanced = process_with_filters(original_image)
                    text_simple, img_simple = process_simple(original_image)

                    # LOGICA DE SELECCIÓN: ¿Cuál obtuvo más texto?
                    if len(text_enhanced.strip()) >= len(text_simple.strip()):
                        final_text = text_enhanced
                        final_img = img_enhanced
                        was_enhanced = True
                    else:
                        final_text = text_simple
                        final_img = img_simple
                        was_enhanced = False

                    st.session_state.all_image_data.append({
                        "n": idx,
                        "filename": uploaded_file.name,
                        "original_image": original_image,
                        "current_text": final_text,
                        "current_processed_image_b64": image_to_base64(final_img),
                        "use_enhancement_for_this_row": was_enhanced
                    })
                except pytesseract.TesseractNotFoundError:
                    st.error(
                        "No se encontró Tesseract-OCR. Verificá la instalación (o el paquete "
                        "de idioma 'spa') antes de continuar."
                    )
                    st.stop()
                except Exception as e:
                    st.error(f"Error procesando '{uploaded_file.name}': {e}")

        st.success("¡Procesamiento inteligente completado!")

# --- FILTRADO ---
if st.session_state.all_image_data:
    all_n_numbers = [d['n'] for d in st.session_state.all_image_data]
    filter_options = ['Todas'] + all_n_numbers
    selected_n_numbers = st.multiselect("Filtrar por N°:", options=filter_options, default=['Todas'])

    # --- TABLA DE RESULTADOS ---
    st.subheader("📊 Resultados de OCR")

    # Filtrar datos
    if 'Todas' in selected_n_numbers:
        filtered_results = st.session_state.all_image_data
    else:
        filtered_results = [d for d in st.session_state.all_image_data if d['n'] in selected_n_numbers]

    # Encabezados
    cols_h = st.columns([0.5, 1.5, 3.5, 1.5, 1, 1])
    cols_h[0].write("**N°**")
    cols_h[1].write("**Archivo**")
    cols_h[2].write("**Texto Extraído**")
    cols_h[3].write("**Vista Previa**")
    cols_h[4].write("**Mejorado**")
    cols_h[5].write("**Estado**")
    st.divider()

    # Callback para cambios manuales
    def update_manual(idx):
        row = st.session_state.all_image_data[idx]
        new_state = not row['use_enhancement_for_this_row']

        if new_state:
            t, img = process_with_filters(row['original_image'])
        else:
            t, img = process_simple(row['original_image'])

        st.session_state.all_image_data[idx].update({
            "current_text": t,
            "current_processed_image_b64": image_to_base64(img),
            "use_enhancement_for_this_row": new_state
        })

    for res in filtered_results:
        idx_real = res['n'] - 1
        c = st.columns([0.5, 1.5, 3.5, 1.5, 1, 1])

        c[0].write(res['n'])
        c[1].write(res['filename'])
        c[2].write(res['current_text'])
        c[3].image(f"data:image/png;base64,{res['current_processed_image_b64']}", use_container_width=True)

        # Checkbox manual
        c[4].checkbox(" ", value=res['use_enhancement_for_this_row'],
                     key=f"chk_{idx_real}",
                     on_change=update_manual, args=(idx_real,))

        # Etiqueta de estado
        estado = "✨ Auto-Mejora" if res['use_enhancement_for_this_row'] else "⚡ Simple"
        c[5].info(estado)
        st.divider()

    # --- SECCIÓN DE EXPORTACIÓN ---
    st.subheader("📋 Copiar resultados en tabla")

    # Construir el texto de la tabla para copiar, usando solo los resultados FILTRADOS actualmente visibles.
    table_text_filtered = "N°\tArchivo\tTexto extraído\n"
    for r in filtered_results:  # Usar la lista de resultados ya filtrados.
        # Reemplazar saltos de línea con espacios para que el texto sea una sola línea en la celda de Excel.
        texto_plano = r['current_text'].replace('\n', ' ').strip()
        table_text_filtered += f"{r['n']}\t{r['filename']}\t{texto_plano}\n"

    # Mostrar un área de texto con el contenido de la tabla, que el usuario puede copiar manualmente.
    st.text_area("Tabla para copiar y pegar en Excel", table_text_filtered, height=300)

    # Botón para copiar automáticamente el texto de la tabla al portapapeles.
    # Usamos json.dumps para escapar el texto de forma segura como literal de JS
    # (evita romper el script si el OCR trae backticks, comillas, ${...}, </script>, etc.)
    texto_js_seguro = json.dumps(table_text_filtered)

    copy_button_js = f"""
    <script>
    function copyToClipboard(text) {{
        navigator.clipboard.writeText(text).then(function() {{
            console.log('Texto copiado al portapapeles exitosamente.');
        }}, function(err) {{
            console.error('No se pudo copiar el texto usando navigator.clipboard: ', err);
            var textArea = document.createElement("textarea");
            textArea.value = text;
            textArea.style.position = "fixed";
            textArea.style.opacity = "0";
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
    <button onclick="copyToClipboard({texto_js_seguro})"
            style="padding:10px 20px; font-size:16px; border-radius: 8px; background-color: #4CAF50; color: white; border: none; cursor: pointer; transition: background-color 0.3s ease;">
        📋 Copiar tabla al portapapeles
    </button>
    """
    st.markdown(copy_button_js, unsafe_allow_html=True)
