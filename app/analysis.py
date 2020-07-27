# analysis.py
from os.path import dirname, relpath, join
import numpy as np
import numba as nb
import geojson as gj
import polyline as pl
from scipy.spatial import ConvexHull


nb.config.THREADING_LAYER = 'tbb'


def route_names():
    _route_names = [
        "_B_lackLivesMatter",
        "B_l_ackLivesMatter",
        "Bl_a_ckLivesMatter",
        "Bla_c_kLivesMatter",
        "Blac_k_LivesMatter",
        "Black_L_ivesMatter",
        "BlackL_i_vesMatter",
        "BlackLi_v_esMatter",
        "BlackLiv_e_sMatter",
        "BlackLive_s_Matter",
        "BlackLives_M_atter",
        "BlackLivesM_a_tter",
        "BlackLivesMa_t_ter",
        "BlackLivesMat_t_er",
        "BlackLivesMatt_e_r",
        "BlackLivesMatte_r_",
    ]
    return _route_names


def read_routes_numpy(dirpath='static/routes'):
    # convert to pure python types for numba
    filepath = dirname(relpath(__file__))
    routes = [dict(gj.load(open(join(filepath,
                                     f'{dirpath}/{name}.geojson'),
                                'r'))
                   ) for name in route_names()]

    for route in routes:
        mls = [np.array(lonlat) for lonlat in route['geometry']['coordinates']]
        east = np.max([np.max(ls[:, 0]) for ls in mls])
        west = np.min([np.min(ls[:, 0]) for ls in mls])
        north = np.max([np.max(ls[:, 1]) for ls in mls])
        south = np.min([np.min(ls[:, 0]) for ls in mls])
        bbox = np.array([west, south, east, north])
        route['mls'] = mls
        route['bbox'] = bbox
        route['minbox'] = find_rbbox(mls)

    return routes


def obbox(mls):
    # find bounding box for multilinestring
    east = np.max([np.max(ls[:, 0]) for ls in mls])
    west = np.min([np.min(ls[:, 0]) for ls in mls])
    north = np.max([np.max(ls[:, 1]) for ls in mls])
    south = np.min([np.min(ls[:, 0]) for ls in mls])
    bbox = np.array([west, south, east, north])
    return bbox


def qhull(mls):
    lls = np.concatenate(mls, axis=0)
    hull = lls[ConvexHull(lls).vertices]
    return hull


@nb.jit
def bbox(mls):
    hull = qhull(mls)
    east = hull[:, 0].max()
    west = hull[:, 0].min()
    north = hull[:, 1].max()
    south = hull[:, 1].min()

    bbox = np.array([west, south, east, north])
    return bbox, (east-west)*(north-south)


@nb.jit
def bbox_pts(hull):
    # area not adjusted.. in sqr degrees
    E = hull[:, 0].max()
    W = hull[:, 0].min()
    N = hull[:, 1].max()
    S = hull[:, 1].min()
    A = [W, S]
    B = [W, N]
    C = [E, N]
    D = [E, S]
    bbox = np.array([A, B, C, D])
    area = (N - S) * (E - W)
    return bbox, area


@nb.jit
def rot_matrix(rm, theta):
    c, s = np.cos(theta), np.sin(theta)
    rm[0, 0] = c
    rm[0, 1] = -s
    rm[1, 0] = s
    rm[1, 1] = c


@nb.jit
def bbox_angle(hull, R):
    hullr = hull @ R
    bboxr, area = bbox_pts(hullr)
    bbox = bboxr @ R.T
    return bbox, area


@nb.jit()
def find_rbbox_from_hull(hull):
    rm = np.array([[1.0, 0.0], [0.0, 1.0]])
    s = hull[0]-hull[-1]
    rot_matrix(rm, np.arctan2(s[1], s[0]))
    bbox, area = bbox_angle(hull, rm)
    for i in range(hull.shape[0]-1):
        s = hull[i+1] - hull[i]
        rot_matrix(rm, np.arctan2(s[1], s[0]))
        nbbox, narea = bbox_angle(hull, rm)
        if narea < area:
            area = narea
            bbox = nbbox
    return bbox


def find_rbbox(mls):
    hull = qhull(mls)
    return find_rbbox_from_hull(hull)


def minimum_bounding_rectangle(points):
    """
    Find the smallest bounding rectangle for a set of points.
    Returns a set of points representing the corners of the bounding box.

    :param points: an nx2 matrix of coordinates
    :rval: an nx2 matrix of coordinates
    """
    # from scipy.ndimage.interpolation import rotate
    pi2 = np.pi/2.

    # get the convex hull for the points
    hull_points = points[ConvexHull(points).vertices]

    # calculate edge angles
    edges = np.zeros((len(hull_points)-1, 2))
    edges = hull_points[1:] - hull_points[:-1]

    angles = np.zeros((len(edges)))
    angles = np.arctan2(edges[:, 1], edges[:, 0])

    angles = np.abs(np.mod(angles, pi2))
    angles = np.unique(angles)

    # find rotation matrices
    rotations = np.vstack([
        np.cos(angles),
        np.cos(angles-pi2),
        np.cos(angles+pi2),
        np.cos(angles)]).T
    rotations = rotations.reshape((-1, 2, 2))

    # apply rotations to the hull
    rot_points = np.dot(rotations, hull_points.T)

    # find the bounding points
    min_x = np.nanmin(rot_points[:, 0], axis=1)
    max_x = np.nanmax(rot_points[:, 0], axis=1)
    min_y = np.nanmin(rot_points[:, 1], axis=1)
    max_y = np.nanmax(rot_points[:, 1], axis=1)

    # find the box with the best area
    areas = (max_x - min_x) * (max_y - min_y)
    best_idx = np.argmin(areas)

    # return the best box
    x1 = max_x[best_idx]
    x2 = min_x[best_idx]
    y1 = max_y[best_idx]
    y2 = min_y[best_idx]
    r = rotations[best_idx]

    rval = np.zeros((4, 2))
    rval[0] = np.dot([x1, y2], r)
    rval[1] = np.dot([x2, y2], r)
    rval[2] = np.dot([x2, y1], r)
    rval[3] = np.dot([x1, y1], r)

    return rval


@nb.jit
def triangle_area(A, B, C):
    return np.abs(
        A[0] * (B[1]-C[1]) +
        B[0] * (C[1]-A[1]) +
        C[0] * (A[1]-B[1])
    )/2


@nb.njit
def pt_in_rectangle(pt, rectangle, overscale=1.0001):
    A = triangle_area(pt, rectangle[0], rectangle[1])
    B = triangle_area(pt, rectangle[1], rectangle[2])
    C = triangle_area(pt, rectangle[2], rectangle[3])
    D = triangle_area(pt, rectangle[3], rectangle[0])
    AP = A + B + C + D
    h = rectangle[1] - rectangle[0]
    w = rectangle[2] - rectangle[1]
    AR = np.sqrt((h[0]**2 + h[1]**2)*(w[0]**2 + w[1]**2))
    return AP <= AR * overscale


@nb.njit(parallel=True)
def pts_in_rectangle(pts, rect, overscale=1.0):
    inrect = pts[:, 0] == 0
    for i in nb.prange(pts.shape[0]):
        inrect[i] = pt_in_rectangle(pts[i], rect, overscale=overscale)
    return inrect


@nb.njit
def dist2(pt1, pt2):
    # distance between two points squared
    mlat = (pt1[1] + pt2[1])/2
    dlat = pt2[1] - pt1[1]
    dlon = (pt2[0] - pt1[0])*np.cos(mlat*np.pi/180)
    d2 = dlat**2 + dlon**2
    return d2


@nb.njit
def dist_m(pt1, pt2):
    # distance in meters between two points
    return 111320 * np.sqrt(dist2(pt1, pt2))


@nb.njit
def deltas(pts):
    delts = np.zeros(pts.shape[0])
    for i in nb.prange(pts.shape[0]-1):
        delts[i+1] = dist_m(pts[i], pts[i+1])
    return delts


@nb.njit
def dist_pt_to_segment(pt, v1, v2):
    # distance from point pt to line segment v1, v2
    lls = (v1[0]-v2[0])**2 + (v1[1]-v2[1])**2
    vm = (v1+v2)/2
    chk = (pt[0]-vm[0])**2 + (pt[1]-vm[1])**2

    if chk > 2*lls:
        return dist_m(pt, vm)

    # check this elsewhere.
    # if (lls == 0):
    #    return dist_m(pt, v1)
    t = np.dot((pt - v1), (v2 - v1))/lls
    if t <= 0:
        pp = v1
    elif t >= 1:
        pp = v2
    else:
        pp = v1 + t * (v2 - v1)
    # clip it from 0 to 1
    return dist_m(pt, pp)


@nb.njit(parallel=True)
def dist_pt_to_linestring(pt, ls):
    ds = np.zeros(ls.shape[0]-1)
    for i in nb.prange(ls.shape[0]-1):
        ds[i] = dist_pt_to_segment(pt, ls[i], ls[i+1])
    return ds.min()


# @nb.njit(parallel=True)
# @nb.njit
def dist_pt_to_multilinestring(pt, mls):
    ds = np.zeros(len(mls))
#    for i in nb.prange(len(mls)):
    for i in range(len(mls)):
        ds[i] = dist_pt_to_linestring(pt, mls[i])
    return ds.min()


# find closest two routes
# break activity into segments
# a) point cloud
# break into equalspaced points
# find distance to closest routepoint
# weight based on distance
# b) line segments
# more strava like.. but no tools for this


def activity_first_pass(pts, routes):
    # find what every point
    nr = len(routes)
    ins = np.ndarray((nr, pts.shape[0]), np.bool)
    # roughly, are you in the box.
    for i in range(nr):
        ins[i] = pts_in_rectangle(pts, routes[i]['minbox'], overscale=1.3)

    d2 = np.full((nr, pts.shape[0]), np.inf)
    # route distances
    for j in range(pts.shape[0]):
        for i in range(nr):
            if ins[i, j]:
                d2[i, j] = dist_pt_to_multilinestring(pts[j], routes[i]['mls'])

    dist = np.amin(d2, axis=0)
    rtnum = np.argmin(d2, axis=0)+1

    sel = (dist == np.inf).nonzero()
    if sel:
        rtnum[sel] = 0

    delts = deltas(pts)

    return dist, rtnum, delts


def activity_segment(pts, rtnumin, d2r, deltas):
    # recursively break into segments where the on
    # or off route is the same in a segment
    rtnum = np.abs(rtnumin)
    rtnum[d2r > 200] *= -1
    drt = rtnum[1:] - rtnum[:-1]
    rt_breaks = drt.nonzero()[0]  # gives the index of end of a section
    # check for short sections
    rt_breaks_tmp = list(rt_breaks)

    '''
    print(rt_breaks)
    rt_breaks_tmp = []

    for i in range(len(rt_breaks)-1):
        ib = rt_breaks[i]  # and the end of the section
        ia = rt_breaks[i + 1] + 1  # look after the next section
        try:
            if rtnum[ib] == rtnum[ia] and dist_m(pts[ib], pts[ia]) < 1000:
                rt_breaks_tmp.remove(rt_breaks[i])
                rt_breaks_tmp.remove(rt_breaks[i+1])
        except ValueError:
            # don't remove third in quick sequence
            pass
    '''
    # breaks should be at the beginning of a new segment
    rt_breaks = [i+1 for i in rt_breaks_tmp]
    print(rt_breaks)
    # big breaks are special
    delta_breaks = list((deltas > 2000).nonzero()[0])

    breaks = list(set(rt_breaks + delta_breaks))
    breaks.sort()
    breaks.append(len(rtnum))

    segs = []
    on_route = 0
    last = 0
    for br in breaks:
        if br in delta_breaks:
            i1 = last
            i2 = br
            last = br
        elif rtnum[br-1] > 0:
            # this segment is on course
            i1 = last
            i2 = br
            last = br - 1
        else:
            i1 = last
            i2 = br+1
            last = br

        segment = {
            'coordinates': pts[i1:i2, :],
            'route_num': np.median(rtnum[i1:i2]),
            'distance': np.sum(deltas[i1+1:i2]),
            'offroute': d2r[i1:i2]
        }
        if segment['route_num'] > 0:
            on_route += segment['distance']

        segs.append(segment)

    return segs, on_route


def values_to_heatmap_points(pts, d2r, deltas):
    # take the test points and make delta points
    # this will be used for simpleheat
    import scipy.interpolate

    delta_breaks = list((deltas > 2000).nonzero()[0])
    x = np.cumsum(deltas)

    xs = np.split(x, delta_breaks)
    lons = np.split(pts[:, 0], delta_breaks)
    lats = np.split(pts[:, 1], delta_breaks)
    d2rs = np.split(d2r, delta_breaks)

    lonl = []
    latl = []
    d2nl = []
    for x, lon, lat, d2r in zip(xs, lons, lats, d2rs):
        if x.shape[0] < 3:
            continue
        xnew = np.arange(x[0], x[-1], step=200)
        lonl.append(scipy.interpolate.interp1d(x, lon)(xnew))
        latl.append(scipy.interpolate.interp1d(x, lat)(xnew))
        d2nl.append(scipy.interpolate.interp1d(x, d2r)(xnew))

    lon = np.concatenate(lonl)
    lat = np.concatenate(latl)
    d2n = np.concatenate(d2nl)

    inten = np.ones(d2n.shape[0])
    inten[d2n > 200] = .8
    inten[d2n > 500] = .5
    inten[d2n > 1000] = .2

    heat_pts = np.column_stack([lat, lon, inten])
    return heat_pts


def generate_test_data():
    routes = read_routes_numpy()
    tpl = (
       r"{sndG~nvoLP@CMICKDMJMBMCKGIQKKg@Q]EIBCPAhAIPMBOIc@[SGiAQBBUCQDSNKPG\KxBw@nGq@vD[xAE\UvAS|@M|@gBrIg@tBKXSLWBq@AYBYJm@h@yEzFu@jA_AbCw@bB]~@MJ]n@[r@S`@CRDRTf@NPt@nAP`@rB|C|D`ILHLDBJCx@E\Ad@A|@Eb@B\?dCWlBKxAMl@Ax@e@rCG`AI`@OZW~@Q\E`@QZS"  # noqa: E501
       r"|@MZUz@]t@Uz@MVONSLIRQPSl@iAfAM^[FWRWLaAx@s@VYD[L_@AYD[@ULWFS?[HQEYF[@{@BYC[?EB[AQIgAH[?g@@w@HqAZgAb@yA|@WTKXNn@i@x@?ZFPl@h@DRGXi@xADRJNLLd@FRCNQJ?CTIHcA|AQJS?g@i@c@Wa@c@?Nd@n@a@dAc@`BAbCIb@a@l@O\s@x@k@z@g@l@OHSBKDIJGTKLQHO@MIQAEBLLNBFJETSd@@QXEj@`A?FCAGHDLFFUA?DQVj@_AN@t@l@f@PJHRx@XfCb@`CFl@TbAr@|BNVFTD\HZjAhFLjAp@vDdAhFfAzEDZT~@VdBTnCpAxLJhB?hAG~ASfCWtCU~A?\I`@_@dEYbBSdBKf@C`@a@tCa@bCa@bDIZUrAUx@_@r@i@p@oCnBu@\{B|Au@`@cBvAo@t@g@t@y@fBc@fAaEpLo@rBUtAGl@OzDAnCEl@OfJBzAHjBJZHz@b@`CXxBzAtJ"  # noqa: E501
       r"FfAAfAOjDK\Ed@MbCK|@KZOXy@rAwAfBq@t@[Vs@|@YX{@h@y@\u@b@y@PUPC\b@lBLt@h@|ARV`A~CfAhENjADbA@b@Ab@B`@@lAMvAGlAGf@O|BO|A?t@Ct@?l@ErA?n@Dj@d@dE`@pCl@fFRhDBnACj@@d@?f@qBjGo@|BO\_ArCI^Ed@UpAAf@OzA?hEK~Ca@`E_@xBEb@QbACb@m@|DYlAu@~AQRa@x@WXg"  # noqa: E501
       r"@~@O\wB|BgAv@UR}@n@SHMPg@Zo@t@OFKLGRMLGROL]j@QLSl@Yl@OPIXi@fA[`AUjAi@bBy@vBG\y@dCg@lAUn@_BdDm@bBkBhEUT[v@Yz@MVg@rAwAzCI^gBbEcAnCo@bAuArCSV_@r@i@n@iA~Ao@jAEZKXEtBCZClAD`A?j@Dj@@j@Ft@`@pAd@zBhAtC`@pAfApBt@tBRXN`@H^n@jBFTGXSXq@~AuD~Hs@dBmA~BQd@c@r@a@~@STEXDXJR\\JNRj@Xl@j@~@b@fA^r@Tr@p@fAl@vA|@dBp@~APd@V`@hClFPf@BXFLLFXn@l@hAv@xBp@hAbA|BPVjAzCd@v@nCnCh@x@"  # noqa: E501
       r"TT|@lAPXTXbFtEvA`BtAnAnB~BRZ^t@Q?Ug@KKa@u@UUGBAR@Z@rAc@|CKb@?NGNIp@Qt@EPEBOr@EHW~@Kj@MbA]nAIh@OXO`@MzAQt@QvAETSf@It@Ox@I|@EVMNG`@AJBFA@G`@YtAQj@GZMzAc@fAKb@QvA_@dBGb@c@~Ae@zBGR[hBYz@U|AUv@Sx@YdBA\KVQzAI\INGRALJBME@@i@zBA^kA`GGhAKf@E"  # noqa: E501
       r"z@UlAClAUnDMZDTCb@v@pArA~Cf@bAt@jBR`@^jAV`@Nb@|@jBvAbE~AjDh@xAP\Lb@n@`BFhAk@v@oAvBSTw@nAwC~DaC~D_@x@mB`DeBlCQ^k@p@{@lAgC|Bk@l@mA|@w@Z{Ad@y@b@s@z@o@hBc@z@UZWTk@^m@NYDk@Z{@Xo@^o@Vk@\iBhBWPaBZo@ZYT[LUXeAh@_@^Uj@Yh@Qb@ERWp@Qv@w@fCQn@g@pAUr@}@~AiA|BIBKAQDIAEBCL@LP^GXY|@WhA[lAWxAIn@i@`COf@Ij@e@zB]bAIl@i@jBGd@YjAYhBWnAs@xDCpAGf@Sb@Gf@Ol@Gj@]rASdA[hAa@lBMf@eAxFMh@ItBHlBNbAH\Db@HZBf@If@QrBCf@SfC@`@Op@InAIr@GTI~@G\M\Cv@?h@KhAAZEv@IZCt@Ip@?VIl@AVG`@K^C^O~@IdBIhAM`@GlAOjAEf@I^?d@q@nD_@|DOj@k@fEEnCa@"  # noqa: E501
       r"zDKl@AZUx@MZQV[NYFaACa@Q]Aq@MeAe@y@w@}@c@UW{@o@WMYSgAU]O]EuAN{@DSDc@De@R_@\a@d@yAlB_@^a@X{Ar@uBtB[b@y@pBi@zAi@rCI`BIl@Kl@Qj@Yh@m@bAqA`BWb@]^s@|@iBfDmBhCM`@Ej@Gd@@h@E\FdAJZLhAH`@\z@AV@TV~@LpA^`A?^H\?v@RdABZJLT|@Z|AZ~@b@pBX`ADf@Ld@D^V"  # noqa: E501
       r"fAB`@V`ACVMRSHi@Jy@DWf@DXbA~DXtA@ZJ`@zC|ONjA`@fB`@jCXrAJXFj@^nBThAVp@HZTzAZjAJp@lAnEb@nAVfAh@jBNr@r@~BF\Vz@b@z@ATh@`ChA`DD^~@~C@\C`@[l@g@d@aBhAwAv@YRsArAcAjAoAfA]R]NaAV{@LsBl@Y@]JUN]Ly@d@YXw@`@u@j@UV{@j@s@^YT[P}Aj@aAP_@B}A`@sAh@YR_AZ_@Fy@Bw@JaAB]?sARqAh@wAx@w@XQLkA`@y@b@Wb@Sf@W\O^W\_@^Wd@Wj@Mb@aBjDe@lAw@hCWdBK^[`BY~BEt@WjB[jAa@fAk@dASRORQLe@r@q@v@KPoCrCIb@eAxAg"  # noqa: E501
       r"@h@a@j@{@t@MXgBhB}@x@WPoBhBq@`@mBxAWNYLs@b@qA`A}@l@gAlAIXUTMVSNa@hAQTQPMPSLQTaAx@g@PqCtA]Hy@\]TYToAxAg@nBa@x@WXINSr@e@v@}CtEe@b@]Js@p@aBnAsA|@g@Vc@XWJu@n@[`@Wd@Sn@]fBm@jFa@dCu@nGCz@Dr@BxCCh@C~BI^C\G^OZ_BbGOt@Aj@IRGn@c@jBAXO`@G^iA`Fo"  # noqa: E501
       r"@zFWjBYtAIhAYhAEdAG`@OrBId@]bAaAbBwApA[T[Jy@LU?a@H?Dh@ITHP?J^QjA?b@C\@d@KfA@PNLW?m@HYFOHQAOF?JFRDn@D|@?`AN^J^d@bAJZHh@X|@ThAVl@RfBLVZ`AHj@VjAZjALXPx@Zv@Nt@f@dAHh@t@bAVTXLj@z@j@b@n@`@TRJD^FvAj@j@Hd@V^JjAf@j@HTHj@B\Nx@R~@d@XDf@TxATzAh@\HDEh@PDF^NP?bB\L?PHxAX`@Nt@Np@V^PJHv@@f@b@ZB\NlB^d@@p@Hz@XlALz@B^@t@Et@PjAJRAd@Fd@BRENBbAJx@BZGd@FTA~AH|AAlAFb@?d@DTCx@?zBPfAFTJd@LRJTDdAXLLNXNPPNLDdAfAj@v@NHt@jAp@dB`@z@Tv@Dp@VhAB`@HVJz@Bp@Fr@`@dBFp@Hf@@\Nd@F^@dALrABTTj@RlABR@zBXvBFj@RlAVfAF`@?dAJd@FfAXpBDx"  # noqa: E501
       r"@Pl@Fj@FTL`A@ZLTDRLpAFfAJn@Hp@BrADp@Rv@Jl@Np@D|A?fABZJZJbAHb@Zr@Vv@hAtAVd@r@x@\Tx@r@|@fAd@b@d@|@b@j@JRt@j@j@j@Zl@\^^Vj@~@PNp@~@^`@XHJVp@~@f@|@~@~@v@`At@hAP`@ZXLRf@bALL`@r@f@hA^fAt@bA@NLLHXz@lBj@`Ab@l@|@jBTXl@rAHZP\f@rAl@z@rAhCTh@b@p"  # noqa: E501
       r"@J\b@r@Vt@d@bAr@fAVr@jAdBRl@t@~@Nf@`@r@Ll@LVJH|@lBb@p@P`@j@x@Pb@X`@h@j@P`@JJb@fAf@bARZf@hAv@jAlAbDl@hA\f@N\r@|@Xx@\\LVb@h@`AbANLNTfA|@p@x@r@\d@ZhAzAv@n@TVr@dAJJr@`@\n@l@t@Zh@vAxAt@h@Zr@z@`AV\h@b@x@v@j@p@f@^T\TZRPZb@PJV\ZXhAnAv@l@jC~CVPj@l@TZRLb@x@ZXx@bA\TRXrCjC`BvBz@x@^f@BJh@^Zh@h@j@RJ`@d@f@v@P\NPFND`@R^Pp@FN@Nd@dARz@HPNbANhBJXHh@DL@b@BRHPNz@BXJVXzAL^"  # noqa: E501
       r"BZL\Hn@j@nA@\XlBl@xAFT?\BJ`A~BNd@T~@^z@X~@Vj@Nj@jAbCXd@HZ^v@b@fAj@dAt@fA~@fA^r@h@f@Th@r@hAb@XT^TL~@rA`@b@VPp@z@tAjAx@`Ax@d@ZL`@f@`B~@TXZRbBn@LRNFh@^v@ZVDRJl@b@~@f@p@RNLh@Pl@Zz@ZTTz@d@TDXLd@Jb@XZBXJ`Al@`@LRTVNLDRNf@NNHNLn@R\PHHh@NPJt"  # noqa: E501
       r"@VnAl@l@RVPf@P`@RVPd@RrAp@t@Vd@Xb@Lb@R`@Hl@\r@RNLNB\TPFLNb@LLJd@TNBTJHH`@NJHTHb@BXHBF@PFN\?n@XbBzAl@b@h@z@bAhAl@nAn@dBf@x@d@fAR\b@~@`@j@J`@@RHVPJHJp@zATTNVTd@l@dBb@l@d@dAv@r@DLEt@@LlAvB`@j@Nh@^f@Vd@b@nAj@v@h@jA^`BDb@Rh@Jd@f@hANdATx@\z@v@rBn@pC^nALz@Z~@h@vB\hA\zB\tAB`@FZZzAPf@JpADPXt@DR@h@RhAPlBL`@P`@Nh@^t@@PL\TVPHBFAZIb@BC@@ECBAG@B??KAACJDXIb@?PFb@CDID_@o@c@s@Qe@]QSQw@aAGUOOOGUc@OQYi@Yc@i@oAOSIUa@}BOuCOcAw@{CIg@a@sAw@iB_A}AOa@U[M_@S_@o@y@Ug@i@sAaA_EiA{DIq@Is@JaAFeAFuDCw@Oi@UkAI{@a@qBMsAU"  # noqa: E501
       r"u@m@qA_@s@[w@_@q@EWkAyCKi@Y_CyAoDoAkBcByCaAmAQOaCcC[c@Q_@MM@FMk@w@aBQSWOw@OaBTS@g@LW?UFU?yAZ]Xg@XGRwA~@KVUJeAz@wA|AOTWRqBrBwBxCYXUPc@L]D[NcAPaADi@JU@aATQ@K?OFMA{Bh@g@DcAPc@L}CLKFSA}AJyB`@m@?k@Fs@@s@PSCMUC]?}@Gs@@?C?GGIFC]?SJe@Ay@LyC"  # noqa: E501
       r"@g@IgASaA[u@Yk@]_@a@]cAk@g@Ek@McE]w@My@FULUDUHWFWBcATk@RS@UCs@SUMUW_C_Dg@m@g@[QGk@I{@Ae@JeA^OAg@}Aa@u@Og@a@_AOQ?SFObCcDXo@^m@t@aBj@_Bj@mBNy@L{@Fy@@u@F_AVuBFy@@wFB{@XsEPiEN{BJk@Ty@Xs@Zi@j@}A|@mERm@Xq@\_@lA_CxBmFv@yBb@sALk@LsADoBEiBO}AM[MQ]SQEKIUAa@W]k@CYMU@WCS[gAMs@Ee@e@aCUoBAg@OiAa@s@OQWu@e@w@Mc@Q_@i@w@K_@U]Mc@_A{Ai@gAWk@Mq@c@yAQq@Uk@So@_@yAIk@Mc@Sc@a@kB]_Ai@}@i@s@M_@U"  # noqa: E501
       r"[Sg@_@e@Yk@Ys@Os@o@cBaAeEEa@[aAK]?YGa@Oe@Gg@Kc@Y_@Se@Kg@m@oBSa@][_@Se@OuASgAe@[Ug@k@[i@Se@s@oBi@gAUs@mBoDQc@Ya@i@kAc@iAcAgBQ_C?]NkA\mACQg@k@SO_@a@g@]QSGQ}@o@eBkBk@w@_@[q@y@W]_@]Ya@y@u@c@[W[iBoBYc@Se@Ok@Gm@OqCB}@AoBDm@Am@VqE@}AGuAMg@"  # noqa: E501
       r"Ei@UsAA}AEo@Uq@_BiCc@aAYaAc@y@c@g@kAy@YY]Qu@g@OSy@[q@Dc@Gg@]yAgBKw@QU[Qq@uAWSQYUKYGy@?UDmA`@mAJcA?o@E_@?WAYImAMoAYs@Go@ImBCu@IUK_@?uAQQMqAk@eAm@{Ao@o@SmB_AsAu@WIi@Yk@U_@KkAs@e@_@i@[YWKAk@p@aA`AmAx@uAp@wC|@{Dz@cBf@]HeKd@SE{@?eAM]KMSGU@yEAqBL_CCm@?o@GaB_@_EWuD_@gEAmAGk@Ci@WmA[yC?k@QkAKqASuASe@Ge@Oa@UyAQc@g@sBMi@Ik@EyA@}BKgDa@sDUeAa@gAKc@aAuAKg@Oc@c@eAU_@{@sBi@kAQg@i@kAOg@g@iAYaAUa@Ok@e@aAEsA@qCGq@CgCIg@IeAE_@c@RiB`Be@h@KXOTi@b@uBxAUPMPMTEXATMZa@n@K^ORs@hBUt@OZC\IXcAhCc@n@g@j@_@R]LU?YFwCXkA"  # noqa: E501
       r"Dy@?WD]@[Am@HkCFU@WFUEaAAQCc@AeAIkB@c@Ec@?IE{CUY@w@LeA@MAa@Fg@EcAOoAIcCe@o@Gm@F}Ah@qAPoAQc@C_ADq@EQ@m@CkAK_A]WWs@iBKo@Mg@i@}FM[E[@[D[Fc@FQTwAFwC?qCKuBMw@IK]mAAi@Oy@AWH}@@mAGwA?s@IeB?m@KgA?]CU@YMDIG[qA]m@[}@c@}@a@kAQa@Ke@MIw@DkAA_A@a"  # noqa: E501
       r"@D_@L]RuBr@cBr@s@X{Ax@eAn@oA~@y@d@w@j@cDtBWRUJ}AnAw@h@S\WT[RoALWHw@B_@?_@D]?u@AY@[AYD[LWBeAh@{A~@GP]ZKPkA`Ai@\uAtA_@Lk@V_@JeCXk@AYHU?cB\qCZSFw@JULc@BWF[LkARY@}Ab@u@Hy@`@_A^YFoClAa@D_A\YNs@N]BoB`@wA?cBEk@BWFYCY@UBSAiBH[Ec@@o@E{AFuASY@u@ESHo@@SCo@@eADUJg@ZyBnB_Ap@SRs@d@k@d@_Af@OPi@b@m@n@u@f@aAbAiCt@cAP_@L_@P_@V]\u@bAST[J[Ti@NWB{Br@iAj@g@RiAZ_@Ve@Jq@\m@D"  # noqa: E501
       r"wFR_@AaEHeCCmAFeCMs@O_@CwAWgAa@m@QSKaB_@_AMQIYIWK_B_@KG[CWK[Eg@Ke@FQE_@e@i@i@aAu@cAM]?YBgA?aAKe@]MSs@k@[g@k@q@_@YeAk@WWsAq@SUSKiAc@}@K}@CcABm@FSFu@Lo@A]BgAEm@Oi@_@}Ao@gBMm@CgCaAw@IUF]BYPSDa@?u@Ru@N{@B]?]M_@Gy@WwAYeEQ{ADSGW?}@Ku@?s@O"  # noqa: E501
       r"WCq@Q{@M_@Cm@g@_@Qq@w@OY_A_Ae@k@m@g@]Qs@SYAiAOSIe@EWGqAMy@Oa@?YEy@EQGKg@B]|@sCH]Na@NSDa@^w@Pw@@eAC_@?i@Bc@FoGEgBE]Bg@AcAB[G[BmAIYI}@Yo@Wu@I[Gg@EkADg@AWBgAI{AGiBBU?eAJWD_@BOj@{@Dm@Aa@Fg@?aAFU@eAVo@@w@J}@EwAIc@?SD_AMw@g@{@w@iAs@q@c@Qy@u@g@WOQ[ScBs@{@E_@Mg@Ia@MyB{Ay@o@YYy@_@SMyAi@YUc@Eo@OOASC{Bg@QIQEw@E_@IyBCkADs@Pg@VOB_Aj@iAdAg@NkDh@wC\cBBaAJo@Nu@ZgAZSDULWAQOMYi@o@w@kAe@e@qAs@aFwB{@e@oAkAcAuAu@w@{@iA_@s@Y[e@s@e@o@SYkAsAaAgB[{@g@_A{@sAa@w@sAiBWU{@a@iBU[KiAOWIWDaAAo@KgA[iAMi@MmBs@eEkBwEcBgCc"  # noqa: E501
       r"AmG{BYQkBu@aBaA}@u@SK}Bw@s@OWMYIw@CqBBuALy@L{A`@cDdAeAZ_AT{Bt@{JjCuE^{@Ay@EsAQoF{As@]uCw@k@S}Ae@m@YeAWcAa@o@QSMQQ[Iq@[o@Ic@Qm@KQIoB[eACm@Io@Om@ABISC_DOi@?SAWEsBG}E_@_AMwBk@{B}@u@W_Ae@mAg@iAo@yAm@{@a@a@Iw@_@IGAML{@CO?A@DEGBAAABGE?MTC"  # noqa: E501
       r"?FIIBCHIEa@TCaADJD@@LLTFIFAHBh@r@EMOABEAGGGE@CGKOD_@B@DHDX@B@??CECA@?C?BAA@ACB@BCE@CCAABGEACBGL?ZPDH?ZGf@_@bAKtAYhBOhBSX]RK@sAw@e@S}@g@y@m@g@g@k@Yc@e@a@UWYUIc@a@mAsAwAiBg@_@KEsA{AUIMQk@_@UYk@aAk@s@m@k@}@k@_@[aB_Bc@[e@Wg@Oi@Ke@Ec@@kCM[Eu@Wo@GU@OCOGUAa@K}Ac@e@KwBcA_@_@YOi@g@m@w@Qc@m@oASm@U}Ak@yCa@_DIWOy@Ww@c@m@YUMEo@Gk@Me@SWC_AU{@[WIQCyAi@gAa@MKgD{@][]UQEg@SOKo@K"  # noqa: E501
       r"SKeBi@UKUS]K{@KoAg@c@MeBy@]Y_AkAc@yAY[Ua@Ic@Q[_@Sy@q@[O]o@Su@kAuCa@e@Mo@Uc@_@_@qAo@cC{@a@Wm@SaBu@yBiA{BqA_CqAg@]_Ae@_@O[U[M[Wc@ISO[G}@[aAQ]KaAYa@Os@_@a@GoDcAc@I]Ua@KsAs@sAk@YS[KsA]iBeAe@m@UQmA}@SUS_@WWQa@UYWQ]a@Y{@W[YWi@w@I[w@{A_@i@"  # noqa: E501
       r"IYOOEc@gAeBUYa@[MUCYOMe@q@SGKQKIOCEUY[[WEMWWOa@KOc@e@eAsAc@u@y@cAMWcCgCa@[a@i@_Aq@MQa@UOQ_@m@WYWQUCgAu@{@g@aAa@aAq@IMy@Wi@e@m@_@iBqAaBq@YA{@Y]Qk@GWDgASq@Ac@HcBNM?]Kc@AcAQ_BY]Gk@ASO}As@q@a@QUSQQUs@k@i@m@U[]Y]_A]u@_A}BgCkIIc@s@kC_AqCYe@Qk@Ik@Qm@e@sA}@mBKc@i@{@k@q@aAy@g@[kA_@oA}@g@GQGOUo@OMIwAcA{@c@e@_@w@a@SS_@Qm@a@q@s@q@e@UYc@]Mc@MQOI_@k@}AmBu@kAg@i@sEiEYOSGWMSWM[sAsAU[c@Yc@OsB}@QGUCe@OOK_@Gg@YSSc@Q{@s@q@_@QSo@e@iAwAOMk@w@_@w@i@y@aAgB]a@kAqB}BoDm@g@o@_@w@Uy@MsBUw@Qu@]m@e@m@m@g@i@kA{Ag@c@i@"  # noqa: E501
       r"[gC}@cCgAqAc@e@SeAi@}@{@sAgBu@w@aBqB{AeCeAgAY]Qk@IeB]uCE{ALa@RYN[l@aAb@o@NYJ[b@k@R_@h@u@L]LKZq@Z}@\gAN{@N]H_@Fc@B_@JiAAe@Ie@]qAIi@]sAMg@Gi@Ok@SuAAg@KmAOe@A[a@yAWuA[qAEo@Mg@AQIUKy@k@kB]k@u@iBGo@c@kB{@uCo@uAkAsB[c@k@gA]c@Ue@o@{AaA{A}@"  # noqa: E501
       r"eBTu@PeCRaBCm@Gq@}B_FMc@MmAOkB?a@NaCPsADmAFo@EKDo@CcAWgBo@kCi@eB[sAW]@a@E{@E[M[I_AMa@@g@KiEB{@U}@[}@s@iBYm@cBmBi@y@i@aAs@_AKS[YMSWk@KWMu@?w@By@E]Aa@J{AC_@Da@AyANeBCe@H}@@mBFY?W\aBHYN]Lg@`AcCx@oDRqA@g@Cg@O_AMEIDORMFUBg@^c@R[Vg@JyAt@MBi@DmA@a@Mi@?y@Ka@A]C]@[FY@YF{@Vs@@w@Ps@@]Js@F[F]LUAwBp@q@LeA`@i@b@k@ZSFSPiAf@u@RiAN[?s@Lq@E[@YLq@Jo@TSLOToAbCo@|AYTQXw@V"  # noqa: E501
       r"]D]LeB@[EWCWA]FWCYGW?WE[@s@Uw@Iu@Uk@EeAAW@g@GU?eAOSASBKMWA[H]DSE[KYQWS{A}Au@c@{@a@YSs@q@_@Q{@u@s@u@]Y_@SaAa@}@Y{@Qs@?i@JsANkA@oAYeAO{Bi@UCqABYDW?uAFs@@{@EsCw@kAUe@Q_@UiAc@eA]]GgAHUJqA`@W@q@JWAU@SFu@KoA@OGQAQG[Ii@Du@a@WKOM]My@cAa@S]W"  # noqa: E501
       r"a@Kc@_@cA[MIW]i@]o@q@Ye@cA}@eAC]GQF]@MDi@F_@Iy@EmA?{@DQ?KMEY@Wh@yD?_@GGM\GZm@nEKXWLUFu@?kATq@HWAi@@iAH]@OD}@FSFkAJWHgC\k@L}@F}@?YAo@So@c@USOWUQOSUMIU{@q@UM}@q@eBeA]KcBgAe@g@i@WMM_@QKQYGYWg@UIYOKu@{@_@KeAsAs@s@_@UIO_CsAKMq@i@[a@mAgAcAq@o@i@s@g@]Mq@a@MWUWq@a@m@i@[Ms@e@k@m@uC}BcAcAe@_@q@_@i@c@k@c@c@i@qA_AmDyCm@m@Q[K]YKcBuA_@UsAiAw@a@m@g@m@s@_@]wAiAa@Sa@[e@WaA{@]a@{@gAc@_@q@}@_AqBYa@]]c@[kAq@[i@Ok@mAcDSe@{@yAK[]s@ScAAm@YmCOs@AYIk@i@aDYuA]cDMi@_@gA[i@D@NN@@KCBLA@B@ABDIAEYWKOIYaAyAKc@O]cCcDmAu"  # noqa: E501
       r"A_Au@aAcA{@uASg@]gAMqBK]I{@M{@GkAG_@C}@?a@G[GyBM{@M]A_@e@iBM[]a@Ea@Ui@W{@OUK]G]MYOO]i@QOs@cAUm@eAgBkBiC[]{A_CiAoA[e@e@_@c@g@sAmA}DiEi@[]o@cAiA{AmAm@s@q@e@k@m@WMYIYO}@q@MCEOMIKQ]]YS{@a@KO_@YKSQCu@w@KCO@U][]kBsAe@q@cAm@KKM@BC?DE??@_@m"  # noqa: E501
       r"@WUKUAs@CY?g@F{B?c@JuCTmCNq@FuA\_APw@Fq@@i@IqBFi@Ei@@m@Gk@PuCBq@Hm@LeBHcBAm@n@uHFwARmCFo@JwARaBNqCHy@\iBh@qAdA_BL]LQlCsD~@aAKDMNk@b@[^_AtAa@d@MLa@j@Wj@_@l@SHaA^sBj@w@VSLuAh@UDuAp@eALMHe@LS@e@XSDGFODKAM@aAXc@PIJCF@BBQA@BBCLi@HQ?YRc@J_A^[DOBg@VOD[P[Hs@X]HwEhBk@Nk@To@Lg@RQJu@Ve@BSHgAtAu@dA]x@wAnBSRMZ]h@k@j@iAhBg@l@a@t@OVSPo@hAe@h@g@v@s@|@oAtA{A`Ae@Ja@?e@I]U_@a@y@c@[K]Cy@C"  # noqa: E501
       r"YNm@d@{BfBQBYRs@n@SXKHa@Pq@DaAKg@MYK_CKm@@i@EcDY_BG_@G[DuCWWKYAWFY?m@MQGOAKLc@vCW~AKXSJi@DUJk@\mB|AWLkAXWJ_@Fk@PwAl@m@Po@LgAL[@UHYDq@DW?]IY@]Am@Hs@BgAVqAd@}A|@yAdAyAv@q@b@[LcB`A}Ap@q@Ns@BW?s@GUO[AsABs@A[F[H[NcBdAgBx@mAh@WD]PYBWIWQm@"  # noqa: E501
       r"k@eBoAOUWEo@UWCk@QY?]Sa@GiAi@SMu@YqCyA_@I[M_@E[Gw@GS@qBt@m@FwBFq@Cw@?uAIUM]Gq@SwCgASAy@i@g@SWQ]OkAs@eEwBUQ_Ak@WQ]OW@y@NSOIU@UZuALa@Li@ACODENGj@?ZGLI^A@GCB@GD@CB@MC?EADEOC@@BHAFCELGBGEODSCM@ICOMEAGDG?Ea@Qu@Sa@WkA?IUqAMOEWGIs@w@S[IgAOw@e@c@g@m@WQg@k@a@[o@w@UKwAcA_@_@IMk@g@aAm@wAiAWWU[Ic@Gs@@g@TiABc@Ng@GiAGa@Sc@UUs@k@[c@COGMCSDIKIGQK@]n@]b@kA|@wAdB[XmAr@y@j@m@n@m@x@Q^e@h@Wl@QPIRWXUZuAhCg@r@k@f@SZUNs@t@MDKPOHo@|@Ud@UXaBfCIHMRGVMXMRERWj@GXu@jAGPc@x@}@|AQ`@QVYJaC\]?[C]E]OgA[kCcAc@G{@k@[]kCkB[Y"  # noqa: E501
       r"aBoAcBaB_@UW[[[{AmA][Wa@_@SeBoA[KgBkAaBaB[a@_@YeAwAYQSYe@c@_@e@aA}@w@{@yCuDcBiBmCkCqAaBcBeBmAeBg@a@MSe@a@]a@}AuCu@q@e@[aB{@_@g@USc@g@u@_A_A{@kBwBaA{@iDyDQKe@a@s@{@eAu@_CmCcA_AOKMM]Y_DuDaAy@w@y@Q_@IECNDLh@^p@n@\f@NGn@~@HBZ\ZP`CxCt@z@"  # noqa: E501
       r"lB|A^\Zf@z@v@r@x@jAdAdApAdAfAbAjAn@n@lBpBV\n@j@p@t@nAbAvA`An@x@b@z@rCnDz@jA\ZxA`B\f@n@p@ZPTXn@d@b@v@f@Zr@z@~AbBp@~@JLPH\h@^\^p@TVpAnAX^\VfAhAjBrBzAlAZRb@PLJPJf@\|ChCz@r@RJxBxBJNTLp@x@TFp@x@n@^TRr@^~@n@bAf@fAp@lAb@zATj@Rf@Jd@Cr@Md@OP?XGVYXg@Z[R]^a@Zm@Ts@t@eBRa@l@{@Pc@Dg@LWp@e@j@y@La@ZYTe@|@iA~C}Ct@}@XeA`@m@BYVQFYJYh@o@tAsA`@g@XUd@Yb@S`@Mr@w@t@cAjBoB|@g"  # noqa: E501
       r"AF?DXFPLNLTdAz@JVFVXv@FZFlAARKb@O`@CN@z@?lAL\t@f@v@z@^Td@`@h@h@xAdANVXR?Fh@Xr@p@v@b@b@l@ZXPXBHDf@Xd@BNFP`AlAJ`APl@Dt@\`BXl@BPC?@LN?JDNRH?TFPCLDHCPDDH?JCf@FR\BJINCTBVC\JjCtAbAr@fB|@nAt@NPn@Zz@h@pAd@j@DVPzAXfA\x@Hd@?VHX@RD`@Bt@Ap@CdAQ"  # noqa: E501
       r"~Ay@f@AZH`@DpCdA`CpAf@TXNbATZNr@DXJXNb@Jt@h@fAbAfAt@JLPJRBTMTAROt@UXQhAe@TQl@[n@_@n@WVOt@ArAFr@@ZBjBBVAt@Mr@Yp@c@rAo@RQp@_@r@e@n@QlAo@v@e@dAy@XKVQ^KZSt@Ar@B^F^?TEXBhBQXK\EXA\GtA_@|BeAXI\EZIb@ATOTSN[fAs@f@c@TMRGb@@RHHEHMNq@d@qCHy@HWTErBRxBLtE`@r@@r@H\DVHt@?n@Hl@BNEZFZ@HCtATbAHn@GLWl@k@t@_@v@k@^_@d@WX[ZSx@[V?v@JzAp@n@d@TJZDVAdAc@vAy@Tg@vA}AXKROPi@NOd@mAx@gAP[RUN[PSPWj@o@L[PSFSRM~@kATSN_@RWXQRY@YJ[P]Vy@P[\Sx@SbBk@p@OhBu@REh@Y^I`By@ZE~@Y\Qt@k@VE@BDAI@B@FGXANGZQh@MZY`@Sh@IVIJ?\QJCx@Ar@_@xAg@t"  # noqa: E501
       r"@a@JMRM`Ck@|@_@RCNK~@SP@lCaALAHDBL_@fAG\I|@Q~B?XAVUjDOfBGNC\GfAYlCObCS~A?z@QdA?r@Gd@IzAGj@Id@C`CC`@RnBHrA?n@Ix@On@Er@SdB[z@Gj@UnAK`@Gn@GlFBXAp@HT?jABTFTDLJJRHPJZZhAx@^^fAp@j@d@t@b@V^vArAv@n@ZPlCbCvAx@rBvAb@VnBrBv@l@ZZdArA\TNNLVr@h@H"  # noqa: E501
       r"LXVFNLLzAxA|@fA`BhBl@z@JVf@z@bAzAd@h@f@|@TZz@|@HNx@dAH`@l@jAZbAXf@Rb@hAvDTpATr@HpA@lAHh@Af@Hd@@^TbD@j@Jn@Dj@PjAJd@~@zATVTPfBhBdA|@JNDRHDZXf@j@T^n@tAp@hARPDTNPZj@n@dB^rBDh@TvALnAh@`CFn@XfBPjB\`CZ|@Zd@Td@^fAXh@Rh@|@rCVTd@Xn@RRJj@h@PTJf@\j@PPXl@PTTTPVVTRXx@p@b@TPPHT\RHPP@DJTDTVl@ZTVpAbAVTx@`Al@b@~AvANHJN~@r@lAhA|@n@b@r@p@f@^RPRb@b@|DxC?LZN^VfAx@h@l@^X^Nj@h@Zd@TRdB"  # noqa: E501
       r"jAv@l@^^TFRJdAt@\FTRNTh@j@j@`@RH\h@p@h@\RbAx@xCpBb@\jBjB`@d@`@\|@v@|CfCdCpA|@^ZRt@r@\TZLpCrCr@f@ZNZHd@FRFVE`@OTF`AC^KbAOj@Et@O`AMbAA|@Od@CZMb@BZGf@?v@MbAEf@GR?LCJO@_@RgAX{BXsCFcBN_CHeC@iDPcEAa@Ba@@eAF]HmBTcIP}CFyCAk@Fa@Dg@@qARoB?e@J"  # noqa: E501
       r"qBFyBCe@DkCB{EDs@CaB@q@LyADcBHs@JoBTuBLsBHu@NiBLkBBu@PsBr@}HJeCh@cGD{EFmABcD?k@FkAD_@BqCF_ABe@Cc@Fa@@a@DyCLiCB_DXaF\gDFw@By@NmBTmE\yEReEj@{H`@{HTiCH}AHkCt@_KBi@TuCHgBp@qIx@eNFWHKX[Hm@?a@EmA?yAT_Fn@}KLyAFaC@wAOuDAk@KuAWgGIuAGwBKmAKmBAcAM{A@sAC_@Mu@?qBIu@Aq@EoAIs@?WIyAAw@UyBY}EOgAGoA_@uBAe@Oc@Gi@?sDEk@Kg@Gi@?m@QwACm@YeCG{AIq@?o@Km@Eo@CkBIm@DgBHaB`@gCLg@d@sCn@kCp@_DT{@nCiNb@cBRsAKCKPIf@_@xAKRIVQhAQp@Ip@e@xBAXETKPE\i@nBUpA@\NDPShAoBPOJUbBcCVi@FQ?F@WCUs@[mAu@y@c@a@Kc@G_@KeBKc@GYWMg@JmCr@}HD}@"  # noqa: E501
       r"ZkB^{CJkAx@wHH_@?a@^}A`@s@Fc@@s@Tw@Lw@Ne@~@eEr@qCN_ARy@Hu@Vw@bAyDRe@Fi@ZuAn@kDr@eCfAeFjCaLbCqLp@iCFm@Po@X{ANi@h@mC^yA|@aFj@aCb@eCnBkJ\uAJo@^sAhGmZ\mA~@iF\qAT]Lg@@g@Fi@xA{Gf@yBHYdAyEVs@dAqCp@uBR_@v@_ChAqCnAuDnAeDLe@^eAt@}An@cBd@y@Pc@"  # noqa: E501
       r"l@yBp@wAh@aBZo@h@}ARq@hBeEb@}BNe@p@yCh@w@JgAJ[`@eC\gBNeBH[JwALcAJkAPoEDO@UN[j@o@CQQ?MDIIe@gAGESAIK?EEFAEE?AEEJQCDACA@C?D@AFDF?CJECFLCABFLHBC?ICGEAC@MLAAEOABBFPMIJC@CA?MA@?CA@@@CEBBCF?QGOCB?DDF?DBI@HBACCE?@?AEBAC@ELDNN?JKCFIFGQ@EYEIGGME[Yu@Og@_BaE]wAKeAUkAOqAu@qEYuAAi@]qAUmAWaBg@{BM[m@aASQM]@]IcAMWI[I}@Ma@w@uDYsCIQQs@KQKi@Es@UqAIq@?]Gg@BQIQ?YJI?GEO?SEe"  # noqa: E501
       r"@Ao@IyAU}AAqAE]CeBIoACyDOyF@wGRwCFm@TsAFg@d@gCp@}CH_@Hy@H_@J[^}BT_AB[ReA\uC`@iB^uCNc@LeAd@qCVkBdAeFZkAb@cAh@eA`@uAv@}Al@qBrAcILoA@g@X{BRaALmAZqBTeA`AoGb@uBV{@Da@L_@Fa@lAoFf@qCLeATaD@}AH}AFeEDq@L{GHuALkDJsAPmDD{B`@yG?]E[Fy@?_@F_@B]Ca"  # noqa: E501
       r"@@[F_@?]C]FW?WHUVsBCWBgAFg@DsAJg@Hm@HcBHu@VsEHo@JyDBwAAsDSgD?i@UwFMyCIgAAiCMgBCiBEg@HuGPmBPe@Hg@T}B`AaHl@_FPmBNkAJg@\}Cj@mEVsAl@sEFe@F{Bp@iBDg@Jg@De@Je@BiAHa@Dg@PeAVeAXeBdAmC`@wAj@}@r@_Bd@}@p@{ALa@P]J_@z@aBRUp@{Az@_Bt@_BLc@tCyFbA{Br@oAp@{AfAuBt@uBZo@z@}Ah@mA`BoCz@cAf@i@v@cANWh@o@bAuAd@eAJi@oAaAe@A]HWRgAbBgAzAwApAKNDBZEx@WZSZ_@PMVa@\]l@{@vEwF~AqBlAsAxAoBf@e@f@k@nHwJVc@n@w@h@_Ab@kAhByCx@mALU@WG[?YDU~@kBBWGWYe@MIO?QGWYO?]TM?M]AGD?ABKA@HBDEKGG@D?AB@?GDD@?EE?BEDH^FN@ADDL?`Aq@^a@`@]HS^a@`@a@d@"  # noqa: E501
       r"[PQjAwALWRUfAkBbBeDHW\o@DStAuATGRQRUP[j@g@dAm@xAw@PAXM`Aw@t@w@P[jBaCnAuAr@{@h@g@RQ\Ol@_@j@UVMn@SrAUTIdAm@JSDUnCmEn@mAFU\u@x@wAd@o@|@uCTaA^aAX_A`@}@pByC\aAJa@|@iFb@cAZ_AP]^eAt@iB\eAt@iBnAoDv@iBLS`@mAtAcC^Q@FE?FGT@JFjA|Ah@h@vArBCEF?C?"  # noqa: E501
       r"BHd@BPENUn@}Al@kBLYXy@l@mA\{@t@oA`@w@h@o@h@aALQFCB@p@gAfDqCd@U~@y@xBeAPUPMVIn@c@bCiATSlAs@r@Yn@_@VK~@m@jAm@LQfB}@hAs@bAe@JK@BJGh@]bCmBfAeAN[|@mA~AgB\u@h@qBD[LWRGtBBf@Ih@Qz@}@RONW|@y@zB}Aj@[jAaAv@_Af@_@Ba@CiAJoANk@j@sDLk@\cCd@_E^wBRsC?m@Hi@Z{ENaB@w@f@wFFm@Li@A_BJiBBgBFy@?s@NcDPwIPuCRuAPuBNgA@g@TcCXyAn@oCJu@v@}GLsAHqAFg@TkA`BcDZu@NWJYP]b@o@TUZk@Z]BYESi@{@ASFMNKbAkANYRUP["  # noqa: E501
       r"LCFYAMOe@Ke@DOh@[\[t@i@DKRId@_@H@@GJBAK\Sv@YTMPMHQRKTGABFH@ATYx@a@HK@SIo@GUMYQq@CUSo@BUPI`@m@jAyBNc@jAiF`@kCR}@RULY?[Hs@DUNi@LcAZs@FYr@oDrAaB|@o@bAUl@I~A_@r@MbA]j@a@p@kAD_@F_AGc@GcAG_@A_@MaAGmBUqCQuD?e@Ce@I_@Ee@Ci@Ea@Aa@K{BW_CAa@QoB"  # noqa: E501
       r"Ae@@k@De@La@Da@r@iBRiABg@CY?i@a@wDI][_DYcBy@cIgAaHOc@KmBFyCHmAZkJNcBNaAXuAHw@Bo@GiBImAGe@GOGs@HgADUVs@zDaI`@cAb@}@\aAPa@\gARoAHYF{@?u@KUG[_@m@UUuBgCe@q@}@eAc@{@O_@Ec@H]Fg@PcA?_AIc@M[O_AQw@IaAI_@CkBDqBRiA^sALWx@q@lAi@VIR?XFbA|@TX`AjBxAbBj@~@VZTTVPnANRCP@hAIr@SZLZAn@IV@RGfAm@dAKf@Hl@Ph@JTHl@Fn@Nl@l@JTf@l@VTLRb@PNNLHf@n@j@hAD^h@dBD\N^BXRRB^D^^|A`@nAf@fAZbAl@rA~@`Cl@pA`@rANx@NxA?vADxBJ`BLbAR~@n@tAfAzAh@h@T\n@v@dA~A|@zAlCdEl@x@`A~@PTTPRV`BtEt@dBt@|BVn@Zh@fArCvAvCb@hAFZHz@J`BPvAp@zCAd@NXJ\Px@L"  # noqa: E501
       r"~@JZFd@^dAVfATX~AzCh@|AB|ALnDMdAQnCIbDFhEBZJp@ElBD\Cr@@REt@@ZVbAAn@DHHDN?p@Or@AnANVHr@JZJx@P^BTAl@IVKt@CZK`@CZK`@IVAv@Y\A~@UdBo@TCZK`Bk@tAYXKVGTKd@ONAPBR?JWGYKWCa@GiB@iBB_@GgAYyAOgABmAFg@Rc@T]dAiA^MVQhAg@LM^y@J_@Aa@B_@F]N_@I_@EgAMg@"  # noqa: E501
       r"YeBEqABg@TcA^y@f@kBPe@Jk@Ai@Fi@Am@KuAUkBScAAg@YoCAc@@_@KgAGeAm@mCOc@oA}EIa@q@eCc@}@e@y@y@mAqAcB}A{ByAyCcAgBsAoB_AyAS_@YiASkAKmA@g@JkADgATeAVy@z@{Dz@yBb@s@f@q@n@k@n@e@hAk@p@c@t@[r@o@d@u@Tk@f@cBXoA`@iApAmBTYR_@j@y@Xq@fB}A|BeA\K^Gt@DZDp@D\ElCaAr@Q|Ao@bAUp@CVBhANn@LtA\h@Rf@XvAhANP~ArARJZ`@jBxA`@`@b@^NP^Xd@`@LNf@\t@p@n@t@x@b@h@PXBfAGVMdAWVMdASp@Df@LRJ`@`@l"  # noqa: E501
       r"@dAf@tBVvATt@|@vB\n@hAlBz@n@TDz@Xf@`@j@T|@h@hAbAZb@HThBhDFTr@xA\tAF`AA`@G`@]pAI^MrCIb@o@bBa@~AKbABdAP|@dAdBJXpAbBl@n@@BAGD?\Tb@Px@Th@@lB?tABl@Gl@Bl@LTFz@d@|@j@PPrAr@d@Xz@XbBt@zC~AnAj@nA`@T@RDfEHh@JnBEf@Dj@ETK|@?l@Gj@M|@Al@GbAEz@B|@N"  # noqa: E501
       r"vBNVFTHf@Z`@`@TLv@l@|@\bCX`AFn@H|@RTJd@\b@b@LRTt@j@hD^pAn@nCJz@?^I|CBx@Jv@h@xBZx@F^b@pAj@jA\h@fAlAn@z@fBhBf@`@p@x@~ArArBrAd@`@tAh@x@j@d@VdBf@jB\n@NvAJlBTT?fBTTAj@DzAEh@EvAOtAMRBPLFVB`@Ix@Q~@gB|HM\yA~EI\]rBE@?Fe@`BE^?xAPv@JZNVRR|@n@`@h@z@d@PRTN~@h@z@n@RLlA`ApDbCPN\f@RLPRx@l@`@d@|AdAPJ|ArAv@l@f@ZPNJVRNf@XPPf@ZbBvAz@j@z@z@hAp@nBz@VF`@ZZHn@Lj@XjATj@Tj@Pz@b@l@HRLl@JRPVF`A^`AXNLbAVh@VbAZzB~@TDPPTJVFf@VtAh@tAn@RNpAj@b@X~@`@RLTHRJ`CbA`Ct@dB`@~Bz@h@PPJxAf@f@VfAXRJzATzA`@j@F~@VjB`@pD`AvAb@|A^TBj@J"  # noqa: E501
       r"j@VzA`@|@d@h@RVDR?d@OPQ~@qAPQRMVCf@J~@`@j@Pj@JfALjA@t@GVKl@]xAgA`Ak@VCXDTNPRfBlEbAvBTr@`A|B\xAT|ABXVr@Zl@t@v@|AjA~AvAzC`Ep@hAPP`@n@PPt@l@bA^dCr@z@Lj@BzAEj@ITKz@c@d@c@r@aArA{C^k@bBaBPKTB^`@tBpERXj@h@fAh@bBh@lATr@FX?`CTPDt@d@ZZ`@v@~@v"  # noqa: E501
       r"A~@jBHZVr@PTJ\LX^f@f@\PPh@XzBv@jAV\J`@P^^Th@\~AHn@HxAAh@MpAKf@Q`@Mf@Id@Aj@HtANfAJ\N`@PVRV~@bA`CvBNXTTrAjA|@n@z@z@VNj@n@t@`BpBjG^z@f@zAZx@N\PXTTn@`@hBr@pAb@nAh@|Bt@jARXHlAR`B^jA\hBXfAZZ@hEhAfAf@ZDVNXJVNRRn@ZdBn@nCnAVRXLh@l@b@r@tAhD\t@Vr@h@jAZ~@\x@b@r@l@rAp@x@p@f@NFLNVNdA`@hAl@jBr@|@h@RBbA\n@LRHp@HVHRNj@RfAb@bALRLbA\bAZ\BJL`Bf@l@NdAN|@\n@Nj@VVFX@VNh@Rp@HtBb@l@PfA"  # noqa: E501
       r"PNLhANl@Np@BdDv@xBNl@JTJdAHl@LdABTBV@VDhAJVHxC`@`ANTFPPFZFp@hBc@XBxFOX?n@Ft@Ep@@hAEVIZ@ZAXIjJaAhA@dARp@Rh@\bBj@|At@`Aj@PRjAbALVLxA?^FnB?`@B~ALvA@x@FZ?r@FV@^J\Fp@ZlA\fBFt@FZZlA?\FZRj@\RHLFTLHHJ`Al@bA\`@X^RPDd@Zh@TRLTHRLr@v@HXf@Xj@f@z"  # noqa: E501
       r"A~@L@JFd@r@PNTHHXLNTFLPJV?NLJBRHTF`@@l@EvABXJTbAbAf@XPPx@t@j@^fAd@XAVBtBZ~@Rj@Th@HZJl@Jl@N`ALp@Np@TVBRJZDBAjA\vAN`@Pn@D~@Rj@FTDXHb@TV?XDRFh@HhCn@RATNT@VFv@HXFVJdBJPPjB^h@HVAn@LXLVDXPR@~@NRH`AN|@TPBPNbAT`Dh@T?fCd@`Ft@lAVzDn@~@LVFvCb@\Jx@PRJjALhBVlAXT@t@Pr@FnBh@hC`@bD\|Cl@l@Hn@NjEl@~Bf@B??E^JR?rA\l@JrCXjCDfACj@Eh@K|@YxBa@TKXCrEiAlAWn@IjCCpADjDC\DdCAr@BfA?bFFVAjADr@CfGHnAAZDfBATEr@?f@ObBKTGlAMZAt@BjAKt@BpAOrDKxCOhBGlAGvCW~C?fBHv@AdDDf@CxAFn@CjA@VCr@Ap@DbB?VDp@@XF~ADp@C|BCZBzCGV@l@Gr@?p@KhAK"  # noqa: E501
       r"r@DdA@p@FjEBx@HTAp@@hAFp@CVEV?ZDdB?fBKr@BRCp@Bn@?dAFp@@dBGp@FTCXB`CKbC@~CGzBJl@?zBJfC`@bBLh@Jn@AXJTBdAHT@VDrBPX@TAj@DTCnB@VAd@BP?RLHPFx@E^H~CC`AD|GFz@B~AL`A?|@B^z@tCf@vAl@vBRz@V|AN~A`@`GTbCFxBPbBC~@X~BF`AR~@A`@@^NbALdB`@|B@\Nl@B\d@t"  # noqa: E501
       r"A`@zAD^E`@L^DZHhB@xAOjDKnAAzBBdBEnCB|AC`A@~@Et@FV@|@HtAAVJv@rA`FZfBLb@ThBBdAA^NbC?z@N|BC\FbC?^JlCE`A@~AE`CS`AQbBI^Cb@Kb@k@lDYvAK|AGZIXk@lDSv@C\Kx@M`@[zBIbAY~AE\Ov@O~@g@rBWlAc@nAOl@a@lAE\IXStAYfAGf@ATBZCh@BRNLv@Pf@R^h@JXtAfBj@`A`B|Ab@d@Tv@@t@Cz@Kv@C`AE\IrBc@|CMn@Wj@A^Mr@MXOp@KTK\[~AM`@qAjFY~@W~@q@rDe@xAC`@Op@IDB?CGm@Gu@H_@RwAb@SNUFSN_Ah@sAhAiBvBoBdDSNO"  # noqa: E501
       r"l@GnBBV?TB`@@d@ChA@n@OdCAh@O~@Ar@Gh@HhCE\BXAz@EPAV@n@Kz@Cl@O|AIjCD~C?rAE`@BT@j@C^Fl@ATSdACZFbA?|@En@@r@EjA?l@GlAFpAE|@YvC?rB?VKr@@h@Ct@Gr@I|DCtDFX@XAXB\OhC?\EZ?XETCn@@XQzABr@EfBGv@@v@Av@KrB@pACr@Gj@IJKf@AfCCl@LfBSpD@TFNHHN@RI|@Q~@Ol"  # noqa: E501
       r"@EX?hBLpALFFPbAAVBTObBFJNCFWReDLQRKRCh@]LAn@SR?`@DJDZ@f@Dd@\JBf@BDEC??G?F?GA?AJBIDB"  # noqa: E501
       )

    tpl2 = (
        r"gkodGjnooLp@t@`AdBr@`ARPVF\VN?DDDJ@NGf@@FZ`AMVWp@QLA\B~@E|@C|CLxCSz@QvAVhBYhBMfCApAMhBG~CAtAGfEM|B@zCIdCAlCK~AK|@ErAMnAU~LIlAGrBFlBIjEe@|IIzDBlANlA@\EvBKpAMrAAlC@jDCx@?hAEz@E`CEzEInBQlCE`BA~EK~EYpAIfD@v@LvAMdDC~BNfBEvA[x@Gd@IxANbDL"  # noqa: E501
        r"TBZQnCGzA@~@NtABHZb@fBfALV@JEl@K`@]lBSVYHg@CS@]JSJ}CpD[ZWFGNyAbCk@tA?^VXXP`@NPLBJE^g@|AE`@Lf@~ApDl@~@JLNXn@xA@NCREF_@zHKzAQ~HMbBW~BKpCIZq@lDWhAu@hCsAlDg@hAo@fAy@fAi@j@{ArAkAl@gBv@aBTaAFqDEc@F_@?oBCiBVQDy@\gAf@u@f@q@l@AR@v@STUf@@jAP"  # noqa: E501
        r"fBFh@AHM`@u@z@Yh@Ol@AVJFPMb@F`@VJRCd@Y|@IPOBUME?GBg@nAQNsAdBa@`@y@~@c@ZMTG`@]^EXF^AJ@PFHl@b@VH\RNZHj@Vz@VfB`AhFXbA`@|@jC`NTrANf@Ht@CbA@@VBNXZtAXbBn@|C^zBHx@Bj@p@pG?f@BABRNbB^nC@pBB\DBPEZo@?GKe@UoB?s@Dg@DIN@FDFG@MHML?FKG_@[SC@@p@CP@"  # noqa: E501
        r"^BBJE?YCGEQ?c@CGBKFHVDJOKJUpAUD_@EQBIOCe@S_Ak@{E[kDQgAw@{DEg@?@GGSqAKaAQa@[sA}@oEQu@QkAaA_FJs@ESGEOGY_@c@qAeAyFk@aCKm@Gu@CIOISAk@[[e@EKKi@?cAFg@v@kAz@y@p@i@z@_Ab@_ADc@Es@Am@@Kv@mCLWr@oAJq@G_BIgAAy@^[JUGm@DOV[fBsApBw@r@Qj@EzBDZBj@Gh"  # noqa: E501
        r"BLz@@t@G~@Mx@Ox@UbAc@l@_@p@m@r@a@`B{Br@kA|AyD~AsF\iB\}Bl@aCDgBHeAHoCHyE?_ADKASFSFw@J{E?UBKHW?Kq@mBMWMMaBiDa@WCq@Kw@t@}B@QEOUOs@Yc@a@H_@HSTc@l@}@tDeEl@y@l@s@FEb@ORQ~@aDPe@Ls@UWo@]c@g@Ws@G{@DeEP_BC[Sg@Em@LmFXu@DcBAa@Mo@AWNqHQuAJyEZ_A"  # noqa: E501
        r"@]VkMByFHsFFsBDr@?oA\sFHkERoENmKBoHNkGEwC\aH@wA`@oNHmEDm@EY?y@N}FDyDLoE@iAJ}DHoBN_BTwAU}A?e@B}@LqA?_DHuEEoBBKHINa@?m@C]Ww@O[cA}AcB}CQQa@Y"  # noqa: E501
        )

    pts = np.array(pl.decode(tpl))[:, (1, 0)]
    pts2 = np.array(pl.decode(tpl2))[:, (1, 0)]

    return routes, pts, pts2
