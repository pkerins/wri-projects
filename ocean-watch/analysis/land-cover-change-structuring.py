# Land cover change areas have already been calculated for several types of transitions.
# Google Earth Engine output several congruent csv files corresponding to different years.
# This script combines and restructures that data to match requested Vizzuality template
# for all Ocean Watch widgets.

# Author: Peter Kerins
# Created: 10 Jun 2021
# Environment: jupyterlab 

# generation of data: https://code.earthengine.google.com/1a106a75689826e6bf7283b7d7c7f6f5
# files downloaded manually:
#     - land-cover-change-areas-by-territory_2015-2016_gadm.csv
#     - land-cover-change-areas-by-territory_2016-2017_gadm.csv
#     - land-cover-change-areas-by-territory_2017-2018_gadm.csv
#     - land-cover-change-areas-by-territory_2018-2019_gadm.csv

# imports
import os
import pandas as pd

# paths to input data objects
data_folder = '/mnt/c/Users/PKerins.Local/World Resources Institute/OceanData - Documents/modified_data/land-cover-change'
calcs_16 = os.path.join(data_folder, 'land-cover-change-areas-by-territory_2015-2016_gadm.csv')
calcs_17 = os.path.join(data_folder, 'land-cover-change-areas-by-territory_2016-2017_gadm.csv')
calcs_18 = os.path.join(data_folder, 'land-cover-change-areas-by-territory_2017-2018_gadm.csv')
calcs_19 = os.path.join(data_folder, 'land-cover-change-areas-by-territory_2018-2019_gadm.csv')

# read data into memory for manipulation
# note that totalArea is excluded from all but one file, since this figure is static year to year, ie redundant
df_16 = pd.read_csv(calcs_16).drop(columns=['system:index','.geo']).sort_values('GID_0').reset_index(drop=True)
df_17 = pd.read_csv(calcs_17).drop(columns=['system:index','.geo','totalArea']).sort_values('GID_0').reset_index(drop=True)
df_18 = pd.read_csv(calcs_18).drop(columns=['system:index','.geo','totalArea']).sort_values('GID_0').reset_index(drop=True)
df_19 = pd.read_csv(calcs_19).drop(columns=['system:index','.geo','totalArea']).sort_values('GID_0').reset_index(drop=True)

# function for restructuring data into appropriate arrangement and format
def restructure(df, year):
    df_2 = pd.melt(df, id_vars=['GID_0','NAME_0']).sort_values('GID_0')
    df_2['value'] = df_2['value'] / 1000000
    
    col_section = ['catchments' for x in range(0,len(df_2))]
    col_widget = ['land cover change' for x in range(0,len(df_2))]
    col_unit = ['sq. km' for x in range(0, len(df_2))]
    col_date = [year for x in range(0,len(df_2))]
    
    df_2['section'] = col_section
    df_2['widget'] = col_widget
    df_2['unit'] = col_unit
    df_2['date'] = col_date
    
    return df_2[['section','widget','GID_0','NAME_0','variable','date','value','unit']]

# apply function to all input files and append them to form a single, complete dataframe
df_complete = restructure(df_16, 2016).append(
                restructure(df_17, 2017), ignore_index=True).append(
                restructure(df_18, 2018), ignore_index=True).append(
                restructure(df_19, 2019), ignore_index=True).sort_values(['GID_0','variable','date',])

# correct data in final structure

# totalArea is not associated with a specific year, so set to none
df_complete.loc[(df_complete['variable']=='totalArea'), 'date'] = None

# specify which widget each row corresponds to, as a function of variable

# totalArea variable does not belong to one widget, but might be used for several
mask = df_complete['variable']=='totalArea'
df_complete.loc[mask, 'widget'] = 'land cover change: misc'

# desertification widget includes various land cover types which turned to bare ground
mask = df_complete['variable'].isin(['cropBare','forestBare','vegBare','wetBare'])
df_complete.loc[mask, 'widget'] = 'land cover change: desertification'

# deforestation and crop expanstion widget is about forest to/from crop
mask = df_complete['variable'].isin(['forestCrop','cropForest'])
df_complete.loc[mask, 'widget'] = 'land cover change: deforestation and crop expansion'

# urbanization widget is about any land type (with restrictions) turning into urban land
mask = df_complete['variable']=='anyUrban'
df_complete.loc[mask, 'widget'] = 'land cover change: urbanization'

# export final output
path_output = os.path.join(data_folder, 'ow_land-cover-change.csv')
df_complete.to_csv(path_output,index=False)