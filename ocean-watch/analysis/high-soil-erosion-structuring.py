# Surface areas have already been calculated for areas with high soil erosion prevalence
# and forest loss (per-year and cumulatively) for the full available time series.
# For each, Google Earth Engine output results in so-called "short" form, with one row
# for every territory and one column for each calculated attribute.
# This script combines and restructures that data to match requested Vizzuality template
# for all Ocean Watch widgets.

# Author: Peter Kerins
# Created: 28 Jul 2021
# Environment: jupyterlab 

# generation of data: https://code.earthengine.google.com/78c04b071939eeddfcdc40f3dae2153c
# files downloaded manually:
#     - high-soil-erosion-areas-by-territory_gadm.csv

# imports
import os
import pandas as pd

# paths to input data objects
data_folder = '/mnt/c/Users/PKerins.Local/World Resources Institute/OceanData - Documents/modified_data/soil-erosion-forest-loss'
calcs = os.path.join(data_folder, 'high-soil-erosion-areas-by-territory_gadm.csv')

# read data into memory for manipulation
# note that totalArea is excluded from all but one file, since this figure is static year to year, ie redundant
df_calcs = pd.read_csv(calcs).drop(columns=['system:index','.geo']).sort_values('GID_0').reset_index(drop=True)

# function for restructuring data into appropriate arrangement and format
def restructure(df):
    df_2 = pd.melt(df, id_vars=['GID_0','NAME_0']).sort_values('GID_0')
    df_2['value'] = df_2['value'] / 1000000
    df_2.loc[df_2['variable']=='area_2002', 'date'] = '2002'
    df_2.loc[df_2['variable']=='area_2007', 'date'] = '2007'
    df_2.loc[df_2['variable']=='area_2012', 'date'] = '2012'
    df_2.loc[df_2['variable']=='area_2017', 'date'] = '2017'
    df_2.loc[df_2['variable']=='area_2020', 'date'] = '2020'
    df_2 = df_2.assign(variable='highsep')
    # df_2.loc[df_2['variable']=='area_2007', 'variable'] = 'highsep_2002'
    
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
path_output = os.path.join(data_folder, 'ow_high-soil-erosion-prevalence.csv')
df_complete.to_csv(path_output,index=False)