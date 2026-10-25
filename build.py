#!/usr/bin/env python3
"""柴垣医院 テストサイト ビルド（標準ライブラリのみ）

src/ の部品を組み立てて site/ に静的 HTML を書き出す。
  python3 build.py            → site/ を生成
  python3 build.py --check    → 生成せず JSON とリンクの整合だけ確認
"""
import json, re, shutil, sys, time, html, hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SRC, OUT = ROOT / 'src', ROOT / 'site'
# CSS/JS の中身が変わったときだけ変わる版番号（ビルドのたびに全ページが差分になるのを防ぐ）
BUILD = hashlib.sha1((SRC / 'base.css').read_bytes() + (SRC / 'site.js').read_bytes()).hexdigest()[:8]

def load(name):
    return json.loads((SRC / 'data' / name).read_text(encoding='utf-8'))

site, pages, news, recruit, slides = load('site.json'), load('pages.json'), load('news.json'), load('recruit.json'), load('slides.json')
PROD = site.get('production') is True
if PROD and site.get('production_base_url'):
    site['base_url'] = site['production_base_url']
image_notes = load('image_notes.json')
CLINIC_KEY = {'jiyugaoka': 0, 'togoshi': 1, 'kugahara': 2, 'zaitaku': 3}
template = (SRC / 'template.html').read_text(encoding='utf-8')
esc = html.escape

# ---------- 共通部品 ----------
def nav_html(mobile=False):
    out = []
    for item in site['nav']:
        if 'children' in item:
            kids = ''.join(f'<li><a href="{c["url"]}">{esc(c["label"])}</a></li>' for c in item['children'])
            btn = f'<button type="button" class="accordion-elm" aria-expanded="false">{esc(item["label"])}</button>' if mobile \
                else f'<button type="button" aria-expanded="false">{esc(item["label"])}</button>'
            out.append(f'<li class="menu-item menu-item-has-children">{btn}<ul class="sub-menu">{kids}</ul></li>')
        else:
            out.append(f'<li class="menu-item"><a href="{item["url"]}">{esc(item["label"])}</a></li>')
    return '\n'.join('      ' + x for x in out)

def tel_href(t): return 'tel:' + re.sub(r'\D', '', t)
header_phones = '\n'.join(f'          <a href="{tel_href(c["tel"])}"><span>{esc(c["name"])}</span><strong>{c["tel"]}</strong></a>' for c in site['clinics'])
mobile_phones = '\n'.join(f'      <li><a href="{tel_href(c["tel"])}"><span>{esc(c["name"])}</span><strong>{c["tel"]}</strong></a></li>' for c in site['clinics'])
footer_clinics = '\n'.join(
    f'            <div class="clinic-footer__clinic"><dt><a href="{c["url"]}">{esc(c["name"])}</a></dt>'
    f'<dd class="clinic-footer__phone"><a href="{tel_href(c["tel"])}">{c["tel"]}</a></dd>'
    f'<dd class="clinic-footer__location">{c["zip"]}<br>{c["address"]}</dd></div>' for c in site['clinics'])
cols = []
for i, m in enumerate(site['footer_menus']):
    items = ''.join(f'<li><a href="{it["url"]}">{esc(it["label"])}</a></li>' for it in m['items'])
    extra = '\n            <a class="clinic-footer__contact" href="/contact/">お問い合わせ</a>' if i == len(site['footer_menus']) - 1 else ''
    cols.append(f'          <div class="clinic-footer__menu-column"><nav class="clinic-footer__menu" aria-label="{esc(m["heading"])}">'
                f'<h3 class="clinic-footer__heading">{esc(m["heading"])}</h3><ul class="clinic-footer__list">{items}</ul></nav>{extra}</div>')
footer_menus = '\n'.join(cols)
contact_tels = '\n'.join(f'    <li><span>{esc(c["name"])}</span><a href="{tel_href(c["tel"])}">{c["tel"]}</a></li>' for c in site['clinics'])


# ---------- 簡易 Markdown → HTML（編集画面で書いた本文用。HTML で始まる本文はそのまま） ----------
def md_to_html(text):
    if not text or text.lstrip().startswith('<'):
        return text or ''
    def inline(t):
        t = esc(t)
        t = re.sub(r'!\[([^\]]*)\]\(([^)\s]+)\)', r'<img src="\2" alt="\1" loading="lazy">', t)
        t = re.sub(r'\[([^\]]+)\]\(([^)\s]+)\)', r'<a href="\2">\1</a>', t)
        t = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', t)
        return t
    out, para, lst = [], [], None
    def flush_para():
        if para: out.append('<p>' + '<br>'.join(inline(x) for x in para) + '</p>'); para.clear()
    def flush_list():
        nonlocal lst
        if lst: out.append(f'<{lst[0]}>' + ''.join(f'<li>{inline(x)}</li>' for x in lst[1]) + f'</{lst[0]}>'); lst = None
    for line in text.replace('\r', '').split('\n'):
        m = re.match(r'^(#{1,4})\s+(.*)', line)
        if m:
            flush_para(); flush_list(); lvl = min(len(m.group(1)) + 2, 6); out.append(f'<h{lvl}>{inline(m.group(2))}</h{lvl}>'); continue
        m = re.match(r'^\s*[-*]\s+(.*)', line)
        if m:
            flush_para()
            if not lst or lst[0] != 'ul': flush_list(); lst = ['ul', []]
            lst[1].append(m.group(1)); continue
        m = re.match(r'^\s*\d+[.)]\s+(.*)', line)
        if m:
            flush_para()
            if not lst or lst[0] != 'ol': flush_list(); lst = ['ol', []]
            lst[1].append(m.group(1)); continue
        if not line.strip():
            flush_para(); flush_list(); continue
        flush_list(); para.append(line)
    flush_para(); flush_list()
    return '\n'.join(out)

# ---------- お知らせ ----------
def jp_date(iso):
    y, m, d = iso.split('-'); return f'{y}年{m}月{d}日'
items = sorted([n for n in news['items'] if not n.get('draft')], key=lambda n: n['date'], reverse=True)
def news_list(entries, more=False):
    if not entries:
        return '<p class="news-empty">現在、お知らせはありません。</p>'
    li = ''.join(f'<li class="news-list__item"><time class="news-list__date" datetime="{n["date"]}">{jp_date(n["date"])}</time>'
                 f'<span class="news-list__category">{esc(n.get("category","お知らせ"))}</span>'
                 f'<span class="news-list__title"><a href="/news/{n["slug"]}/">{esc(n["title"])}</a></span></li>' for n in entries)
    tail = '<p class="news-list__more"><a href="/news/">お知らせ一覧<span>›</span></a></p>' if more else ''
    return f'<ul class="news-list">{li}</ul>{tail}'
news_top = f'<section id="infoSecID" class="infoSec"><h2>お知らせ</h2>{news_list(items[:5], more=True)}</section>'

# ---------- 採用 募集要項 ----------
def recruit_blocks():
    out = []
    for p in recruit['positions']:
        closed = p.get('status') == '募集終了'
        st = f'<span class="recruit-position__status{" recruit-position__status--closed" if closed else ""}">{esc(p.get("status","募集中"))}</span>'
        rows = ''.join(f'<div class="recruitment-page__requirement"><dt>{esc(f["label"])}</dt><dd>{f["value"] if "<" in f["value"] else esc(f["value"]).replace(chr(10), "<br>")}</dd></div>' for f in p['fields'])
        out.append(f'<div class="recruit-position"><h4 class="recruit-position__title">{esc(p["title"])}{st}</h4>'
                   f'<dl class="recruitment-page__requirements">{rows}</dl></div>')
    return '\n'.join(out)
open_positions = [p for p in recruit['positions'] if p.get('status') != '募集終了']
recruit_opening = ('<h3 class="recruitment-page__current-opening"><span class="recruitment-page__current-opening-label">募集職種：</span>'
                   + ('／'.join(esc(p['title']) for p in open_positions) if open_positions else '現在、募集はありません') + '</h3>')
position_options = '\n'.join(f'        <option>{esc(p["title"])}</option>' for p in open_positions)

# ---------- フォーム ----------
common_fields = (SRC / 'forms' / '_common_fields.html').read_text(encoding='utf-8')
consent_tpl = (SRC / 'forms' / '_consent.html').read_text(encoding='utf-8')
def form_html(name):
    f = (SRC / 'forms' / f'{name}.html').read_text(encoding='utf-8')
    f = f.replace('{{COMMON_FIELDS}}', common_fields).replace('{{CONTACT_TELS}}', contact_tels).replace('{{POSITION_OPTIONS}}', position_options)
    purpose_common = ('<p class="wv-form__purpose">ご入力いただいた内容は、お問い合わせへの回答とご連絡のために使います。ご予約、緊急のご連絡、個別の病状のご相談には、このフォームをお使いいただけません。'
                      '詳しくは<a href="/privacy-policy/" target="_blank" rel="noopener">「個人情報の取り扱いについて」</a>をご覧ください。</p>')
    purpose_recruit = ('<p class="wv-form__purpose">ご入力いただいた内容は、採用選考とご連絡のためだけに使います。'
                       '詳しくは<a href="/privacy-policy/" target="_blank" rel="noopener">「個人情報の取り扱いについて」</a>をご覧ください。</p>')
    def consent(m):
        label = m.group(1).split('|')[0]
        return consent_tpl.replace('{{SUBMIT_LABEL}}', label)
    f = re.sub(r'\{\{PURPOSE:(\w+)\}\}', lambda m: '', f)  # 位置指定は使わず、同意欄の直前に置く
    f = re.sub(r'\{\{CONSENT:([^}]+)\}\}', consent, f)
    f = f.replace('{{PURPOSE}}', purpose_recruit if name.startswith('recruit') else purpose_common)
    return f


# ---------- 電話ブロック（No.55/16：各ページの冒頭と末尾） ----------
def tel_block(keys, bottom=False, lead=None, note=None):
    if not keys: return ''
    items = ''.join(f'<li class="tel-block__item"><a href="{tel_href(site["clinics"][CLINIC_KEY[k]]["tel"])}"><span class="tel-block__name">{esc(site["clinics"][CLINIC_KEY[k]]["name"])}</span><span class="tel-block__number">{site["clinics"][CLINIC_KEY[k]]["tel"]}</span></a></li>' for k in keys)
    zaitaku_first = keys[0] == 'zaitaku'
    lead = lead or ('お電話でのご相談・ご紹介は在宅診療部へ。' if zaitaku_first else 'お電話でのご相談・ご予約はこちらへ。')
    note = ('<p class="tel-block__note">FAX：03-3724-2636　ご紹介は電話か FAX でお願いします。受付時間は診療時間内です。<br>'
            '<strong>訪問診療を受けている方の緊急のご連絡は、契約時にお渡しした連絡先へお願いします。</strong></p>') if zaitaku_first else \
           ('<p class="tel-block__note">' + esc(note) + '</p>' if note else '<p class="tel-block__note">受付時間は各院の診療時間内です（診療時間は各院のページをご覧ください）。</p>')
    cls = 'tel-block tel-block--bottom' if bottom else 'tel-block'
    return f'<div class="{cls}"><p class="tel-block__lead">{lead}</p><ul class="tel-block__list">{items}</ul>{note}</div>'

def toc_nav(items):
    if not items: return ''
    li = ''.join(f'<li><a href="{u}">{esc(t)}</a></li>' for t, u in items)
    return f'<nav class="next-links page-jump" aria-label="このページの内容"><p class="next-links__title">このページの内容</p><ul>{li}</ul></nav>'

def next_links(links):
    if not links: return ''
    li = ''.join(f'<li><a href="{u}">{esc(t)}</a></li>' for t, u in links)
    return f'<nav class="next-links" aria-label="関連ページ"><p class="next-links__title">あわせてご覧ください</p><ul>{li}</ul></nav>'

# ---------- No.26：実際の撮影でない画像の alt と注記 ----------
def apply_image_notes(html_text):
    def fix(m):
        tag = m.group(0)
        src = re.search(r'src="([^"]+)"', tag)
        if not src: return tag
        name = src.group(1).rsplit('/', 1)[-1]
        info = image_notes.get(name)
        if not info: return tag
        tag2 = re.sub(r'alt="[^"]*"', f'alt="{esc(info["alt"])}"', tag) if 'alt=' in tag else tag.replace('<img', f'<img alt="{esc(info["alt"])}"', 1)
        return tag2 + f'<span class="img-note" data-note-for="{name}">{esc(info["note"])}</span>'
    out = re.sub(r'<img\b[^>]*>', fix, html_text)
    # figure の中なら figcaption に寄せる
    out = re.sub(r'(<img\b[^>]*>)<span class="img-note" data-note-for="[^"]+">([^<]*)</span>(\s*)</figure>', r'\1<figcaption class="img-note">\2</figcaption>\3</figure>', out)
    out = re.sub(r'<span class="img-note" data-note-for="[^"]+">([^<]*)</span>', r'<span class="img-note">\1</span>', out)
    return out

def normalize_headings(html_text):
    """No.76/H-9/S-7：最初の h2 を h1 に。本文に h2 が残らなければ h3→h2・h4→h3・h5→h4 に繰り上げ（見た目はクラスで据え置き）"""
    h = first_h2_to_h1(html_text)
    if re.search(r'<h2\b', h): return h, False
    def up(tag_from, tag_to, cls):
        nonlocal h
        def f(m):
            attrs = m.group(1)
            if 'class="' in attrs: attrs = attrs.replace('class="', f'class="{cls} ', 1)
            else: attrs += f' class="{cls}"'
            return f'<{tag_to}{attrs}>'
        h = re.sub(rf'<{tag_from}\b([^>]*)>', f, h)
        h = h.replace(f'</{tag_from}>', f'</{tag_to}>')
    # 衝突を避けるため上から順に（h3→h2 を先にすると h4→h3 が h2 になることはない）
    up('h3', 'h2', 'h-sec'); up('h4', 'h3', 'h-sub'); up('h5', 'h4', 'h-min')
    return h, True

def promote_css_selectors(css):
    """見出しを繰り上げたページでは、ページ専用 CSS の h3/h4/h5 のセレクタも h2/h3/h4 に付け替える（見た目を変えない）"""
    def fix(m):
        sel = m.group(1)
        sel = re.sub(r'\bh5\b', 'h4.h-min', sel); sel = re.sub(r'\bh4\b', 'h3.h-sub', sel); sel = re.sub(r'\bh3\b', 'h2.h-sec', sel)
        return sel + '{'
    return re.sub(r'([^{}]*)\{', lambda m: fix(m) if not m.group(1).strip().startswith('@') else m.group(0), css)

def first_h2_to_h1(html_text):
    # No.76：ページの大見出しを h1 にする（最初の h2 のみ）
    return re.sub(r'<h2(\b[^>]*)>(.*?)</h2>', r'<h1\1>\2</h1>', html_text, count=1, flags=re.S)

# ---------- No.47：トップの構造化データ ----------
def jsonld_top():
    c = site['clinics']
    def addr(x, locality, street):
        return {'@type': 'PostalAddress', 'addressCountry': 'JP', 'addressRegion': '東京都', 'addressLocality': locality, 'streetAddress': street, 'postalCode': x['zip'].replace('〒', '')}
    data = {'@context': 'https://schema.org', '@type': 'MedicalOrganization', 'name': '医療法人社団明洋会 柴垣医院', 'url': site['base_url'] + '/',
            'logo': site['base_url'] + site['logo'], 'telephone': '+81-3-3724-0066',
            'address': addr(c[0], '目黒区', '自由が丘1-13-4 シャイン自由が丘ビル2F'),
            'department': [
                {'@type': 'MedicalClinic', 'name': '柴垣医院 自由が丘', 'url': site['base_url'] + '/jiyugaoka-clinic/', 'telephone': '+81-3-3724-0066', 'address': addr(c[0], '目黒区', '自由が丘1-13-4 シャイン自由が丘ビル2F')},
                {'@type': 'MedicalClinic', 'name': '柴垣医院 戸越', 'url': site['base_url'] + '/togoshi-clinic/', 'telephone': '+81-3-3787-0610', 'address': addr(c[1], '品川区', '平塚1-7-6 2F')},
                {'@type': 'MedicalClinic', 'name': '柴垣医院 久が原', 'url': site['base_url'] + '/kugahara-clinic/', 'telephone': '+81-3-5732-2121', 'address': addr(c[2], '大田区', '西嶺町15-10 ガーデンビル1F・2F')},
                {'@type': 'MedicalClinic', 'name': '柴垣医院 在宅診療部', 'description': '柴垣医院 自由が丘の訪問診療部門', 'url': site['base_url'] + '/home-medical-care/', 'telephone': '+81-3-3724-2626', 'address': addr(c[3], '目黒区', '自由が丘1-13-4 シャイン自由が丘ビル2F'),
                 'areaServed': [{'@type': 'AdministrativeArea', 'name': n} for n in ['目黒区', '品川区', '世田谷区', '渋谷区', '港区', '新宿区', '大田区', '川崎市']]},
            ]}
    return '<script type="application/ld+json">' + json.dumps(data, ensure_ascii=False) + '</script>'

# ---------- ページ出力 ----------
def render(slug, content, *, title, description, page_css='', hero='', breadcrumb_label=None, out_path=None, is_top=False, crumbs_html=None, noindex=False, tel=None, nxt=None, toc=None, tel_lead=None, tel_note=None, crumbs_list=None, og_type='website', extra_jsonld=''):
    label = crumbs_html if crumbs_html is not None else esc(breadcrumb_label or '')
    crumbs = '' if is_top else f'      <nav id="breadcrumbs" aria-label="現在位置"><a href="/">ホーム</a> &gt; {label}</nav>'
    url = '/' if is_top else (pages.get(slug, {}).get('url') or f'/{slug}/')
    content = apply_image_notes(content)
    promoted = False
    if is_top:
        content = '<h1 class="visually-hidden">' + esc(pages['index']['title']) + '</h1>' + content
    else:
        content, promoted = normalize_headings(content)
        if promoted: page_css = promote_css_selectors(page_css)
    css_tag = f'<style>\n{page_css}\n</style>' if page_css.strip() else ''
    if tel and is_top:
        content = content.rstrip() + tel_block(tel, bottom=True)
    elif tel:
        # 冒頭（大見出しの直後）と末尾。自院だけのページは注記を自ページの診療時間へ
        if tel_note is None and len(tel) == 1 and slug.endswith('-clinic'):
            tel_note = '受付時間は診療時間内です（下の「診療時間」をご覧ください）。'
        content = re.sub(r'(</h1>)', lambda m: m.group(1) + tel_block(tel, lead=tel_lead, note=tel_note) + toc_nav(toc), content, count=1)
        content = content.rstrip() + next_links(nxt) + tel_block(tel, bottom=True, lead=tel_lead, note=tel_note)
    elif nxt:
        content = content.rstrip() + next_links(nxt)
    # C-02 BreadcrumbList
    bc = ''
    if not is_top and slug != '404':
        items = [('ホーム', site['base_url'] + '/')] + (crumbs_list or [(breadcrumb_label or '', site['base_url'] + url)])
        bc = '<script type="application/ld+json">' + json.dumps({'@context': 'https://schema.org', '@type': 'BreadcrumbList', 'itemListElement': [
            {'@type': 'ListItem', 'position': i + 1, 'name': n, 'item': u} for i, (n, u) in enumerate(items)]}, ensure_ascii=False) + '</script>'
    robots = '<meta name="robots" content="noindex, nofollow">' if (noindex or not PROD) else '<meta name="robots" content="index, follow">'
    canon_url = site['base_url'].rstrip('/') + url
    canonical_tag = '' if slug == '404' else f'<link rel="canonical" href="{canon_url}">'
    banner = '' if PROD else '<div id="test-banner" role="note">テストサイト（shibagaki.clinic の検証用複製・非公開）</div>'
    h = (template
         .replace('{{TITLE}}', esc(title)).replace('{{DESCRIPTION}}', esc(description))
         .replace('{{CANONICAL}}', site['base_url'].rstrip('/') + url).replace('{{BUILD}}', BUILD)
         .replace('{{ROBOTS}}', robots).replace('{{OG_IMAGE}}', site['base_url'].rstrip('/') + site.get('og_image', site['logo']))
         .replace('{{OG_TYPE}}', og_type).replace('{{CANONICAL_TAG}}', canonical_tag).replace('{{TEST_BANNER}}', banner)
         .replace('{{JSONLD}}', (jsonld_top() if is_top else '') + bc + extra_jsonld)
         .replace('{{PAGE_CSS}}', css_tag).replace('{{BODY_CLASS}}', 'bodyhome' if is_top else 'bodysub')
         .replace('{{WRAPPER_CLASS}}', 'page_weveryhome' if is_top else 'page_weverysub')
         .replace('{{LOGO}}', site['logo']).replace('{{LOGO_ALT}}', esc(site['logo_alt']))
         .replace('{{HEADER_PHONES}}', header_phones).replace('{{MOBILE_PHONES}}', mobile_phones)
         .replace('{{NAV}}', nav_html()).replace('{{MOBILE_NAV}}', nav_html(mobile=True))
         .replace('{{HERO}}', hero).replace('{{BREADCRUMBS}}', crumbs).replace('{{CONTENT}}', content)
         .replace('{{FOOTER_CLINICS}}', footer_clinics).replace('{{FOOTER_MENUS}}', footer_menus)
         .replace('{{COPYRIGHT}}', esc(site['copyright'])))
    leftover = re.findall(r'\{\{[A-Z_]+(?::[^}]*)?\}\}', h)
    if leftover: raise SystemExit(f'{slug}: 未置換のプレースホルダ {leftover}')
    p = out_path or (OUT / ('index.html' if is_top else (pages.get(slug, {}).get('out') or f'{slug}/index.html')))
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(h, encoding='utf-8')
    return p

def hero_html():
    parts = []
    for i, sl in enumerate(slides['slides']):
        active = ' is-active' if i == 0 else ''
        lazy = 'fetchpriority="high" ' if i == 0 else 'loading="lazy" '
        note = '<p class="hero-slider__note">写真はイメージです（当院の職員・患者さんではありません）</p>' if sl.get('note') else ''
        inner = (f'<img src="{sl["image"]}" alt="" {lazy}width="1784" height="882">'
                 f'<div class="hero-slider__caption"><p class="hero-slider__title">{esc(sl["title"])}</p><p class="hero-slider__desc">{esc(sl["desc"])}</p></div>')
        if sl.get('link'): inner = f'<a class="hero-slider__link" href="{sl["link"]}">{inner}</a>'
        parts.append(f'<div class="hero-slider__slide{active}">{inner}{note}</div>')
    dots = []
    for i in range(len(slides['slides'])):
        cur = ' aria-current="true"' if i == 0 else ''
        dots.append(f'<li><button type="button" aria-label="スライド{i+1}"{cur}></button></li>')
    return ('  <div id="images"><div class="hero-slider" role="region" aria-roledescription="carousel" aria-label="メインビジュアル">' + ''.join(parts)
            + '<button type="button" class="hero-slider__nav hero-slider__nav--prev" aria-label="前のスライド">‹</button>'
            '<button type="button" class="hero-slider__nav hero-slider__nav--next" aria-label="次のスライド">›</button>'
            '<ul class="hero-slider__dots">' + ''.join(dots) + '</ul></div></div>')

def main():
    check = '--check' in sys.argv
    if not check:
        for d in ('assets/css', 'assets/js'):
            (OUT / d).mkdir(parents=True, exist_ok=True)
        for sub in OUT.iterdir():
            if sub.is_dir() and sub.name not in ('assets', 'admin'): shutil.rmtree(sub)
            elif sub.is_file(): sub.unlink()
        shutil.copy(SRC / 'base.css', OUT / 'assets/css/base.css')
        shutil.copy(SRC / 'site.js', OUT / 'assets/js/site.js')
    written = []
    for slug, meta in pages.items():
        content = (SRC / 'pages' / f'{slug}.html').read_text(encoding='utf-8')
        css_p = SRC / 'pages' / f'{slug}.css'
        page_css = css_p.read_text(encoding='utf-8') if css_p.exists() else ''
        hero = ''
        if slug == 'index':
            content = content.replace('{{NEWS_TOP}}', news_top); hero = hero_html()
        if slug == 'recruit':
            content = content.replace('{{RECRUIT_OPENING}}', recruit_opening).replace('{{RECRUIT_REQUIREMENTS}}', recruit_blocks())
        if meta.get('form'):
            content = content.replace('{{FORM}}', form_html(meta['form']))
        if slug == 'faq':
            if open_positions:
                ans = '／'.join(esc(p_['title']) for p_ in open_positions) + 'を募集しています（常勤・非常勤）。'
                closed = [p_ for p_ in recruit['positions'] if p_.get('status') == '募集終了']
                if closed: ans += '／'.join(esc(p_['title']) for p_ in closed) + 'は現在募集していません。'
            else:
                ans = '現在、募集はありません。'
            content = content.replace('{{FAQ_RECRUIT}}', f'<p>{ans}詳しくは<a href="/recruit/">採用情報</a>をご覧ください。</p>')
        if slug == 'recruit':
            content = content.replace('{{DOCTOR_MESSAGE}}', esc(recruit.get('doctor_message') or '理事長からのメッセージ（どのような医師と働きたいか）は、準備ができ次第こちらに掲載します。'))
        extra_ld = ''
        if meta.get('jsonld'):
            extra_ld += '<script type="application/ld+json">' + json.dumps(meta['jsonld'], ensure_ascii=False).replace('{BASE}', site['base_url']) + '</script>'
        if slug == 'faq':
            qa = []
            for q, a in re.findall(r'<button class="faq-page__question"[^>]*>\s*<span class="faq-page__mark"[^>]*>Q</span>\s*<span>(.*?)</span>.*?<div class="faq-page__answer"[^>]*>\s*<span[^>]*>A</span>\s*<p>(.*?)</p>', content, flags=re.S):
                qa.append({'@type': 'Question', 'name': re.sub(r'<[^>]+>', '', q).strip(), 'acceptedAnswer': {'@type': 'Answer', 'text': re.sub(r'<[^>]+>', '', a).strip()}})
            if qa: extra_ld += '<script type="application/ld+json">' + json.dumps({'@context': 'https://schema.org', '@type': 'FAQPage', 'mainEntity': qa}, ensure_ascii=False) + '</script>'
        if slug == 'index':
            content = content.replace('{{RECRUIT_OPENING_TOP}}', '<p class="recruitment-top__positions">現在の募集：' + ('／'.join(esc(p_['title']) for p_ in open_positions) if open_positions else '現在、募集はありません') + '</p>')
        if check: continue
        written.append(render(slug, content, title=meta['title'], description=meta['description'], page_css=page_css, hero=hero,
                              breadcrumb_label=meta['heading'], is_top=(slug == 'index'), noindex=meta.get('noindex', False),
                              tel=meta.get('tel'), nxt=meta.get('next'), toc=meta.get('toc'), tel_lead=meta.get('tel_lead'), tel_note=meta.get('tel_note'),
                              crumbs_html=meta.get('crumbs_html'), extra_jsonld=extra_ld))
    # お知らせ一覧・詳細
    if not check:
        lst = f'<section class="pageSec"><h2>お知らせ</h2><div class="subpagecontents">{news_list(items)}</div></section>'
        written.append(render('news', lst, title='お知らせ｜柴垣医院', description='柴垣医院からのお知らせ・勉強会のご案内・活動報告の一覧です。', breadcrumb_label='お知らせ'))
        for n in items:
            body = (f'<section class="pageSec"><h2>{esc(n["title"])}</h2>'
                    f'<p class="news-post__meta"><time datetime="{n["date"]}">{jp_date(n["date"])}</time><span class="news-list__category">{esc(n.get("category","お知らせ"))}</span></p>'
                    f'<div class="subpagecontents news-post__body">{md_to_html(n["body"])}</div>'
                    f'<p class="news-post__back"><a class="wv-button" href="/news/">お知らせ一覧へ</a></p></section>')
            art_ld = '<script type="application/ld+json">' + json.dumps({'@context': 'https://schema.org', '@type': 'NewsArticle', 'headline': n['title'], 'datePublished': n['date'],
                     'publisher': {'@type': 'MedicalOrganization', 'name': '医療法人社団明洋会 柴垣医院'}, 'mainEntityOfPage': f"{site['base_url']}/news/{n['slug']}/"}, ensure_ascii=False) + '</script>'
            written.append(render(f'news/{n["slug"]}', body, title=f'{n["title"]}｜柴垣医院', description=n.get('description') or re.sub(r'<[^>]+>', '', md_to_html(n['body']))[:110],
                                  crumbs_html=f'<a href="/news/">お知らせ</a> &gt; {esc(n["title"])}', og_type='article', extra_jsonld=art_ld,
                                  crumbs_list=[('お知らせ', site['base_url'] + '/news/'), (n['title'], f"{site['base_url']}/news/{n['slug']}/")]))
        # 検索避け・Netlify 用
        (OUT / 'robots.txt').write_text(('User-agent: *\nAllow: /\nSitemap: ' + site['base_url'] + '/sitemap.xml\n') if PROD else 'User-agent: *\nDisallow: /\n', encoding='utf-8')
        nf = ('<section class="pageSec"><h2>ページが見つかりませんでした</h2><div class="subpagecontents"><div class="thanks-box"><p>URL が変更されたか、ページが削除された可能性があります。</p>'
              '<p><a class="wv-button" href="/">トップページへ戻る</a></p></div></div></section>')
        render('404', nf, title='ページが見つかりませんでした｜柴垣医院', description='', breadcrumb_label='404', out_path=OUT / '404.html', noindex=True,
               tel=['jiyugaoka', 'togoshi', 'kugahara', 'zaitaku'], nxt=[['自由が丘', '/jiyugaoka-clinic/'], ['戸越', '/togoshi-clinic/'], ['久が原', '/kugahara-clinic/'], ['在宅診療', '/home-medical-care/'], ['お問い合わせ', '/contact/']])
        # sitemap.xml（フォーム・完了・404 は除外）
        urls = [site['base_url'] + '/'] + [f"{site['base_url']}/{s_}/" for s_, m in pages.items() if s_ != 'index' and not m.get('noindex')] + [site['base_url'] + '/news/'] + [f"{site['base_url']}/news/{n['slug']}/" for n in items]
        (OUT / 'sitemap.xml').write_text('<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">' + ''.join(f'<url><loc>{u}</loc></url>' for u in urls) + '</urlset>\n', encoding='utf-8')
    # 内部リンク検査
    broken = []
    for p in OUT.rglob('*.html'):
        for href in re.findall(r'(?:href|src)="(/[^"#?]*)', p.read_text(encoding='utf-8')):
            t = OUT / href.lstrip('/')
            if not (t.exists() or (t / 'index.html').exists()): broken.append((str(p.relative_to(OUT)), href))
    print(f'pages: {len(written)}  broken links: {len(broken)}')
    for b in broken[:40]: print('  BROKEN', *b)
    return 1 if broken else 0

if __name__ == '__main__':
    sys.exit(main())
