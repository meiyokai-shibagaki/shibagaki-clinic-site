#!/usr/bin/env python3
"""訪問エリアの地図（SVG）を生成する。

入力：市区町村境界の GeoJSON（niiyz/JapanCityGeoJson、国土数値情報 N03 由来）を置いたフォルダ
使い方：python3 tools/make_area_map.py <geojsonフォルダ> site/assets/img/visiting-area-map.svg
"""
import json, math, sys, pathlib

SRC = pathlib.Path(sys.argv[1]); OUT = pathlib.Path(sys.argv[2])
TARGET = {'13110': '目黒区', '13109': '品川区', '13112': '世田谷区', '13113': '渋谷区', '13103': '港区', '13104': '新宿区', '13111': '大田区'}
KAWASAKI = {'14131', '14132', '14133', '14134', '14135', '14136', '14137'}
CONTEXT_LABEL = {'13115': '杉並区', '13114': '中野区', '13101': '千代田区', '13102': '中央区', '13208': '調布市', '13219': '狛江市', '13120': '練馬区', '13116': '豊島区', '13105': '文京区'}
SKIP = {'13108', '13107', '13106', '13118', '13117', '13119', '13121', '13122', '13123'}  # 江東・墨田・台東・荒川・北・板橋・足立・葛飾・江戸川
LON0, LON1, LAT0, LAT1 = 139.555, 139.865, 35.465, 35.745
W = 1000.0
COS = math.cos(math.radians(35.6))
S = W / ((LON1 - LON0) * COS)
H = (LAT1 - LAT0) * S

def proj(lon, lat):
    return ((lon - LON0) * COS * S, (LAT1 - lat) * S)

def dp(points, eps):
    """Douglas–Peucker で点を間引く（反復版。閉じた輪は最遠点で2つに分けてから処理）"""
    if len(points) < 3: return points
    if points[0] == points[-1]: points = points[:-1]
    # 始点から最も遠い点で2分割（閉じた輪は始点＝終点だと基準線が引けないため）
    x0, y0 = points[0]
    far = max(range(len(points)), key=lambda i: (points[i][0] - x0) ** 2 + (points[i][1] - y0) ** 2)
    def simplify(seg):
        keep = [False] * len(seg); keep[0] = keep[-1] = True
        stack = [(0, len(seg) - 1)]
        while stack:
            a, b = stack.pop()
            if b - a < 2: continue
            (x1, y1), (x2, y2) = seg[a], seg[b]
            dx, dy = x2 - x1, y2 - y1; norm = math.hypot(dx, dy) or 1e-9
            idx, dmax = a, 0.0
            for i in range(a + 1, b):
                px, py = seg[i]
                d = abs(dy * px - dx * py + x2 * y1 - y2 * x1) / norm
                if d > dmax: idx, dmax = i, d
            if dmax > eps:
                keep[idx] = True; stack.append((a, idx)); stack.append((idx, b))
        return [pt for pt, k in zip(seg, keep) if k]
    first = simplify(points[:far + 1]); second = simplify(points[far:] + [points[0]])
    return first[:-1] + second[:-1]

def polys(geom):
    if geom['type'] == 'Polygon': return [geom['coordinates']]
    return geom['coordinates']

def ring_area(pts):
    a = 0.0
    for i in range(len(pts)):
        (x1, y1), (x2, y2) = pts[i], pts[(i + 1) % len(pts)]
        a += x1 * y2 - x2 * y1
    return abs(a) / 2

def path_for(feature, eps=1.2):
    d = []
    for poly in polys(feature['geometry']):
        ring = poly[0]
        raw = [proj(lon, lat) for lon, lat in ring]
        if ring_area(raw) < 600: continue  # 小さな島・飛び地は描かない（中央防波堤など）
        pts = dp(raw, eps)
        if len(pts) < 3: continue
        d.append('M' + ' L'.join(f'{x:.1f},{y:.1f}' for x, y in pts) + 'Z')
    return ''.join(d)

def centroid(feature):
    # 最大の外周リングの単純な重心
    best, area_best = None, 0
    for poly in polys(feature['geometry']):
        ring = [proj(lon, lat) for lon, lat in poly[0]]
        a = cx = cy = 0.0
        for i in range(len(ring) - 1):
            (x1, y1), (x2, y2) = ring[i], ring[i + 1]
            f = x1 * y2 - x2 * y1; a += f; cx += (x1 + x2) * f; cy += (y1 + y2) * f
        if abs(a) > area_best and a != 0:
            area_best = abs(a); best = (cx / (3 * a), cy / (3 * a))
    return best

feats = {}
for f in sorted(SRC.glob('*.json')):
    data = json.loads(f.read_text(encoding='utf-8'))
    for ft in data['features']:
        code = ft['properties'].get('N03_007') or f.stem
        feats[code] = ft

base, target, kawa, labels = [], [], [], []
for code, ft in feats.items():
    if code in SKIP: continue
    d = path_for(ft)
    if code in TARGET:
        target.append(f'<path d="{d}"/>')
        c = centroid(ft); labels.append((TARGET[code], c, True))
    elif code in KAWASAKI:
        kawa.append(f'<path d="{d}"/>')
    else:
        base.append(f'<path d="{d}"/>')
        if code in CONTEXT_LABEL:
            c = centroid(ft); labels.append((CONTEXT_LABEL[code], c, False))
# 川崎市のラベルは市全体の中心あたり（中原区の重心を使う）
kc = centroid(feats['14133']); labels.append(('川崎市', (kc[0] - 10, kc[1] + 20), True))
# 横浜市は複数区なので1つのラベル
labels.append(('横浜市', proj(139.62, 35.49), False))
# 拠点のピン（座標は各院ページに埋め込んだ Google マップの中心値）
PINS = [
    ('自由が丘・在宅診療部', 139.66813, 35.60860, 'end', -14, 34),
    ('戸越', 139.71416, 35.61530, 'start', 14, -10),
    ('久が原', 139.68238, 35.58017, 'start', 14, 30),
]

def pin_svg(name, lon, lat, anchor, dx, dy):
    x, y = proj(lon, lat)
    return (f'<circle class="pin" cx="{x:.1f}" cy="{y:.1f}" r="9"/>'
            f'<text class="pinlbl" x="{x + dx:.1f}" y="{y + dy:.1f}" text-anchor="{anchor}">{name}</text>')

def text(t, x, y, strong):
    cls = 'lbl-t' if strong else 'lbl-c'
    return f'<text class="{cls}" x="{x:.1f}" y="{y:.1f}" text-anchor="middle">{t}</text>'

svg = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W:.0f} {H:.0f}" width="{W:.0f}" height="{H:.0f}" role="img" aria-labelledby="t d">
<title id="t">訪問診療に伺えるエリアの地図</title>
<desc id="d">目黒区・品川区・世田谷区・渋谷区・港区・新宿区・大田区と川崎市を塗り分けた地図。柴垣医院の3院（自由が丘・戸越・久が原）と在宅診療部の位置を示す。</desc>
<style>
.base{{fill:#efefec;stroke:#ffffff;stroke-width:1.5}}
.target{{fill:#b9d0d2;stroke:#ffffff;stroke-width:1.5}}
.kawa{{fill:#d7e4e5;stroke:#ffffff;stroke-width:1.5}}
.lbl-t{{font-family:"Zen Old Mincho","Hiragino Mincho ProN",serif;font-size:21px;font-weight:600;fill:#2c4256}}
.lbl-c{{font-family:"Zen Old Mincho","Hiragino Mincho ProN",serif;font-size:16px;fill:#8a9496}}
.pin{{fill:#c9655a;stroke:#fff;stroke-width:3}}
.pinlbl{{font-family:"Zen Old Mincho","Hiragino Mincho ProN",serif;font-size:18px;font-weight:600;fill:#c9655a}}
.legend{{font-family:"Zen Old Mincho","Hiragino Mincho ProN",serif;font-size:16px;fill:#424242}}
</style>
<rect width="{W:.0f}" height="{H:.0f}" fill="#ffffff"/>
<g class="base">{''.join(base)}</g>
<g class="kawa">{''.join(kawa)}</g>
<g class="target">{''.join(target)}</g>
{''.join(text(t, x, y, s) for t, (x, y), s in labels)}
{''.join(pin_svg(*pn) for pn in PINS)}
<g transform="translate(24,{H - 96:.0f})">
<rect x="0" y="0" width="26" height="18" class="target"/><text class="legend" x="34" y="15">定期訪問を行っている区</text>
<rect x="0" y="28" width="26" height="18" class="kawa"/><text class="legend" x="34" y="43">川崎市（多摩川に近い地域）</text>
<circle class="pin" cx="13" cy="64" r="7"/><text class="legend" x="34" y="69">柴垣医院の拠点（自由が丘・戸越・久が原）</text>
</g>
</svg>
'''
OUT.write_text(svg, encoding='utf-8')
print('wrote', OUT, len(svg), 'bytes; features', len(feats), 'target', len(target), 'kawasaki', len(kawa))
