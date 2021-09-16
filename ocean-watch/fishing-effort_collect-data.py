import logging
from cartoframes.auth import set_default_credentials
from cartoframes import read_carto, to_carto
import pandas as pd
import geopandas as gpd
from datetime import date
from pprint import pprint
import json
import time
# import dateutil.relativedelta
import requests
import urllib.request
# import xml.etree.ElementTree as ET
# import math
# import concurrent.futures

# import pandas as pd

import os
# import sys

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

# fixed items defined by gfw
INITIATE_REPORT_ENDPOINT = 'https://gateway.api.globalfishingwatch.org//v1/reports'
INQUIRE_STATUS_ENDPOINT = 'https://gateway.api.globalfishingwatch.org//v1/reports/{}'
RETRIEVE_URL_ENDPOINT = 'https://gateway.api.globalfishingwatch.org//v1/reports/{}/url'

# related objects
INITIATE_REPORT_HEADERS = {
    'Content-Type':'application/json',
    'Authorization':os.getenv('GFW_API_KEY')
}
INQUIRE_STATUS_HEADERS = {
    'Authorization':os.getenv('GFW_API_KEY')
}
RETRIEVE_URL_HEADERS = {
    'Authorization':os.getenv('GFW_API_KEY')
}

logger.debug('Retrieve polygons from Carto')
# retrieve polygons from carto
eez_table = 'com_011_rw1_maritime_boundaries_edit'
# dataset includes following types:
# '12NM', '24NM', '200NM', 'Overlapping claim', 'Joint regime'
# the final three are of potential relevance here
# collect the data for them all, but maintain the distinction for later ease
gdf_zones = read_carto("SELECT * FROM com_011_rw1_maritime_boundaries_edit WHERE pol_type IN ('200NM', 'Overlapping claim', 'Joint regime') AND mrgid=8400",
        index_col='cartodb_id')
gdf_zones = gdf_zones.astype({'mrgid':'int','mrgid_ter1':'int','mrgid_sov1':'int',
        'mrgid_eez':'int','un_sov1':'int','un_ter1':'int',})
gdf_zones['json'] = gdf_zones.the_geom.to_json()

# create set of pairs of dates to loop through
date_pairs = [(date(year,1,1), date(year+1,1,1)) for year in range(2012, 2022)]

# create object to track api activity & results
# mrgid, geoname, year, id, url, zip, csv, value
col_type_dict = {
    'mrgid':'int',
    'geoname':'str',
    'year':'int',
    'id':'str',
    'url':'str',
    'zip':'str',
    'csv':'str',
    'value':'float',
}
df_reports = pd.DataFrame({c: pd.Series(dtype=t) for c, t in col_type_dict.items()})

logger.debug('Define functions for submitting API requests and handling responses')
def build_req_data(report_name, date_pair, json_str,  
        value=None, geoname=None, mrgid=None, gfw_id=None):
    # construct data object
    req_data = {}
    req_data['name'] = report_name
    req_data['geometry'] = {}
    req_data['geometry']['type'] = 'Feature'
    req_data['geometry']['properties'] = {}
    if value is not None: req_data['geometry']['properties']['value'] = value
    if geoname is not None: req_data['geometry']['properties']['geoname'] = geoname
    if mrgid is not None: req_data['geometry']['properties']['mrgid'] = mrgid
    if gfw_id is not None: req_data['geometry']['properties']['gfw_id'] = gfw_id
    json_dict = json.loads(json_str)
    if len(json_dict['features']) > 1: 
        raise Exception('not sure if we want this or will encounter')
    req_data['geometry']['geometry'] = json_dict['features'][0]['geometry']
    req_data['type'] = 'detail'
    req_data['timeGroup'] = 'none'
    req_data['filters'] = ['']
    req_data['datasets'] = ['public-global-fishing-tracks:latest']
    date_format = '%Y-%m-%d'
    req_data['dateRange'] = [date_pair[0].strftime(date_format), date_pair[1].strftime(date_format)]
    return req_data

def build_req_data_from_row(report_name, date_pair, row):
    return build_req_data(report_name, date_pair, row.json, 
        value=row.geoname, geoname=row.geoname, mrgid=row.mrgid, gfw_id=None)

logger.debug('Initiate report generation for all times and places')
report_name_template = 'Total Observed Fishing Effort in {}, {}'
for index, row in gdf_zones.iterrows():
    for date_pair in date_pairs:
        # print(row['geoname'], date_pair[0].strftime('%Y-%m-%d'))
        report_name = report_name_template.format(row.geoname, date_pair[0].year)
        req_data = build_req_data_from_row(report_name, date_pair, row)
        # req_data['geometry']['geometry'] = None
        # pprint(req_data)
        r = requests.post(INITIATE_REPORT_ENDPOINT, headers=INITIATE_REPORT_HEADERS, data=json.dumps(req_data))
        r.raise_for_status()
        resp_body = r.json()
        # mrgid, geoname, year, id, url, zip, csv, value
        df_reports.loc[len(df_reports.index)] = [
            row.mrgid, row.geoname, date_pair[0].year, resp_body['id'], None, None, None, None,
        ]
        time.sleep(3)
        break

time.sleep(5)

logger.debug('Retrieve report URLs and download results')
for index, row in df_reports.iterrows():
    r = requests.get(RETRIEVE_URL_ENDPOINT.format(row.id), headers=RETRIEVE_URL_HEADERS)
    r.raise_for_status()
    resp_body = r.json()
    url = resp_body['url']
    df_reports.loc[index, 'url'] = url
    zip = os.path.join(os.getenv('DOWNLOAD_DIR'),row.id+'.zip')
    df_reports.loc[index, 'zip'] = zip
    urllib.request.urlretrieve(url, zip)
    time.sleep(1)
    break
# 
# subsequently, for each report id, we need to:
# (optional: inquire as to status of report)
# submit a GET api request to gfw
# store response, specifically download url
# 
# download report (zip) file
# store with an appropriate name
# unzip file
# load csv to dataframe
# calculate (sum) total effort hours
# store that figure as associated with that year-eez and/or report id
# 
# ultimately, once we have a figure for each year-eez
# upload data to carto