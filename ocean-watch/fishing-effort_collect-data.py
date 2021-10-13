import logging
from cartoframes.auth import set_default_credentials
from cartoframes import read_carto, to_carto
import pandas as pd
from pandas.errors import EmptyDataError
import geopandas as gpd
from datetime import date
from pprint import pprint
import json
import time
# import dateutil.relativedelta
import requests
from requests.exceptions import HTTPError
import urllib.request
import zipfile
from pathlib import Path
# import xml.etree.ElementTree as ET
# import math
# import concurrent.futures

import contextlib

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
dataset_name = 'com_030d_fishing_effort_by_zone'

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

WORKING_DIR = os.path.join(os.getenv('DOWNLOAD_DIR'), 'gfw-api-data')
Path(WORKING_DIR).mkdir(parents=True, exist_ok=True)

logger.debug('Retrieve polygons from Carto')
# retrieve polygons from carto
eez_table = 'com_011_rw1_maritime_boundaries_edit'
# dataset includes following types:
# '12NM', '24NM', '200NM', 'Overlapping claim', 'Joint regime'
# the final three are of potential relevance here
# collect the data for them all, but maintain the distinction for later ease
gdf_zones = read_carto("SELECT *, ST_AsGeoJSON(the_geom) AS the_geom_geojson FROM com_011_rw1_maritime_boundaries_edit WHERE pol_type IN ('Overlapping claim','200NM','Joint regime')",
        index_col='cartodb_id')
gdf_zones = gdf_zones.astype({'mrgid':'int','mrgid_ter1':'int','mrgid_sov1':'int',
        'mrgid_eez':'int',})
gdf_zones['json'] = gdf_zones.the_geom.to_json()

# create set of pairs of dates to loop through
date_pairs = [(date(year,1,1), date(year+1,1,1)) for year in range(2012, 2022)]

# create object to track api activity & results
# mrgid, geoname, year, id, url, zip, csv, value
# needed from original table: geoname, pol_type, iso_ter1, iso_sov1, iso_ter2, iso_sov2, iso_ter3, iso_sov3
col_type_dict = {
    'mrgid':'int',
    'geoname':'str',
    'pol_type':'str',
    'iso_ter1':'str',
    'iso_sov1':'str',
    'iso_ter2':'str',
    'iso_sov2':'str',
    'iso_ter3':'str',
    'iso_sov3':'str',
    'year':'int',
    'id':'str',
    'url':'str',
    'zip':'str',
    'csv':'str',
    'value':'float',
}
df_reports = pd.DataFrame({c: pd.Series(dtype=t) for c, t in col_type_dict.items()})

logger.info('Define functions for submitting API requests and handling responses')
def build_req_data_postgis_json(report_name, date_pair, geom_geojson,  
        value=None, geoname=None, mrgid=None, gfw_id=None):
    # construct data object
    req_data = {}
    req_data['name'] = report_name
    req_data['geometry'] = {}
    req_data['geometry']['type'] = 'MultiPolygon'
    req_data['geometry']['properties'] = {}
    if value is not None: req_data['geometry']['properties']['value'] = value
    if geoname is not None: req_data['geometry']['properties']['geoname'] = geoname
    if mrgid is not None: req_data['geometry']['properties']['mrgid'] = mrgid
    if gfw_id is not None: req_data['geometry']['properties']['gfw_id'] = gfw_id
    json_dict = json.loads(geom_geojson)
    # if len(json_dict['features']) > 1: 
    #     print('warning')
        # raise Exception('not sure if we want this or will encounter')
    req_data['geometry']['geometry'] = json_dict
    # req_data['geometry']['geometry'] = json_dict['features'][0]['geometry']
    req_data['type'] = 'detail'
    req_data['timeGroup'] = 'none'
    req_data['filters'] = ['']
    req_data['datasets'] = ['public-global-fishing-tracks:latest']
    date_format = '%Y-%m-%d'
    req_data['dateRange'] = [date_pair[0].strftime(date_format), date_pair[1].strftime(date_format)]
    return req_data

logger.info('Initiate report generation for all times and places')
report_name_template = 'Total Observed Fishing Effort in {}, {}'
for index, row in gdf_zones.iterrows():
    logger.debug('Request reports for zone: ' + row.geoname)
    for date_pair in date_pairs:
        # print(row['geoname'], date_pair[0].strftime('%Y-%m-%d'))
        report_name = report_name_template.format(row.geoname, date_pair[0].year)
        # req_data = build_req_data_from_row(report_name, date_pair, row)
        req_data_postgis = build_req_data_postgis_json(report_name, date_pair, row.the_geom_geojson, 
                value=row.geoname, geoname=row.geoname, mrgid=row.mrgid, gfw_id=None)
        # req_data_pandas = build_req_data_pandas_json(report_name, date_pair, row.json, 
        #         value=row.geoname, geoname=row.geoname, mrgid=row.mrgid, gfw_id=None)
        with open(os.path.join(WORKING_DIR, 'postgis.json'), 'w', encoding='utf-8') as f:
            json.dump(req_data_postgis, f, ensure_ascii=False, indent=4)
        # with open(os.path.join(WORKING_DIR, 'pandas.json'), 'w', encoding='utf-8') as f:
        #     json.dump(req_data_pandas, f, ensure_ascii=False, indent=4)

        # req_data['geometry']['geometry'] = None
        # pprint(req_data)
        r = requests.post(INITIATE_REPORT_ENDPOINT, headers=INITIATE_REPORT_HEADERS, data=json.dumps(req_data_postgis))
        try:
            r.raise_for_status()
        except HTTPError as e:
            logger.error('Failed report generation request for: ' + report_name)
            resp_body = None
        else:
            resp_body = r.json()
        finally:
            df_reports.loc[len(df_reports.index)] = [
                row.mrgid, row.geoname, row.pol_type,
                row.iso_ter1, row.iso_sov1, row.iso_ter2, row.iso_sov2, row.iso_ter3, row.iso_sov3, 
                date_pair[0].year, (None if resp_body is None else resp_body['id']), None, None, None, None,
            ]
            time.sleep(1)
        # break
    # break

time.sleep(30)

logger.info('Retrieve report URLs and download results')
for index, row in df_reports.iterrows():
    if row.id is None:
        continue
    try:
        r = requests.get(RETRIEVE_URL_ENDPOINT.format(row.id), headers=RETRIEVE_URL_HEADERS)
        r.raise_for_status()
    except HTTPError as e:
        logger.error('Failed report URL retrieval request for: ' + row.geoname)
        continue
    resp_body = r.json()
    url = resp_body['url']
    df_reports.loc[index, 'url'] = url
    zip = os.path.join(WORKING_DIR,row.id+'.zip')
    df_reports.loc[index, 'zip'] = zip
    urllib.request.urlretrieve(url, zip)
    time.sleep(8)
    # break

logger.info('Unzip and organize retrieved data')
for index, row in df_reports.iterrows():
    if row.zip is None:
        continue
    with zipfile.ZipFile(row.zip, 'r') as zip_ref:
        zip_list = zip_ref.namelist()
        for f in zip_list:
            if f.endswith('.csv'):
                zip_ref.extract(f, path=WORKING_DIR)
                unzipped_csv = os.path.join(WORKING_DIR, f)
                renamed_csv = os.path.join(WORKING_DIR, row.geoname.replace(' ','-').replace('/','|')+'_'+str(row.year)+'.csv')
                os.rename(unzipped_csv, renamed_csv)
                df_reports.loc[index, 'csv'] = renamed_csv
                # break
    # break

logger.info('Load data, calculate statistics, and record results')
for index, row in df_reports.iterrows():
    if row.csv is None:
        continue
    try:
        df_entry = pd.read_csv(row.csv)
    except EmptyDataError as e:
        logger.debug('No fishing records for ' + row.geoname + ' in ' + str(row.year))
        df_reports.loc[index, 'value'] = 0
        continue
    sum = df_entry['Fishing hours'].sum()
    df_reports.loc[index, 'value'] = sum
    # break

logger.info('Store results locally and upload them to Carto')

# record reports that failed, whose reports are thus missing
df_failures = df_reports[df_reports['value'].isnull()]
if len(df_failures) > 0:
    failures_csv = os.path.join(WORKING_DIR, 'gfw-api_fishing-effort_failures.csv')
    with contextlib.suppress(FileNotFoundError):
        os.remove(failures_csv)
    df_failures.to_csv(failures_csv, header=True, index=False, )

# do not retain local paths or file url (which ultimately derives
# from api access, and is probably ephemeral anyway)
df_reports.drop(columns=['url','zip','csv'], inplace=True)
reports_csv = os.path.join(WORKING_DIR, 'gfw-api_fishing-effort.csv')
with contextlib.suppress(FileNotFoundError):
    os.remove(reports_csv)
df_reports.to_csv(reports_csv, header=True, index=False, )

to_carto(df_reports, dataset_name, if_exists='replace')