import os
import requests
import json

INITIATE_REPORT_ENDPOINT = 'https://gateway.api.globalfishingwatch.org//v1/4wings/report?spatialResolution=low&temporalResolution=yearly&groupBy=flag&datasets[0]=public-global-fishing-effort:v20201001&date-range=2020-01-01T00:00:00.000Z,2021-09-01T00:00:00.000Z&format=json'

INITIATE_REPORT_HEADERS = {
    'Content-Type':'application/json',
    'Authorization':os.getenv('GFW_API_KEY')
}

request_data_string = '{"geojson": {"type": "Polygon","coordinates": [[[-180,-85.051128],[180,-85.051128],[180,85.051128],[-180,85.051128], [-180,-85.051128] ] ] } }'
request_data = json.loads(request_data_string)
r = requests.post(INITIATE_REPORT_ENDPOINT, headers=INITIATE_REPORT_HEADERS, data=request_data)
print(r)