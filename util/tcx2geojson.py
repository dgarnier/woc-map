import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from sys import argv
import os

# this is for parsing activity files
# but 
def tcx_to_geojson(filename: str, course: bool = True):
    root = ET.parse(filename).getroot()
    # wkt = "LINESTRING M ("
    #wkt = "MULTILINESTRING M ("
    name = os.path.splitext(os.path.basename(filename))[0]

    geojson_end = f',\n\t"properties": {{\n\t\t"name": "{name}"\n\t}}\n}}'
    geojson = '{\n\t"type": "Feature",\n\t"geometry": {\n\t\t"type": "MultiLineString",\n\t\t"coordinates": [\n'
    offset = None
    hb = None
    if not course:
        for _ai, a in enumerate(root.findall('t:Activities/t:Activity', {'t': "http://www.garmin.com/xmlschemas/TrainingCenterDatabase/v2"})):
            for _li, l in enumerate(a.findall('t:Lap', {'t': "http://www.garmin.com/xmlschemas/TrainingCenterDatabase/v2"})):
                _xym = ""
                for _pti, pt in enumerate(l.findall('t:Track/t:Trackpoint', {'t': "http://www.garmin.com/xmlschemas/TrainingCenterDatabase/v2"})):
                    _hb = pt.findtext('t:HeartRateBpm/t:Value', namespaces={
                                    't': "http://www.garmin.com/xmlschemas/TrainingCenterDatabase/v2"})
                    if _hb is not None:
                        hb = _hb
                    pos = pt.find('t:Position', {
                                't': "http://www.garmin.com/xmlschemas/TrainingCenterDatabase/v2"})
                    if pos is None:
                        continue
                    timestamp = int(datetime.strptime(pt.findtext(
                        '{http://www.garmin.com/xmlschemas/TrainingCenterDatabase/v2}Time'), '%Y-%m-%dT%H:%M:%S.%fZ').replace(tzinfo=timezone.utc).timestamp())
                    lat = pos.findtext("t:LatitudeDegrees", namespaces={
                                    't': "http://www.garmin.com/xmlschemas/TrainingCenterDatabase/v2"})
                    lon = pos.findtext("t:LongitudeDegrees", namespaces={
                                    't': "http://www.garmin.com/xmlschemas/TrainingCenterDatabase/v2"})
                    if offset is None:
                        # starttime = timestamp
                        offset = timestamp
                    timestamp -= offset
                    endtime = timestamp
                    out = timestamp
                    # out = hb
                    _xym += f"{lon} {lat} {out}, "
                if _xym:
                    wkt += f"({_xym[:-2]}), "
        wkt = wkt[:-2] + ")"
    else:
        for _ci, c in enumerate(root.findall('t:Courses/t:Course', {'t': "http://www.garmin.com/xmlschemas/TrainingCenterDatabase/v2"})):
            _xy = ""
            for _pti, pt in enumerate(c.findall('t:Track/t:Trackpoint', {'t': "http://www.garmin.com/xmlschemas/TrainingCenterDatabase/v2"})):
                # timestamp = int(datetime.strptime(pt.findtext(
                #    '{http://www.garmin.com/xmlschemas/TrainingCenterDatabase/v2}Time'), '%Y-%m-%dT%H:%M:%SZ').replace(tzinfo=timezone.utc).timestamp())
                pos = pt.find('t:Position', {
                    't': "http://www.garmin.com/xmlschemas/TrainingCenterDatabase/v2"})
                if pos is None:
                    continue
                lat = pos.findtext("t:LatitudeDegrees", namespaces={
                    't': "http://www.garmin.com/xmlschemas/TrainingCenterDatabase/v2"})
                lon = pos.findtext("t:LongitudeDegrees", namespaces={
                    't': "http://www.garmin.com/xmlschemas/TrainingCenterDatabase/v2"})
                # if offset is None:
                    # starttime = timestamp
                #    offset = timestamp
                # timestamp -= offset
                # endtime = timestamp
                # out = timestamp
                # out = hb
                # _xym += f"{lon} {lat} {out}, "
                # if _pti % 5 == 0:
                #    _xy += f"\n\t\t\t\t"
                _xy += f"\n\t\t\t\t[{lon}, {lat}], "
            if _xy:
                geojson += f"\t\t\t[{_xy[:-2]}\n\t\t\t],\n"
        geojson = geojson[:-2] + "\n\t\t]\n\t}"+geojson_end
    # return wkt, starttime, endtime
    return geojson

if __name__ == '__main__':
    import os
    for filename in argv[1:]:
        json = tcx_to_geojson(filename, course=True)
        json_file = os.path.splitext(filename)[0]+'.geojson'
        with open(json_file, 'w', encoding='utf-8') as f:
            f.write(json)
