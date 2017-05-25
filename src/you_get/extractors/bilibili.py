#!/usr/bin/env python

__all__ = ['bilibili_download']

from ..common import *
from ..util.log import *

from .qq import qq_download_by_vid
from .sina import sina_download_by_vid
from .tudou import tudou_download_by_id
from .youku import youku_download_by_vid

import hashlib
import re
import time
import json
import http.cookiejar
import urllib.request

appkey = 'f3bb208b3d081dc8'
SECRETKEY_MINILOADER = '1c15888dc316e05a15fdd0a02ed6584f'
SEC2 = '9b288147e5474dd2aa67085f716c560d'

def check_oversea():
    url = 'https://interface.bilibili.com/player?id=cid:17778881'
    xml_lines = get_content(url).split('\n')
    for line in xml_lines:
        key = line.split('>')[0][1:]
        if key == 'country':
            value = line.split('>')[1].split('<')[0]
            if value != '中国':
                return True
            else:
                return False
    return False

def check_sid():
    if not cookies:
        return False
    for cookie in cookies:
        if cookie.domain == '.bilibili.com' and cookie.name == 'sid':
            return True
    return False

def fetch_sid(cid, aid):
    url = 'http://interface.bilibili.com/player?id=cid:{}&aid={}'.format(cid, aid)
    cookies = http.cookiejar.CookieJar()
    req = urllib.request.Request(url)
    res = urllib.request.urlopen(url)
    cookies.extract_cookies(res, req)
    for c in cookies:
        if c.domain == '.bilibili.com' and c.name == 'sid':
            return c.value
    raise

def sign(cid, fallback=False, oversea=False):
    base_req = 'cid={}&player=1'.format(cid)
    if oversea:
        base_req = 'accel=1&' + base_req
    if fallback:
        base_req += '&quality=2'
    base_req = base_req + '&ts=' + str(int(time.time()))
    to_sign = (base_req + SECRETKEY_MINILOADER).encode('utf8')
    return base_req + '&sign=' + hashlib.md5(to_sign).hexdigest()

def sign_bangumi(cid, ts = None):
    if ts is None:
        ts = str(int(time.time()))
    base_req = 'cid={}&module=bangumi&player=1&quality=4&ts={}'.format(cid, ts)
    to_sign = (base_req + SEC2).encode('utf8')
    return base_req + '&sign=' + hashlib.md5(to_sign).hexdigest()

def collect_bangumi_epids(json_data):
    eps = json_data['result']['episodes']
    result = []
    for ep in eps:
        result.append(ep['episode_id'])
    return sorted(result)

def get_bangumi_info(bangumi_id):
    BASE_URL = 'http://bangumi.bilibili.com/jsonp/seasoninfo/'
    long_epoch = int(time.time() * 1000)
    req_url = BASE_URL + bangumi_id + '.ver?callback=seasonListCallback&jsonp=jsonp&_=' + str(long_epoch)
    season_data = get_content(req_url)
    season_data = season_data[len('seasonListCallback('):]
    season_data = season_data[: -1 * len(');')]
    json_data = json.loads(season_data)
    return json_data

def get_srt_xml(id):
    url = 'http://comment.bilibili.com/%s.xml' % id
    return get_html(url)


def parse_srt_p(p):
    fields = p.split(',')
    assert len(fields) == 8, fields
    time, mode, font_size, font_color, pub_time, pool, user_id, history = fields
    time = float(time)

    mode = int(mode)
    assert 1 <= mode <= 8
    # mode 1~3: scrolling
    # mode 4: bottom
    # mode 5: top
    # mode 6: reverse?
    # mode 7: position
    # mode 8: advanced

    pool = int(pool)
    assert 0 <= pool <= 2
    # pool 0: normal
    # pool 1: srt
    # pool 2: special?

    font_size = int(font_size)

    font_color = '#%06x' % int(font_color)

    return pool, mode, font_size, font_color


def parse_srt_xml(xml):
    d = re.findall(r'<d p="([^"]+)">(.*)</d>', xml)
    for x, y in d:
        p = parse_srt_p(x)
    raise NotImplementedError()


def parse_cid_playurl(xml):
    from xml.dom.minidom import parseString
    try:
        urls_list = []
        total_size = 0
        doc = parseString(xml.encode('utf-8'))
        durls = doc.getElementsByTagName('durl')
        cdn_cnt = len(durls[0].getElementsByTagName('url'))
        for i in range(cdn_cnt):
            urls_list.append([])
        for durl in durls:
            size = durl.getElementsByTagName('size')[0]
            total_size += int(size.firstChild.nodeValue)
            cnt = len(durl.getElementsByTagName('url'))
            for i in range(cnt):
                u = durl.getElementsByTagName('url')[i].firstChild.nodeValue
                urls_list[i].append(u)
        return urls_list, total_size
    except Exception as e:
        log.w(e)
        return [], 0


def bilibili_download_by_cids(cids, title, output_dir='.', merge=True, info_only=False):
    urls = []
    for cid in cids:
        sign_this = hashlib.md5(bytes('cid={cid}&from=miniplay&player=1{SECRETKEY_MINILOADER}'.format(cid = cid, SECRETKEY_MINILOADER = SECRETKEY_MINILOADER), 'utf-8')).hexdigest()
        url = 'http://interface.bilibili.com/playurl?&cid=' + cid + '&from=miniplay&player=1' + '&sign=' + sign_this
        urls += [i
                 if not re.match(r'.*\.qqvideo\.tc\.qq\.com', i)
                 else re.sub(r'.*\.qqvideo\.tc\.qq\.com', 'http://vsrc.store.qq.com', i)
                 for i in parse_cid_playurl(get_content(url))]

    type_ = ''
    size = 0
    for url in urls:
        _, type_, temp = url_info(url)
        size += temp

    print_info(site_info, title, type_, size)
    if not info_only:
        download_urls(urls, title, type_, total_size=None, output_dir=output_dir, merge=merge, headers={'Referer': 'http://www.bilibili.com/'})

def test_bili_cdns(urls_list):
    import urllib.error
    headers = {}
    headers['Referer'] = 'bilibili.com'
    headers['User-Agent'] = 'Mozilla/5.0'
    for pos, urls in enumerate(urls_list):
        try:
            _, t, size = url_info(urls[0], headers=headers)
        except urllib.error.HTTPError:
            log.w('HTTPError with url '+urls[0])
        else:
            return pos, t, size
    return -1, None, 0

def bilibili_download_by_cid(cid, title, output_dir='.', merge=True, info_only=False, is_bangumi=False, aid=None, oversea=False):
        endpoint = 'https://interface.bilibili.com/playurl?'
        endpoint_paid = 'https://bangumi.bilibili.com/player/web_api/playurl?'
        if is_bangumi:
            if not check_sid():
                sid_cstr = 'sid=' + fetch_sid(cid, aid)
                headers = dict(referer='bilibili.com', cookie=sid_cstr)
            else:
                headers = dict(referer='bilibili.com')
            url = endpoint_paid + sign_bangumi(cid)
        else:
            url = endpoint + sign(cid, oversea=oversea)
            headers = dict(referer='bilibili.com')
        content = get_content(url, headers)
        urls_list, size = parse_cid_playurl(content)
        pos, type_, mp4size = test_bili_cdns(urls_list)
        if pos == -1:
            if is_bangumi:
                log.wtf('All CDNs failed so You Can NOT Advance')
                raise
            else:
                log.w('CDNs failed. Trying fallback')
                url = endpoint + sign(cid, fallback=True, oversea=oversea)
                headers = dict(referer='bilibili.com')
                content = get_content(url, headers)
                urls_list, size = parse_cid_playurl(content)
                pos, type_, mp4size = test_bili_cdns(urls_list)
                if pos == -1:
                    log.wtf('Fallback tried but no luck')
                    raise
        if '.mp4' in urls_list[0]:
            size = mp4size
        urls = [i
                if not re.match(r'.*\.qqvideo\.tc\.qq\.com', i)
                else re.sub(r'.*\.qqvideo\.tc\.qq\.com', 'http://vsrc.store.qq.com', i)
                for i in urls_list[pos]]

        print_info(site_info, title, type_, size)
        if not info_only:
            while True:
                try:
                    headers = {}
                    headers['Referer'] = 'bilibili.com'
                    headers['User-Agent'] = 'Mozilla/5.0'
                    download_urls(urls, title, type_, total_size=size, output_dir=output_dir, merge=merge, timeout=15, headers=headers)
                except socket.timeout:
                    continue
                else:
                    break


def bilibili_live_download_by_cid(cid, title, output_dir='.', merge=True, info_only=False):
    api_url = 'http://live.bilibili.com/api/playurl?cid=' + cid + '&otype=json'
    json_data = json.loads(get_content(api_url))
    urls = [json_data['durl'][0]['url']]

    for url in urls:
        _, type_, _ = url_info(url)
        size = 0
        print_info(site_info, title, type_, size)
        if not info_only:
            download_urls([url], title, type_, total_size=None, output_dir=output_dir, merge=merge)


def bilibili_download(url, output_dir='.', merge=True, info_only=False, **kwargs):
    #oversea = check_oversea()
    oversea = False
    url = url_locations([url])[0]
    html = get_content(url)

    title = r1_of([r'<meta name="title" content="\s*([^<>]{1,999})\s*" />',
                   r'<h1\s*title="([^\"]+)">.*</h1>'], html)
    if title:
        title = unescape_html(title)
        title = escape_file_path(title)

    if re.match(r'https?://bangumi\.bilibili\.com/', url):
        # quick hack for bangumi URLs
        bangumi_id = match1(url, r'(\d+)')
        bangumi_data = get_bangumi_info(bangumi_id)
        if bangumi_data['result'].get('payment') and bangumi_data['result']['payment']['price'] != '0':
            log.w("It's a paid item")
        ep_ids = collect_bangumi_epids(bangumi_data)
        episode_id = r1(r'#(\d+)$', url) or r1(r'first_ep_id = "(\d+)"', html)
        cont = post_content('http://bangumi.bilibili.com/web_api/get_source',
                            post_data={'episode_id': episode_id})
        cid = json.loads(cont)['result']['cid']
        cont = get_content('http://bangumi.bilibili.com/web_api/episode/' + episode_id + '.json')
        ep_info = json.loads(cont)
        long_title = ep_info['result']['currentEpisode']['longTitle']
        aid = ep_info['result']['currentEpisode']['avId']
        idx = 0
        while ep_ids[idx] != episode_id:
            idx += 1
        title = '%s [%s %s]' % (title, idx+1, long_title)
        bilibili_download_by_cid(str(cid), title, output_dir=output_dir, merge=merge, info_only=info_only, is_bangumi=True, aid=aid, oversea=oversea)

    else:
        tc_flashvars = match1(html, r'"bili-cid=\d+&bili-aid=\d+&vid=([^"]+)"')
        if tc_flashvars is not None:
            qq_download_by_vid(tc_flashvars, title, output_dir=output_dir, merge=merge, info_only=info_only)
            return

        flashvars = r1_of([r'(cid=\d+)', r'(cid: \d+)', r'flashvars="([^"]+)"',
                           r'"https://[a-z]+\.bilibili\.com/secure,(cid=\d+)(?:&aid=\d+)?"', r'(ROOMID\s*=\s*\d+)'], html)
        assert flashvars
        flashvars = flashvars.replace(': ', '=')
        t, cid = flashvars.split('=', 1)
        t = t.strip()
        cid = cid.split('&')[0].strip()
        if t == 'cid' or t == 'ROOMID':
            if re.match(r'https?://live\.bilibili\.com/', url):
                title = r1(r'<title>\s*([^<>]+)\s*</title>', html)
                bilibili_live_download_by_cid(cid, title, output_dir=output_dir, merge=merge, info_only=info_only)

            else:
                # multi-P
                cids = []
                pages = re.findall('<option value=\'([^\']*)\'', html)
                titles = re.findall('<option value=.*>\s*([^<>]+)\s*</option>', html)
                for i, page in enumerate(pages):
                    html = get_html("http://www.bilibili.com%s" % page)
                    flashvars = r1_of([r'(cid=\d+)',
                                       r'flashvars="([^"]+)"',
                                       r'"https://[a-z]+\.bilibili\.com/secure,(cid=\d+)(?:&aid=\d+)?"'], html)
                    if flashvars:
                        t, cid = flashvars.split('=', 1)
                        cids.append(cid.split('&')[0])
                    if url.endswith(page):
                        cids = [cid.split('&')[0]]
                        titles = [titles[i]]
                        break

                # no multi-P
                if not pages:
                    cids = [cid]
                    titles = [r1(r'<option value=.* selected>\s*([^<>]+)\s*</option>', html) or title]
                for i in range(len(cids)):
                    completeTitle=None
                    if (title == titles[i]):
                        completeTitle=title
                    else:
                        completeTitle=title+"-"+titles[i]#Build Better Title
                    bilibili_download_by_cid(cids[i],
                                             completeTitle,
                                             output_dir=output_dir,
                                             merge=merge,
                                             info_only=info_only,
                                             oversea=oversea)

        elif t == 'vid':
            sina_download_by_vid(cid, title=title, output_dir=output_dir, merge=merge, info_only=info_only)
        elif t == 'ykid':
            youku_download_by_vid(cid, title=title, output_dir=output_dir, merge=merge, info_only=info_only)
        elif t == 'uid':
            tudou_download_by_id(cid, title, output_dir=output_dir, merge=merge, info_only=info_only)
        else:
            raise NotImplementedError(flashvars)

    if not info_only and not dry_run:
        if not kwargs['caption']:
            print('Skipping danmaku.')
            return
        title = get_filename(title)
        print('Downloading %s ...\n' % (title + '.cmt.xml'))
        xml = get_srt_xml(cid)
        with open(os.path.join(output_dir, title + '.cmt.xml'), 'w', encoding='utf-8') as x:
            x.write(xml)


site_info = "bilibili.com"
download = bilibili_download
download_playlist = bilibili_download
