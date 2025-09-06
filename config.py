import os
from dotenv import load_dotenv

# Cargar .env solo si existe (desarrollo)
if os.path.exists(".env"):
    load_dotenv() 

API_TOKEN_AMIGOCLOUD_QUEMA = os.getenv('API_TOKEN_AMIGOCLOUD_QUEMA')

PROYECTO_ID = os.getenv('PROYECTO_ID')
BUSCAR_REG_NUEVOS = os.getenv('BUSCAR_REG_NUEVOS')
CARGAR_LOTES_QUEMA = os.getenv('CARGAR_LOTES_QUEMA')
CALC_AREA_LOTES = os.getenv('CALC_AREA_LOTES')
CALC_TOTAL_INSP = os.getenv('CALC_TOTAL_INSP')

PATH_TEMPLATE_INFORME = os.getenv('PATH_TEMPLATE_INFORME')
PATH_INFORMES = os.getenv('PATH_INFORMES')
PATH_PLANOS = os.getenv('PATH_PLANOS')
PATH_FOTOS = os.getenv('PATH_FOTOS')
PATH_FIRMAS = os.getenv('PATH_FIRMAS')

#print(PATH_PLANOS)