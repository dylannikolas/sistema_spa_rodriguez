import docx
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
import os

doc_path = 'Laboratorio_Spa_Rodriguez_corregido_v2.docx'
doc = docx.Document(doc_path)
body = doc._body._body

# Locate paragraph 170 / 172
p_count = 0
cut_index = None
for i, child in enumerate(body):
    tag = child.tag.split('}')[-1]
    if tag == 'p':
        p_count += 1
        if p_count == 173: # paragraph index 172
            cut_index = i
            break

print(f"Cutting body elements starting at index {cut_index}...")
elements_to_remove = []
for i in range(cut_index, len(body)):
    tag = body[i].tag.split('}')[-1]
    if tag != 'sectPr':
        elements_to_remove.append(body[i])

for el in elements_to_remove:
    body.remove(el)

print(f"Body elements after removal: {len(body)}")

# Helper functions to add paragraphs with consistent formatting
def add_h1(text):
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(14)
    p.paragraph_format.space_after = Pt(6)
    p.paragraph_format.keep_with_next = True
    r = p.add_run(text)
    r.font.name = 'Times New Roman'
    r.font.size = Pt(14)
    r.bold = True
    return p

def add_h2(text):
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(12)
    p.paragraph_format.space_after = Pt(4)
    p.paragraph_format.keep_with_next = True
    r = p.add_run(text)
    r.font.name = 'Times New Roman'
    r.font.size = Pt(13)
    r.bold = True
    return p

def add_body_p(lead_text, body_text):
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    p.paragraph_format.space_before = Pt(0)
    p.paragraph_format.space_after = Pt(6)
    p.paragraph_format.line_spacing = 1.15
    if lead_text:
        r1 = p.add_run(lead_text + ' ')
        r1.font.name = 'Times New Roman'
        r1.font.size = Pt(12)
        r1.bold = True
    r2 = p.add_run(body_text)
    r2.font.name = 'Times New Roman'
    r2.font.size = Pt(12)
    return p

def add_image_block(img_filename, caption_text, width_inches=6.5):
    img_path = os.path.join('lab09_corrigido_imgs', img_filename)
    p_img = doc.add_paragraph()
    p_img.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_img.paragraph_format.space_before = Pt(6)
    p_img.paragraph_format.space_after = Pt(2)
    p_img.paragraph_format.keep_with_next = True
    run_img = p_img.add_run()
    run_img.add_picture(img_path, width=Inches(width_inches))
    
    p_cap = doc.add_paragraph()
    p_cap.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_cap.paragraph_format.space_before = Pt(0)
    p_cap.paragraph_format.space_after = Pt(8)
    r_cap = p_cap.add_run(caption_text)
    r_cap.font.name = 'Times New Roman'
    r_cap.font.size = Pt(10)
    r_cap.italic = True
    return p_img, p_cap

# 1. Title of section 2.7
add_h1("2.7 Consultas SQL y Comprobación de las Reglas de Negocio")

# Introduction
add_body_p("", "El objetivo de esta sección es demostrar que la base de datos implementada para el Salón Spa Rodríguez no solamente almacena información correctamente, sino que permite responder preguntas relevantes para la administración del negocio y verificar el cumplimiento de las reglas de negocio establecidas. Siguiendo el modelo pedagógico propuesto para la evaluación funcional, se presentan tres consultas estratégicas formuladas sobre el esquema relacional en MySQL 8.0, vinculadas directamente con sus respectivas reglas de negocio (RN), el código SQL ejecutado, la evidencia gráfica del resultado y su interpretación analítica.")

# --- 2.7.1 Consulta 1 ---
add_h2("2.7.1 Consulta 1. Servicios más solicitados")
add_body_p("RN relacionadas:", "RN1, RN2 y RN5.")
add_body_p("Descripción de la regla:", "Esta consulta permite identificar cuáles son los servicios que presentan mayor demanda dentro del Salón Spa Rodríguez. Para ello relaciona los servicios registrados con las citas y con el estado final de cada reserva. De esta manera, no solo se contabiliza cuántas veces fue solicitado cada servicio, sino también cuántas de esas solicitudes terminaron en atención efectiva o en cancelación. La consulta se vincula con las reglas de negocio RN1, RN2 y RN5, pues toma en cuenta la correcta asociación entre citas, servicios y estados válidos del proceso de atención.")
add_body_p("Código SQL:", "La siguiente imagen presenta el código SQL empleado para formular la consulta en MySQL 8.0.")
add_image_block("figura15_sql_c1.png", "Figura 15. Código SQL de la consulta C1 (servicios más solicitados).", width_inches=6.4)
add_body_p("Resultado:", "La siguiente imagen muestra el resultado documentado de la consulta ejecutada en MySQL 8.0.42.")
add_image_block("tabla6_c1.png", "Tabla 6. Resultado de la consulta C1", width_inches=6.4)
add_body_p("Análisis:", "Los resultados muestran que Limpieza facial profunda, Masaje descontracturante, Masaje relajante y Pedicura spa son los servicios más solicitados, con dos registros cada uno. Esto evidencia que la demanda del negocio se distribuye entre varios servicios y no se concentra en una sola atención. En términos administrativos, esta información es útil para planificar horarios, asignar personal y prever insumos para los tratamientos que tienen mayor recurrencia.")

# --- 2.7.2 Consulta 2 ---
add_h2("2.7.2 Consulta 2. Estado general de las citas")
add_body_p("RN relacionadas:", "RN1 y RN5.")
add_body_p("Descripción de la regla:", "Esta consulta tiene como objetivo determinar cuántas citas se encuentran en cada estado del flujo de atención del spa. Para ello utiliza el catálogo de estados y lo relaciona con los registros de citas, permitiendo obtener tanto la cantidad como el porcentaje que representa cada estado sobre el total de reservas. La consulta se relaciona con las reglas RN1 y RN5, dado que depende de la existencia de citas registradas correctamente y de la asignación de un estado válido para su seguimiento.")
add_body_p("Código SQL:", "La siguiente imagen presenta el código SQL empleado para formular la consulta en MySQL 8.0.")
add_image_block("figura16_sql_c2.png", "Figura 16. Código SQL de la consulta C2 (estado general de las citas).", width_inches=6.4)
add_body_p("Resultado:", "La siguiente imagen muestra el resultado documentado de la consulta ejecutada en MySQL 8.0.42.")
add_image_block("tabla7_c2.png", "Tabla 7. Resultado de la consulta C2", width_inches=6.4)
add_body_p("Análisis:", "El resultado indica que el 40 % de las citas ya fueron atendidas, el 30 % permanece pendiente, el 20 % está confirmado y el 10 % fue cancelado. Esta distribución permite observar que todavía existe un conjunto importante de reservas por gestionar, especialmente las pendientes, que requieren confirmación o seguimiento antes de la fecha programada. Por ello, la consulta resulta útil para controlar el estado operativo del servicio y mejorar la organización del trabajo diario.")

# --- 2.7.3 Consulta 3 ---
add_h2("2.7.3 Consulta 3. Productos con menor stock")
add_body_p("RN relacionadas:", "RN8, RN9 y RN10.")
add_body_p("Descripción de la regla:", "Esta consulta permite identificar los productos del inventario que registran las menores existencias. Además de mostrar el stock disponible, incorpora el almacén al que pertenecen, el responsable asociado y la cantidad de servicios que utilizan cada producto. La consulta se relaciona con las reglas RN8, RN9 y RN10 porque apoya el control del inventario, la supervisión del abastecimiento y la prevención de quiebres de stock que podrían afectar tanto la prestación de servicios como la venta directa de productos.")
add_body_p("Código SQL:", "La siguiente imagen presenta el código SQL empleado para formular la consulta en MySQL 8.0.")
add_image_block("figura17_sql_c3.png", "Figura 17. Código SQL de la consulta C3 (productos con menor stock).", width_inches=6.4)
add_body_p("Resultado:", "La siguiente imagen muestra el resultado documentado de la consulta ejecutada en MySQL 8.0.42.")
add_image_block("tabla8_c3.png", "Tabla 8. Resultado de la consulta C3", width_inches=6.4)
add_body_p("Análisis:", "Los productos con menor existencia son Cera depilatoria tibia, Aceite de almendras para masaje, Exfoliante corporal de café, Mascarilla de arcilla verde y Aceite esencial de lavanda. Todos ellos se encuentran por debajo del stock promedio de 55,8 unidades, por lo que constituyen los principales candidatos para reposición. En consecuencia, la consulta proporciona una herramienta concreta para el control preventivo del inventario y para la toma de decisiones relacionadas con compras y abastecimiento.")

# --- 2.7.4 Conclusión general ---
add_h2("2.7.4 Conclusión general")
add_body_p("", "La reorganización de esta sección en torno a una estructura uniforme por consulta mejora la claridad del informe y responde de manera directa a la observación realizada por el docente en la pizarra. Asimismo, el uso de imágenes para el código SQL y para los resultados facilita la presentación visual de la información y mantiene la coherencia entre el análisis de las reglas de negocio y la evidencia obtenida mediante la base de datos.")

doc.save(doc_path)
print("Saved modified document to:", doc_path)
print("Final doc paragraphs:", len(doc.paragraphs), "tables:", len(doc.tables))
