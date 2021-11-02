var merit = ee.Image("MERIT/Hydro/v1_0_1"),
    test_geometry = 
    /* color: #98ff00 */
    /* shown: false */
    /* displayProperties: [
      {
        "type": "rectangle"
      }
    ] */
    ee.Geometry.Polygon(
        [[[-124.43503217972783, 47.27159183940336],
          [-124.43503217972783, 46.54734195251303],
          [-123.61105757035283, 46.54734195251303],
          [-123.61105757035283, 47.27159183940336]]], null, false),
    world = 
    /* color: #0b4a8b */
    /* shown: false */
    /* displayProperties: [
      {
        "type": "rectangle"
      }
    ] */
    ee.Geometry.Polygon(
        [[[-139.749993871936, 81.93064926017728],
          [-139.749993871936, -68.6372055066505],
          [156.9687531105789, -68.6372055066505],
          [156.9687531105789, 81.93064926017728]]], null, false);

// extract river mouth locations as points from merit hydro

var testing = true;

var mouth_pixels = merit.select('dir').eq(0).and(merit.select('wth').gt(0)).rename('is mouth');
// extract points from the identified river mouth pixels
var mouth_pixels = mouth_pixels.updateMask(mouth_pixels);
var mouth_pixels = mouth_pixels.addBands(mouth_pixels);
var mouth_points = mouth_pixels.reduceToVectors({
  reducer: ee.Reducer.anyNonZero(),
  geometry: testing ? test_geometry : world,
  scale: 90,
  geometryType: 'centroid',
  eightConnected: false,
  // labelProperty: 'zone',
  // crs: nl2012.projection(),
  maxPixels: 1e13,
});

if(testing) {
  print(mouth_points);

  var vizParams = {
    min: 0,
    max: 1,
    palette: ['ffffff','000000']
  };
  
  // Map.setCenter(90.301, 23.052, 10);
  
  Map.addLayer(mouth_pixels.select([0]), vizParams, "mouths");
}
else{
  Export.table.toAsset({
    collection: mouth_points,
    description:'owCalcs_riverMouthPoints_toAsset',
    assetId: 'projects/resource-watch-gee/ocean-watch/river-mouths'
  });
}