from datetime import datetime
import pandas as pd
import geopandas as gpd
from shapely import wkb
import contextily as ctx
import matplotlib.pyplot as plt
import logging

from docxtpl import DocxTemplate
import docxtpl
from docx.shared import Mm

import collections
import os

import sys
sys.path.append('_amigocloud')
from amigocloud import AmigoCloud

##==================================================================================
##==================================================================================
from config import API_TOKEN_AMIGOCLOUD_QUEMA, PATH_FOTOS

from config import PROYECTO_ID
from config import BUSCAR_REG_NUEVOS
from config import CARGAR_LOTES_QUEMA
from config import CALC_AREA_LOTES
from config import CALC_TOTAL_INSP

from config import PATH_TEMPLATE_INFORME
from config import PATH_INFORMES
from config import PATH_PLANOS
from config import PATH_FOTOS
from config import PATH_FIRMAS

##==================================================================================
##==================================================================================

logging.basicConfig(
    level=logging.INFO, 
    format="%(asctime)s [%(levelname)s] %(message)s",
)

amigocloud = AmigoCloud(
    token=API_TOKEN_AMIGOCLOUD_QUEMA, 
    project_url="https://app.amigocloud.com/api/v1/projects/31874")

# convercion de wkb a geometria shp
def convertir_wkb(wkb_data):
    return wkb.loads(wkb_data, hex=True)

# convierte de formato YYYY-mm-dd H:M:S+z a d/m/YYYY
def convertir_formato_fecha(fecha):
    new_formato = datetime.strptime(fecha, "%Y-%m-%d %H:%M:%S%z").strftime("%d/%m/%Y")
    return new_formato

# ejecuta cualquier query sql en el proyecto que se le indique
# requiere el id de proyecto, query a ejecutar y tipo solicitud (get o post)
def ejecutar_query_sql(id_project, query, tipo_sql):
    # define la url del proyecto para ejecutar el querry
    url_proyecto_sql = f'https://app.amigocloud.com/api/v1/projects/{id_project}/sql'
    # crea la estructura de query para amigocloud
    query_sql = {'query': query}
    # variable para almacenar resultado
    resultado_get = ''
    # eleige que tipo de solicitud se realizara (get o post)
    if tipo_sql == 'get': 
        resultado_get = amigocloud.get(url_proyecto_sql, query_sql)
    elif tipo_sql == 'post':
        resultado_get = amigocloud.post(url_proyecto_sql, query_sql)
    else:
        resultado_get = 'Se a seleccionado un tipo de solicitud erroneo.'
    return resultado_get

# ejecuta un query que esta almacenado en un proyecto de amigocloud (generalmente un update),
# requiere id de proyecto e id de query
# retorna cuantas filas fueron afectadas
def ejecutar_query_por_id(id_project, id_query, tipo_sql):
    # obtiene el query basado en el id_project y el id_query
    get_query = amigocloud.get(f'https://app.amigocloud.com/api/v1/projects/{id_project}/queries/{id_query}', timeout=15)
    # se extrae solo el texto del query
    query = get_query['query']
    # ejecuta el query_sql con metodo post y guarda la respuesta
    respuesta_post = ejecutar_query_sql(id_project, query, tipo_sql)
    # retorna el numero de filas afectadas por el query
    return respuesta_post

# convierte un dict a un obj
# recibe el dict y el nombre con el que se creara el obj
def convertir_dict_obj(diccionario, name):
    return collections.namedtuple(name, diccionario.keys())(*diccionario.values())

def buscar_nuevos():
    # busca todos los nuevos registros, retorna una lista de IDs
    query = 'select id, canhero, fecha_registro from dataset_351059 where informe_generado=false'
    url_proyecto_sql = f'https://app.amigocloud.com/api/v1/projects/31874/sql'
    query_sql = {'query': query}
    try:
        resultado_get = amigocloud.get(url_proyecto_sql, query_sql, timeout=15)
        resultado_get = resultado_get['data']
        # extrae los IDs de los nuevos regitros
        id_nuevos = [i['id'] for i in resultado_get]
        return id_nuevos
    except Exception as e:
        print(f"Error en buscar_nuevos: {e}")
        return []

def cargar_lotes_quema():
    # inserta los lotes desde catastro a lotes_quema,
    # solo lotes que un no esten en lotes_quema
    query = '''INSERT INTO dataset_351061 (unidad_01, unidad_02, unidad_05, id_inspeccion, geometria)
                SELECT 
                    cat.unidad_01,
                    cat.unidad_02,
                    cat.unidad_05,
                    insp.id AS id_inspeccion,
                    cat.wkb_geometry AS geometria
                FROM 
                    dataset_351059 insp
                JOIN 
                    dataset_377418 cat
                ON 
                    ST_Intersects(insp.ubicacion, cat.wkb_geometry)
                WHERE NOT EXISTS (
                    SELECT 1 
                    FROM dataset_351061 lotes 
                    WHERE lotes.id_inspeccion = insp.id 
                )'''
    url_proyecto_sql = f'https://app.amigocloud.com/api/v1/projects/31874/sql'
    query_sql = {'query': query}
    try:
        # .post retorna {'query':'...', 'count':2}, indicando la cantidad de registro modificados
        resultado_post = amigocloud.post(url_proyecto_sql, query_sql, timeout=15)
        # si 'count' no existe como key en el dict, retorna -1
        if 'count' not in resultado_post:
            return -1
        # retorn la cantidad de registros afectados
        return resultado_post['count']
    except Exception as e:
        print(f"Error en cargar_lotes_quema: {e}")
        return -1

def calcular_area_lotes_quema():
    # actualiza el area de todos los lotes de lotes_quema
    query = '''UPDATE dataset_351061 SET 
                area = round(cast(ST_Area(ST_Transform(geometria, 32720))/10000 as numeric),2)'''
    
    url_proyecto_sql = f'https://app.amigocloud.com/api/v1/projects/31874/sql'
    query_sql = {'query': query}
    try:
        # .post retorna {'query':'...', 'count':2}, indicando la cantidad de registro modificados
        resultado_post = amigocloud.post(url_proyecto_sql, query_sql, timeout=15)
        # si 'count' no existe como key en el dict, retorna -1
        if 'count' not in resultado_post:
            return -1
        # retorn la cantidad de registros afectados
        return resultado_post['count']
    except Exception as e:
        print(f"Error en cargar_lotes_quema: {e}")
        return -1
    
def sumar_total_area_inspeccion(id_insp):
    # suma todos los lotes de una inspeccion indicada en id_insp
    query = f'''UPDATE dataset_351059 insp SET
                    superficie_total = (SELECT sum(area) 
                                FROM dataset_351061 lotes 
                                WHERE insp.id=lotes.id_inspeccion),
                    produccion = (SELECT sum(area) 
                                FROM dataset_351061 lotes
                                WHERE insp.id=lotes.id_inspeccion) * rendimiento
                WHERE insp.id = {id_insp}'''
    url_proyecto_sql = f'https://app.amigocloud.com/api/v1/projects/31874/sql'
    query_sql = {'query': query}
    try:
        # .post retorna {'query':'...', 'count':1}, indicando la cantidad de registro modificados
        resultado_post = amigocloud.post(url_proyecto_sql, query_sql, timeout=15)
        # si 'count' no existe como key en el dict, retorna -1
        if 'count' not in resultado_post:
            return -1
        # retorn la cantidad de registros afectados
        return resultado_post['count']
    except Exception as e:
        print(f"Error en cargar_lotes_quema: {e}")
        return -1

def obtener_inspeccion(id_insp):
    # seleccionar un registro
    # crear consulta
    query = f'select * from dataset_351059 where id = {id_insp}'
    url_proyecto_sql = f'https://app.amigocloud.com/api/v1/projects/31874/sql'
    query_sql = {'query': query}
    try:
        resultado_get = amigocloud.get(url_proyecto_sql, query_sql, timeout=15)
        inspeccion = resultado_get['data'][0]
        # convertion de formato de fechas
        inspeccion['date'] = convertir_formato_fecha(inspeccion['fecha_registro'])
        inspeccion['fecha_inspeccion'] = convertir_formato_fecha(inspeccion['fecha_inspeccion'])
        inspeccion['fecha_quema'] = convertir_formato_fecha(inspeccion['fecha_quema'])
        # convertir el dict en objeto
        insp = convertir_dict_obj(inspeccion, 'insp')
        return insp
    except Exception as e:
        print(f"Error en buscar_nuevos: {e}")
        return None

def obtener_lotes(id_insp):
    # seleccionar todos los lotes marcados con la inspeccion
    # crear consulta
    query = f'select * from dataset_351061 where id_inspeccion = {id_insp}'
    url_proyecto_sql = f'https://app.amigocloud.com/api/v1/projects/31874/sql'
    query_sql = {'query': query}
    try:
        resultado_get = amigocloud.get(url_proyecto_sql, query_sql, timeout=15)
        lotes = resultado_get['data']
        return lotes
    except Exception as e:
        print(f"Error en obtener_lotes: {e}")
        return []

# elimina todos los dic duplicados basandose en "unidad_01", y concerva solo en cop_prop y nom_prop
# con esto se obtiene un dict de propiedades de la inspeccion
def eliminar_duplicados_y_conservar_campos(lista, campo_clave, campos_a_conservar):
    vistos = set()
    nueva_lista = []
    for diccionario in lista:
        valor = diccionario[campo_clave]
        if valor not in vistos:
            vistos.add(valor)
            nuevo_diccionario = {campo: diccionario[campo] for campo in campos_a_conservar}
            nueva_lista.append(nuevo_diccionario)
    return nueva_lista

def propiedades_lotes(props):
    # recorrer las propiedades, y agregar los lotes correspondientes
    # se crea una lista de objetos propiedad con los respectivos lotes agregados a cada propiedad
    propiedades = []
    for prop in props:
        prop['lote'] = []
        lotes_select = [lote for lote in lotes if lote['unidad_01'] == prop['unidad_01']]
        for lote_select in lotes_select:
            lote = convertir_dict_obj(lote_select, 'lote')
            prop['lote'].append(lote)
        propiedades.append(convertir_dict_obj(prop, 'propiedad'))
    return propiedades

def obtener_fotos(insp_amigo_id):
    # buscar todas las fotos que son parte de la inspeccion
    # crear consulta
    query = f'select amigo_id, source_amigo_id, filename from gallery_61142 where source_amigo_id = \'{insp_amigo_id}\''
    # ejecutar consulta
    fotos = ejecutar_query_sql(PROYECTO_ID, query, 'get')
    # extrae la seccion de data
    fotos = fotos['data']
    return fotos

def cambiar_estado_informe(id_insp):
    # actualizar estado de informe_generado a true
    # crear consulta
    query = f'update dataset_351059 set informe_generado = true where id = {id_insp}'
    # ejecutar consulta
    res = ejecutar_query_sql(PROYECTO_ID, query, 'post')
    return res

def generar_planos(insp, propiedades):
    # generar planos
    lista_planos = []
    path = ''
    for propiedad in propiedades:
        lotes_lista = []
        for lote in propiedad.lote:
            lotes_lista.append(lote._asdict())
        df = pd.DataFrame(lotes_lista)
        df['geometria'] = df['geometria'].apply(convertir_wkb)

        #Convertir a GeoDataFrame
        data = gpd.GeoDataFrame(df, geometry='geometria')

        data['coords'] = data['geometria'].apply(lambda x: x.representative_point().coords[:])
        data['coords'] = [coords[0] for coords in data['coords']]

        data.crs = "EPSG:4326"
        data = data.to_crs(epsg=3857)
        
        fig = plt.figure(i, figsize=(20,20))
        ax = None
        ax = fig.add_subplot()

        data.apply(lambda x: ax.annotate(text=x.unidad_05 + ' \n' + str(x.area) + ' ha', xy=x.geometria.centroid.coords[0], ha='center', va='center', color='black', fontsize=12, weight=1000, bbox=dict(facecolor=(1,1,1,0.3), edgecolor='none', pad=0)), axis=1);
    
        minx, miny, maxx, maxy = data.total_bounds
        ax.set_xlim(minx - 500, maxx + 500)
        ax.set_ylim(miny - 400, maxy + 400)

        data.plot(ax=ax, edgecolor='r', facecolor=(0,0,0,0), linewidth=2, figsize=(20,20))
    
        ctx.add_basemap(ax, source=ctx.providers.Esri.WorldImagery)
        ax.set_axis_off()
        ax.set_title(str(propiedad.unidad_01) + ' / ' + str(propiedad.unidad_02), fontsize=20)
        path = PATH_PLANOS + str(insp.amigo_id) + '_' + str(propiedad.unidad_01) + '.jpeg'
        lista_planos.append(path)
        fig.savefig(path, dpi = 300, bbox_inches='tight')
        plt.clf()
    return lista_planos

def generar_reporte(insp, propiedades, fotos, lista_planos):
    # generar reporte
    # asignacion de template
    doc = DocxTemplate(PATH_TEMPLATE_INFORME)

    #generar lista de InlineImage de planos 
    lista_InlineImage = []
    for plano in lista_planos:
        lista_InlineImage.append(docxtpl.InlineImage(doc, image_descriptor=plano, width=Mm(150)))

    #descargar fotos y generar lista InlineImage
    lista_fotos_inline = []
    for foto in fotos:
        print(foto)
        url_foto = f"https://app.amigocloud.com/api/v1/related_tables/61142/files/{foto['source_amigo_id']}/{foto['amigo_id']}/{foto['filename']}"
        try:
            contenido = amigocloud.get(url_foto, raw=True)
            ruta_salida = PATH_FOTOS + foto['amigo_id'] + '.jpg'
            with open(ruta_salida, "wb") as f:
                f.write(contenido)
            lista_fotos_inline.append({'foto': docxtpl.InlineImage(doc, image_descriptor= ruta_salida, width=Mm(120))})
        except Exception as e:
            print(f"❌ Error al descargar {foto['filename']}: {e}")
            
    firma_respon = None
    if insp.responsable_tec == 'Rogelio Acuña Rodríguez':
        firma_respon = docxtpl.InlineImage(doc, image_descriptor=PATH_FIRMAS + '\\firma_rogelio.png', width=Mm(60))
    else:
        firma_respon = docxtpl.InlineImage(doc, image_descriptor=PATH_FIRMAS + '\\firma_juan_pablo.png', width=Mm(60))

    context = {'insp':insp, 'propiedades':propiedades, 'planos':lista_InlineImage, 'fotos':lista_fotos_inline, 'firma':firma_respon}

    doc.render(context)

    # formato de nombre de archivo: "123_CQ_01-01-2022_NOMBRE"
    cod_nom = insp.canhero.split(' / ')
    file_name = cod_nom[0] + '_IDCQ_' + insp.fecha_inspeccion.replace('/','-') + '_' + cod_nom[1] + '_' + str(insp.id)

    doc.save(PATH_INFORMES + file_name + '.docx')
    return None

def main():
    while True:
        reg_nuevos = buscar_nuevos()
        print(reg_nuevos)
        
        if len(reg_nuevos) == 0:
            print('No se encontraron registros nuevos')
            continue

        count_lotes_cargado = cargar_lotes_quema()
        count_areas_calculadas = calcular_area_lotes_quema()

        if count_lotes_cargado == -1 or count_areas_calculadas == -1:
            print('Error al cargar lotes quema, o error al actualziar areas de lotes quema')
            continue
        
        for i in reg_nuevos:
            insp = obtener_inspeccion(i)
            if insp == None:
                print(f'Error, no se pudo obtener datos de inspeccion: {id}')
                continue
            
            lotes = obtener_lotes(i)
            if len(lotes) == 0:
                print(f'Error, no se pudo obtener lotes quema: {id}')
                continue

            '''
            # de lotes eliminar todos los duplicados, y solo se queda con el codigo y nombre de propiedad, esto sera el objeto de propiedades que son parte de la inspeccion
            props = eliminar_duplicados_y_conservar_campos(lotes, 'unidad_01', ['unidad_01', 'unidad_02'])
            propiedades = propiedades_lotes(props)
            fotos = obtener_fotos(insp.amigo_id)

            if len(fotos) == 0:
                print(f'Inspeccion {i} no tiene fotos')
            lista_planos = generar_planos(insp, propiedades)
            print(insp)
            # print(propiedades)
            print(fotos)
            generar_reporte(insp, propiedades, fotos, lista_planos)
            cambiar_estado_informe(i)
            print(f'Informe generado de {insp.canhero}')
            '''

if __name__ == "__main__":
    main()