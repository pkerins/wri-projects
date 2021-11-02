curl --location -g --request POST 'https://gateway.api.globalfishingwatch.org//v1/4wings/report?spatialResolution=low&temporalResolution=yearly&groupBy=flag&datasets[0]=public-global-fishing-effort:v20201001&date-range=2020-01-01T00:00:00.000Z,2021-09-01T00:00:00.000Z&format=json' \
--header 'Authorization: Bearer eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCIsImtpZCI6ImtpZEtleSJ9.eyJkYXRhIjp7Im5hbWUiOiI0d2luZ3MiLCJhcHBsaWNhdGlvbk5hbWUiOiJXUkkiLCJpZCI6MTIsInR5cGUiOiJhcHBsaWNhdGlvbiJ9LCJpYXQiOjE2Mjg3NTE0MDgsImV4cCI6MTc4NjQzMTQwOCwiYXVkIjoiZ2Z3IiwiaXNzIjoiZ2Z3In0.BDLq4f4kiAIuaHosOGXQW4Mo6bprxh50v6CataI61HZckiTJAcQ9iZ8SRZ8VENb1AoqiOHlrN4WcmeqwcH9ATN2US8IxxWhwKj87C7jYfJh2p9YU_D8JhVwtK4UAPS9LWFfnrXLCVIwo_QqZdKiwxoFwfJn2YEiO10JI4MRkDDuae0I38r1olbWofz6nEYLW-tOBNG1suOPhqe3IzNFf4CmjnSIvJVoB4HrVRFgpuVrt0xNSB6XYz46hMLyuFErVtiX96gwMDaRIveNC4dEQoaiBj465LUT6FuCxGzR4vbmdBFO_46ngktwwkGvjFWeyw5ueXsVvteKUUO2hNWBMUIlHnPZJPJmMGKVlkI0iLrLOC1FmY9P2lC-pwveSRXTBNLu842HgFzpsX8A4nogSwJgDAqwc6mNHM3osZTaGyO7dNWzw7BI3kVt43Zp6oRwZPSdIavIIlzXWrC-9eozKt5S2cG0dU8o8xg0NDtNpl3eo0EZgON7QsuSTo8ofinzY' \
--header 'Content-Type: application/json' \
--data-raw '{
    "geojson": {
        "type": "Polygon",
        "coordinates": [
          [
            [
              -180,
              -85.051128
            ],
            [
              180,
              -85.051128
            ],
            [
              180,
              85.051128
            ],
            [
              -180,
              85.051128
            ],
            [
              -180,
              -85.051128
            ]
          ]
        ]
      }
}' -o file.json