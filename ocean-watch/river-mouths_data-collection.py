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

# name of table on Carto where you want to upload data
# this should be a table name that is not currently in use
dataset_name = 'ocn_020alt_chemical_concentrations'

logger.info('Executing script for dataset: ' + dataset_name)

logger.debug('Pull rivermouth points from Carto table')
# authenticate carto account 
CARTO_USER = os.getenv('CARTO_WRI_RW_USER')
CARTO_KEY = os.getenv('CARTO_WRI_RW_KEY')
set_default_credentials(username=CARTO_USER,
                        base_url="https://{user}.carto.com/".format(user=CARTO_USER),
                        api_key=CARTO_KEY)
# prepare request parameters
variables = [
    'o2',
    'no3',
    'po4'
]
depths = [
    -0.49402499198913574,
    -1.5413750410079956,
    -2.6456689834594727,
    -3.8194949626922607,
    -5.078224182128906,
]

# define function for creating request

def build_wms_request(x, y, variable, depth):
    xmin = x-0.0
    ymin = y-0.0
    xmax = x+0.0000001
    ymax = y+0.0000001
    # make request the 16th of month before last..
    now = datetime.utcnow()
    dt_end = now.replace(day=16)
    months_ago = 2 if (now.day > 16) else 3
    dt_end = dt_end - dateutil.relativedelta.relativedelta(months=months_ago)
    date_end = dt_end.strftime('%Y-%m-%d')
    req_template = (
        'https://nrt.cmems-du.eu/thredds/wms/global-analysis-forecast-bio-001-028-monthly?'
        'SERVICE=WMS'
        '&VERSION=1.1.1'
        '&REQUEST=GetFeatureInfo'
        '&QUERY_LAYERS={variable}'
        '&BBOX={xmin},{ymin},{xmax},{ymax}'
        '&HEIGHT=1'
        '&WIDTH=1'
        '&INFO_FORMAT=text/xml'
        '&SRS=EPSG:4326'
        '&X=0'
        '&Y=0'
        '&elevation={depth}'
        '&time=2019-01-16T12:00:00.000Z/{date_end}T12:00:00.000Z'
    )
    return req_template.format(variable=variable, xmin=xmin, ymin=ymin, xmax=xmax, ymax=ymax, 
        depth=depth, date_end=date_end)

# print(example_resp.content)
def parse_response(response):
    '''
    Parse content of response from GetFeatureInfo query to Copernicus WMS
    INPUT   response: raw response object from requests library (requests.models.Response)
    RETURN  df_resp: structured data object for response (DataFrame)
    '''
    if response.status_code != 200:
        return None
    root = ET.fromstring(response.content)
    response_dict = {}
    response_data_times = []
    response_data_values = []

    dt_format = '%Y-%m-%dT%H:%M:%S.000Z'

    for child in root.iter('*'):
        if(child.tag == 'FeatureInfoResponse'):
            continue
        if(child.tag == 'longitude'):
            response_dict['longitude'] = float(child.text)
        if(child.tag == 'latitude'):
            response_dict['latitude'] = float(child.text)
        if(child.tag == 'iIndex'):
            response_dict['iIndex'] = int(child.text)
        if(child.tag == 'jIndex'):
            response_dict['jIndex'] = int(child.text)
        if(child.tag == 'gridCentreLon'):
            response_dict['gridCentreLon'] = float(child.text)
        if(child.tag == 'gridCentreLat'):
            response_dict['gridCentreLat'] = float(child.text)
        if(child.tag == 'FeatureInfo'):
            continue
        if(child.tag == 'time'):
            response_data_times.append(datetime.strptime(child.text, dt_format))
        if(child.tag == 'value'):
            if child.text == 'none':
                # legitimate request, but no data available at this location (ie invalid coordinates)
                return None
            response_data_values.append(float(child.text));
        # print(child.tag)
    # resp_cols = ['longitude','latitude','gridCentreLon','gridCentreLat','dt','value']
    df_resp = pd.DataFrame()
    df_resp['longitude'] = [response_dict['longitude'] for i in range(len(response_data_times))]
    df_resp['latitude'] = [response_dict['latitude'] for i in range(len(response_data_times))]
    df_resp['gridCentreLon'] = [response_dict['gridCentreLon'] for i in range(len(response_data_times))]
    df_resp['gridCentreLat'] = [response_dict['gridCentreLat'] for i in range(len(response_data_times))]
    df_resp['dt'] = response_data_times
    df_resp['value'] = response_data_values
    return df_resp

# # known-to-work query drawn from copernicus website (pretty viewer)
# example_req = 'https://nrt.cmems-du.eu/thredds/wms/global-analysis-forecast-bio-001-028-monthly?SERVICE=WMS&VERSION=1.1.1&REQUEST=GetFeatureInfo&QUERY_LAYERS=o2&BBOX=-39.04,-13.92,-39.0399999,-13.9199999&HEIGHT=1&WIDTH=1&INFO_FORMAT=text/xml&SRS=EPSG:4326&X=0&Y=0&elevation=-0.49402499198913574&time=2019-01-16T12:00:00.000Z/2021-05-16T12:00:00.000Z'
# print(example_req)
# example_resp = requests.get(example_req)
# df_example = parse_response(example_resp)

test_req = build_wms_request(-39.04,-13.92,'o2',depths[0])
print(test_req)
test_resp = requests.get(test_req)
df_test = parse_response(test_resp)

# pull data
gdf_mouths = read_carto('ocn_calcs_010test_target_river_mouths')
df_cmems = None

for index, row in gdf_mouths.iterrows():
    # say we have our x and y
    x, y = row['x_valid'], row['y_valid']
    hyriv_id = row['hyriv_id']
    if x is None or y is None:
        # corrected coordinates have not been set
        print('No valid coordinates for processed river mouth: HYRIV_ID='+hyriv_id)
        continue
    for variable in variables:
        for depth in depths:
            req = build_wms_request(x, y, variable, depth)
            resp = requests.get(req)
            df_resp = parse_response(resp)
            if df_resp is None:
                raise Exception('Invalid response to supposedly valid location: HYRIV_ID='+hyriv_id)
            df_resp['hyriv_id'] = [hyriv_id for i in range(len(df_resp))]
            if df_cmems is None:
                df_cmems = df_resp.copy()
            else:
                df_cmems = df_cmems.append(df_resp, ignore_index=True, sort=False,)
            break

to_carto(df_cmems, 'ocn_calcs_011_river_mouth_chemical_concentrations', if_exists='replace')
