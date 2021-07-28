# Surface areas have already been calculated for areas with high soil erosion prevalence
# and forest loss (per-year and cumulatively) for the full available time series.
# For each, Google Earth Engine output results in so-called "short" form, with one row
# for every territory and one column for each calculated attribute.
# This script combines and restructures that data to match requested Vizzuality template
# for all Ocean Watch widgets.

# Author: Peter Kerins
# Created: 28 Jul 2021
# Environment: jupyterlab 

# generation of data: https://code.earthengine.google.com/9d7e32d1409dfee9d1d0f81f30688cdb
# files downloaded manually:
#     - forest-loss-areas-by-territory_gadm.csv

# imports
import os
import pandas as pd

# paths to input data objects
data_folder = '/mnt/c/Users/PKerins.Local/World Resources Institute/OceanData - Documents/modified_data/soil-erosion-forest-loss'
calcs = os.path.join(data_folder, 'forest-loss-areas-by-territory_gadm.csv')

# read data into memory for manipulation
# note that totalArea is excluded from all but one file, since this figure is static year to year, ie redundant
df_calcs = pd.read_csv(calcs).drop(columns=['system:index','.geo']).sort_values('GID_0').reset_index(drop=True)

# function for restructuring data into appropriate arrangement and format
def restructure(df):
    df_2 = pd.melt(df, id_vars=['GID_0','NAME_0']).sort_values('GID_0')
    df_2['value'] = df_2['value'] / 1000000
    df_2 = df_2.assign(date=df_2['variable'].str.slice(start=-4))

    df_2.loc[df_2['variable'].str.startswith('cumulative'), 'variable'] = 'cumulative_loss'
    df_2.loc[df_2['variable'].str.startswith('loss'), 'variable'] = 'year_loss'
    
    col_section = ['catchments' for x in range(0,len(df_2))]
    col_widget = ['soil erosion and forest loss' for x in range(0,len(df_2))]
    col_unit = ['sq. km' for x in range(0, len(df_2))]
    
    df_2['section'] = col_section
    df_2['widget'] = col_widget
    df_2['unit'] = col_unit
    
    return df_2[['section','widget','GID_0','NAME_0','variable','date','value','unit']]

# apply function to all input files and append them to form a single, complete dataframe
df_complete = restructure(df_calcs).sort_values(['GID_0','variable','date',], ignore_index=True)

# export final output
path_output = os.path.join(data_folder, 'ow_tree-cover-loss.csv')
df_complete.to_csv(path_output,index=False)