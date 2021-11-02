var mouths = ee.FeatureCollection("projects/resource-watch-gee/ocean-watch/river-mouths"),
    rivers = ee.FeatureCollection("projects/resource-watch-gee/ocean-watch/river-network");

// filter full set of river mouths down to only those "corresponding to"
// non-tributary exorheic rivers, as defined by hydrorivers;
// also grabbing only the most downstream river segment thereof

var testing = true;

var targetRivers = rivers
    .filter(ee.Filter.eq('ORD_CLAS',1))
    .filter(ee.Filter.eq('ENDORHEIC',0))
    .filter(ee.Filter.lte('ORD_FLOW', 5))
    .filter(ee.Filter.equals('MAIN_RIV', null, 'HYRIV_ID', null));

if(testing){
  targetRivers = targetRivers
      .filter(ee.Filter.lte('ORD_FLOW', 1));
}

print(targetRivers);

// build filter for reducing set of river mouths
// Define a spatial filter, with distance 100 km.
var distFilter = ee.Filter.withinDistance({
  distance: 100000,
  leftField: '.geo',
  rightField: '.geo',
  maxError: 100
});

var distSaveBest = ee.Join.saveBest({
  matchKey: 'mouth_point',
  measureKey: 'distance',
  outer: false
});

var spatialJoined = distSaveBest.apply(targetRivers, mouths, distFilter);

// replace the river line segments with the corresponding points,
// but retain all (meaningful) metadata from both features
var targetMouths = spatialJoined.map(function(feature){
  var riverProperties = feature.toDictionary();
  var point = ee.Feature(feature.get('mouth_point')).set(riverProperties);
  point = point.set('HYRIV_ID', ee.String(point.get('HYRIV_ID')));
  point = point.set('MAIN_RIV', ee.String(point.get('MAIN_RIV')));
  point = point.set('HYBAS_L12', ee.String(point.get('HYBAS_L12')));
  var selectProperties = point.propertyNames()
      .filter(ee.Filter.neq('item', 'any'))
      .filter(ee.Filter.neq('item', 'label'))
      .filter(ee.Filter.neq('item', 'mouth_point'));
  var target = point.select(selectProperties);
  return target;
});

if(!testing){
  Export.table.toDrive({
    collection: targetMouths,
    description: 'owCalcs_targetRiverMouths_toDrive',
    folder: 'wri', 
    fileNamePrefix: 'target-river-mouths', 
    fileFormat: 'shp',
    selectors: null
  });
}
else{
  print(targetMouths);
  Map.addLayer(mouths, null, "river mouths");
  // Map.addLayer(rivers, null, "rivers");
  Map.addLayer(targetRivers, null, "target rivers");
}