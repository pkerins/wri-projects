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

import pandas as pd

import os
import sys

# set up logging

# get top-level logger object
logger = logging.getLogger()
for handler in logger.handlers: logger.removeHandler(handler)
# manually set level 
logger.setLevel(logging.DEBUG)
# print to console
console = logging.StreamHandler()
logger.addHandler(console)
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

# name of table on Carto where you want to upload data
# this should be a table name that is not currently in use
dataset_name = 'ocn_020alt_chemical_concentrations'

logger.debug('Authenticate Carto credentials')
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

def parse_response(response):
    '''
    Parse content of response from GetFeatureInfo query to Copernicus WMS
    INPUT   response: raw response object from requests library (requests.models.Response)
    RETURN  df_resp: structured data object for response; None if unable to parse (DataFrame)
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

def pull_data(row, variable, depth):
    if row['x_valid'] is None or row['y_valid'] is None:
        # corrected coordinates have not been set
        # print('No valid coordinates for processed river mouth: HYRIV_ID='+hyriv_id)
        return None
    hyriv_id = row['hyriv_id']
    x, y = float(row['x_valid']), float(row['y_valid'])
    req = build_wms_request(x, y, variable, depth)
    resp = requests.get(req)
    df_resp = parse_response(resp)
    if df_resp is None:
        raise ValueError('Invalid response to supposedly valid location: HYRIV_ID='+hyriv_id)
    df_resp['hyriv_id'] = hyriv_id
    df_resp['pfaf_id_12'] = row['pfaf_id_12']
    df_resp['hybas_id_5'] = row['hybas_id_5']
    df_resp['hybas_id_3'] = row['hybas_id_3']
    df_resp['ord_flow'] = row['ord_flow']
    df_resp['variable'] = variable
    df_resp['depth'] = depth
    cols_reorder = ['longitude','latitude','gridCentreLon','gridCentreLat','dt','variable','depth','value',
            'hyriv_id','pfaf_id_12','hybas_id_5','hybas_id_3','ord_flow']
    df_resp = df_resp[cols_reorder]
    return df_resp

logger.debug('Pull river mouth data from Carto')
gdf_mouths = read_carto('ocn_calcs_010_target_river_mouths')

results = []
logger.info('Initiate multithreading for WMS requests')
# request all records for all permutations, combine into single dataframe
with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
    args_list = []
    args_pending = []
    logger.info('Build request arguments')
    for index, row in gdf_mouths.iterrows():
        # # manual control over looping for interrupted runs
        # if index < 0:
        #     continue
        # if index > 100:
        #     break
        if row['x_valid'] is None or row['y_valid'] is None:
            continue
        for variable in variables:
            for depth in depths:
                args_list.append([index, row, variable, depth])
                # if index == 0:
                #     print([index, variable, depth])
    args_pending = args_list.copy()
    logger.info('Begin request submission loop')
    while(args_pending): # if list not empty
        args_try = args_pending.copy()
        args_pending = []
        logger.debug('Create Futures for outstanding requests ('+str(len(args_try))+')')
        future_to_args = {executor.submit(pull_data, args[1], args[2], args[3]): args for args in args_try}
        for future in concurrent.futures.as_completed(future_to_args):
            args = future_to_args[future]
            try:
                results.append(future.result())
                # print('completed', args)
                if args[0] % 100 == 0 and args[2]==variables[-1] and args[3]==depths[-1]:
                    print('successful request for idx#'+str(args[0])+' at '+str(datetime.now()))
            except ConnectionError as e:
                print(e)
                args_pending.append(args)
            except Exception as e:
                print(e)
                args_pending.append(args)
        logger.debug('Futures completed')
logger.info('Construct DataFrame from full set of responses')
df_all = pd.concat([result for result in results if result is not None],
        axis=0, ignore_index=True)
df_all.sort_values(['hyriv_id','variable','depth','dt'],
        axis=0, ascending=True, inplace=True, ignore_index=True)

logger.info('Persist DataFrame to Carto')
to_carto(df_all, dataset_name, if_exists='replace')