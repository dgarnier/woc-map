#!/usr/bin/env python3
import os
from tcx2geojson import tcx_to_geojson


routes = [
    ("_B_lackLivesMatter", "https://ridewithgps.com/routes/32977936"),
    ("B_l_ackLivesMatter", "https://ridewithgps.com/routes/32978116"),
    ("Bl_a_ckLivesMatter", "https://ridewithgps.com/routes/32978288"),
    ("Bla_c_kLivesMatter", "https://ridewithgps.com/routes/32979113"),
    ("Blac_k_LivesMatter", "https://ridewithgps.com/routes/33078801"),
    ("Black_L_ivesMatter", "https://ridewithgps.com/routes/33078890"),
    ("BlackL_i_vesMatter", "https://ridewithgps.com/routes/33176643"),
    ("BlackLi_v_esMatter", "https://ridewithgps.com/routes/32979727"),
    ("BlackLiv_e_sMatter", "https://ridewithgps.com/routes/33076433"),
    ("BlackLive_s_Matter", "https://ridewithgps.com/routes/33076537"),
    ("BlackLives_M_atter", "https://ridewithgps.com/routes/33076805"),
    ("BlackLivesM_a_tter", "https://ridewithgps.com/routes/33076918"),
    ("BlackLivesMa_t_ter", "https://ridewithgps.com/routes/33077009"),
    ("BlackLivesMat_t_er", "https://ridewithgps.com/routes/33077220"),
    ("BlackLivesMatt_e_r", "https://ridewithgps.com/routes/33077727"),
    ("BlackLivesMatte_r_", "https://ridewithgps.com/routes/33077542"),
]

for name, route in routes:
    os.system(f'curl -o {name}.tcx {route}.tcx')
    json = tcx_to_geojson('{name}.tcx', course=True)
    # might make a big single geojson file
    with open(f'{name}.geojson', 'w') as f:
        f.write(json,  encoding='utf-8')
