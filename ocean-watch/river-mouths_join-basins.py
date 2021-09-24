# imports
import logging
from cartoframes.auth import set_default_credentials
from cartoframes import read_carto, to_carto
import geopandas as gpd
from datetime import datetime
import dateutil.relativedelta
import requests
import xml.etree.ElementTree as ET
import math
import concurrent.futures
import zipfile

import pandas as pd

import os
import sys

# set up logging

# get top-level logger object
logger = logging.getLogger()
for handler in logger.handlers: logger.removeHandler(handler)
# manually set level 
logger.setLevel(logging.INFO)
# print to console
console = logging.StreamHandler()
logger.addHandler(console)
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

logger.info('Adding level 12 basin info to processed river mouth points')

# authenticate carto account 
CARTO_USER = os.getenv('CARTO_WRI_RW_USER')
CARTO_KEY = os.getenv('CARTO_WRI_RW_KEY')
set_default_credentials(username=CARTO_USER,
                        base_url="https://{user}.carto.com/".format(user=CARTO_USER),
                        api_key=CARTO_KEY)

# load level 12 basin dataset
# global level 12 basin dataset has too many features--cannot be stored on carto
# will instead be dealt with locally
# files can be downloaded (manually) at:
#   https://www.dropbox.com/sh/hmpwobbz9qixxpe/AACPCyoHHAQUt_HNdIbWOFF4a/HydroBASINS/standard?dl=0&subfolder_nav_tracking=1
# approach borrowed from:
#   https://github.com/resource-watch/data-pre-processing/blob/master/wat_068_rw0_watersheds/wat_068_rw0_watersheds_processing.py
local_data_dir = '/mnt/c/Users/PKerins.local/data/ocean-watch/hydrosheds'
region_ids = ['af','ar','as', 'au','eu','gr','na','sa','si']
zip_file_template = os.path.join(local_data_dir, 'hybas_{}_lev12_v1c.zip')
shp_file_template = os.path.join(local_data_dir, 'hybas_{}_lev12_v1c.shp')

for region_id in region_ids:
    if os.path.isfile(shp_file_template.format(region_id)):
        continue
    zip_file = zip_file_template.format(region_id)
    with zipfile.ZipFile(zip_file, 'r') as zip:
        zip.extractall(local_data_dir) 

gdf_l12 = None   
for region_id in region_ids:
    shp_file = shp_file_template.format(region_id)
    gdf_reg = gpd.read_file(shp_file, ignore_geometry=True)
    if gdf_l12 is None:
        gdf_l12 = gdf_reg
    else:
        gdf_l12 = gdf_l12.append(gdf_reg, ignore_index=True, verify_integrity=True, sort=False)
gdf_l12 = gdf_l12.astype({'HYBAS_ID':'str','PFAF_ID':'str'})

# load processed river mouth dataset
gdf_mouths = read_carto('ocn_calcs_010_target_river_mouths')
if 'pfaf_id_12' in gdf_mouths.columns:
    gdf_mouths.drop(columns=['pfaf_id_12','pfaf_id_5','pfaf_id_3','hybas_id_5','hybas_id_3'], inplace=True, errors='ignore')

# join level12 river basin data to river mouth data
# allows us to get the pfaf_id for each terminal river mouth level 12 basin
gdf_mouths = gdf_mouths.merge(gdf_l12, how='left', left_on='hybas_l12', right_on='HYBAS_ID', 
        sort=False, validate='many_to_one')
gdf_mouths.drop(columns=['HYBAS_ID', 'NEXT_DOWN',
       'NEXT_SINK', 'MAIN_BAS', 'DIST_SINK', 'DIST_MAIN', 'SUB_AREA',
       'UP_AREA', 'ENDO', 'COAST', 'ORDER', 'SORT'], inplace=True, errors='raise')
gdf_mouths.rename(columns={'PFAF_ID': 'pfaf_id_12'}, inplace=True, errors='raise')

# use level 12 basin pfaf_id to find the corresponding level 5 basin
gdf_mouths['pfaf_id_5'] = gdf_mouths['pfaf_id_12'].str.slice(stop=5)
gdf_l5 = read_carto("SELECT hybas_id::text, pfaf_id::text FROM wat_068_rw0_watersheds_edit WHERE level=5")
gdf_mouths = gdf_mouths.merge(gdf_l5, how='left', left_on='pfaf_id_5', right_on='pfaf_id', 
        sort=False)
gdf_mouths.rename(columns={'hybas_id':'hybas_id_5'}, inplace=True, errors='raise')
gdf_mouths.drop(columns=['pfaf_id'], inplace=True, errors='raise')

# use level 12 basin pfaf_id to find the corresponding level 3 basin
gdf_mouths['pfaf_id_3'] = gdf_mouths['pfaf_id_12'].str.slice(stop=3)
gdf_l3 = read_carto("SELECT hybas_id::text, pfaf_id::text FROM wat_068_rw0_watersheds_edit WHERE level=3")
gdf_mouths = gdf_mouths.merge(gdf_l3, how='left', left_on='pfaf_id_3', right_on='pfaf_id', 
        sort=False)
gdf_mouths.rename(columns={'hybas_id':'hybas_id_3'}, inplace=True, errors='raise')
gdf_mouths.drop(columns=['pfaf_id','pfaf_id_5','pfaf_id_3'], inplace=True, errors='raise')

# store enriched version of river mouth dataset with basin identifiers for
# level 12, 5, and 3 basins corresponding to river outlet
to_carto(gdf_mouths, 'ocn_calcs_010_target_river_mouths', if_exists='replace')
