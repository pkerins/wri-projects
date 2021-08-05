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
import time

import pandas as pd


import tempfile

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

logger.info('Executing preliminary script for internal dataset ocn_calcs_010_target_river_mouths: ' + 
    'must identify corrected points in ocean where Copernicus nutrient time series is available')

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


def build_test_coords(x, y, dir=0, step=1, step_size=0.2):
    '''
    Create point in test sequence
    INPUT   x: original point longitude coordinate (numeric)
            y: original point latitude coordinate (numeric)
            dir: direction in which to create test point, in degrees,
                using standard unit circle coordinates (0 = east)
            step: number of steps in this direction (int)
            step_size: size of each step, in degrees (numeric)
    RETURN  coords: long/lat coordinates for test point (numeric tuple)
    '''
    test_x = x + (math.cos(math.radians(dir)) * step_size * step)
    test_y = y + (math.sin(math.radians(dir)) * step_size * step)
    return (test_x, test_y)
        

def build_test_sequence(x, y, step_size=0.1, n_steps=4, dirs='ordinal'):
    '''
    Create sequence of test coordinates to perform crude search for valid location
    closest to original point
    INPUT   x: original point longitude coordinate (numeric)
            y: original point latitude coordinate (numeric)
            step_size: size of each step, in degrees (numeric)
            n_steps: number of steps to include in sequence, where each step
                represents a larger concentric circle around original point
            dirs: set of directions to incorporate within sequence (string)
    RETURN  test_seq: test sequence of long/lat coordinates for testing (list of numeric tuples)
    '''
    if dirs.lower()=='cardinal':
        dirs = [0, 90, 180, 270]
    elif dirs.lower()=='ordinal':
        dirs = [0, 45, 90, 135, 180, 225, 270, 315]
    elif dirs.lower()=='secondary':
        dirs = [0, 22.5, 45, 67.5, 90, 112.5, 135, 157.5, 180, 202.5, 225, 247.5, 270, 292.5, 315, 337.5]
    test_coords = []
    for step in range(1, n_steps+1):
        for dir in dirs:
            test_coords.append(build_test_coords(x, y, dir=dir, step=step, step_size=step_size))
    return test_coords

# pull data
gdf_mouths = read_carto('ocn_calcs_010_target_river_mouths')

test_existing_valid_coords = False
valid_rows = []
matching_rows = []
updated_rows = []
helpless_rows = []
n_requests = 0
n_fixed = 0

for index, row in gdf_mouths.iterrows():
    if index < 0:
        # manual control over looping for interrupted runs
        continue
    x_valid = row['x_valid']
    y_valid = row['y_valid']
    if x_valid is not None and y_valid is not None:
        if not test_existing_valid_coords:
            continue
        valid_req = build_wms_request(float(x_valid), float(y_valid), variables[0], depths[0])
        valid_resp = requests.get(valid_req)
        df_valid = parse_response(valid_resp)
        if df_valid is None:
            # this is a problem; valid point should return valid results
            raise Exception('Supposedly valid point does not return valid result! '+
                row.to_string())
        else:
            # don't need to do anything here
            valid_rows.append(row['hyriv_id'])
            continue
    # if here, we do not have pre-existing, valid coordinates stored
    x, y = row['the_geom'].x, row['the_geom'].y
    point_req = build_wms_request(x, y, variables[0], depths[0])
    point_resp = requests.get(point_req)
    n_requests += 1
    df_resp = parse_response(point_resp)
    if df_resp is not None:
        # good to go, response worked
        gdf_mouths.loc[index, 'x_valid'] = x
        gdf_mouths.loc[index, 'y_valid'] = y
        matching_rows.append(row['hyriv_id'])
        continue
    else:
        # query failed, need to find valid coordinates
        found = False
        test_seq = build_test_sequence(x, y, n_steps=7, dirs='secondary')
        for test_coords in test_seq:
            x_test = test_coords[0]
            y_test = test_coords[1]
            test_req = build_wms_request(x_test, y_test, variables[0], depths[0])
            try:
                test_resp = requests.get(test_req)
            except ConnectionError as e:
                print(e)
                time.sleep(120)
                continue
            n_requests += 1
            df_test = parse_response(test_resp)
            if df_test is not None:
                # success; test_coords -> valid_coords
                gdf_mouths.loc[index, 'x_valid'] = x_test
                gdf_mouths.loc[index, 'y_valid'] = y_test
                updated_rows.append(row['hyriv_id'])
                found = True
                n_fixed += 1
                if n_fixed > 12:
                    to_carto(gdf_mouths, 'ocn_calcs_010test_target_river_mouths', if_exists='replace')
                    print('Index of last repair: ' + str(index))
                    n_fixed = 0
                break
        if not found:
            print('Unable to find valid point for base river mouth: HYRIV_ID=' +
                row['hyriv_id'])
            helpless_rows.append(row['hyriv_id'])
        # searching on this river mouth complete, whether successful or not
    # slow process. can save incremental progress to disk, then manage loop manually
    if index != 0 and index % 500 == 0:
        to_carto(gdf_mouths, 'ocn_calcs_010test_target_river_mouths', if_exists='replace')

print(n_requests)    
print(gdf_mouths)

to_carto(gdf_mouths, 'ocn_calcs_010_target_river_mouths', if_exists='replace')