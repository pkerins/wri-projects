# imports
import logging
from cartoframes.auth import set_default_credentials
from cartoframes import read_carto
import geopandas as gpd
from datetime import datetime
import dateutil.relativedelta
import requests

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

def build_wms_request(variable, x, y, depth):
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

example_req = 'https://nrt.cmems-du.eu/thredds/wms/global-analysis-forecast-bio-001-028-monthly?SERVICE=WMS&VERSION=1.1.1&REQUEST=GetFeatureInfo&QUERY_LAYERS=o2&BBOX=-39.04,-13.92,-39.0399999,-13.9199999&HEIGHT=1&WIDTH=1&INFO_FORMAT=text/xml&SRS=EPSG:4326&X=0&Y=0&elevation=-0.49402499198913574&time=2019-01-16T12:00:00.000Z/2021-05-16T12:00:00.000Z'
print(example_req)
example_resp = requests.get(example_req)


test_req = build_wms_request('o2',-39.04,-13.92,depths[0])
print(test_req)
test_resp = requests.get(test_req)

print('requests identical? ', example_req == test_req)


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
    if(dir==0):
        test_x = x + (step_size * step)
        test_y = y
    elif(dir==90):
        test_x = x
        test_y = y + (step_size * step)
    elif(dir==180):
        test_x = x - (step_size * step)
        test_y = y 
    elif(dir==270):
        test_x = x 
        test_y = y - (step_size * step)
    else:
        raise ValueError('Illegal argument for direction: '+dir+'. Must be E/N/W/S')
    return (test_x, test_y)
        

def build_test_sequence(x, y, step_size=0.2, n_steps=2):
    '''
    Create sequence of test coordinates to perform crude search for valid location
    closest to original point
    INPUT   x: original point longitude coordinate (numeric)
            y: original point latitude coordinate (numeric)
            step_size: size of each step, in degrees (numeric)
            n_steps: number of steps to include in sequence, where each step
                represents a larger concentric circle around original point
    RETURN  test_seq: test sequence of long/lat coordinates for testing (list of numeric tuples)
    '''


# pull data
gdf_mouths = read_carto('ocn_calcs_010_target_river_mouths')

for index, row in gdf_mouths.iterrows():
    # say we have our x and y
    x, y = row['the_geom'].x, row['the_geom'].y
    
    for variable in variables:
        for depth in depths:
            cmems_req = build_wms_request(variable, x, y, depth)
            print(cmems_req)
            response = requests.get(cmems_req)
            break



# preexisting:
# set of points representing river mouths
# table for data

# cycle
# for each point:
# for each chemical & depth:
# construct query
# pull data from wms
# hold xml response
# convert to something, probably dataframe
# (may choose to parallelize this process)
# append to larger existing dataframe




# at end: 
# dump dataframe to file
# clean existing persistent table
# dump new dataframe into table

# create temporary folder for holding execution files
temp_dir = tempfile.TemporaryDirectory()
print(temp_dir.name)
# use temp_dir, and when done:
temp_dir.cleanup()