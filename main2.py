from sqlalchemy import create_engine
import geopandas as gpd
import matplotlib.pyplot as plt

USER='postgres'
PASSWORD='A123456*'
HOST='localhost'
PORT='5433'
DATABASE='utea'

def obtener_engine():
    return create_engine(
        f"postgresql+psycopg2://{USER}:{PASSWORD}@{HOST}:{PORT}/{DATABASE}"
    )

gdf = gpd.read_postgis(
    "SELECT * FROM catastro_iag.catastro WHERE unidad_01=30", 
    obtener_engine(), 
    geom_col='geom'  # columna con la geometría
)


gdf.plot()