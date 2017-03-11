try:
    import pycurl
except ImportError:
    log.w('Error importing pycurl library. -4 and -6 flags ignored')

import io

if __name__ is '__main__':
#for test
    ipv4 = False
    ipv6 = False
    fake_headers = {}
    proxy = None

class Recv_headers():
    headers = {}

    def __init__(self):
        self.headers = {}

    def __getitem__(self, name):
        return self.headers.get(name)
    
    def __setitem__(self, name, val):
        self.headers[name.lower()] = val

    def __delitem__(self, name):
        del self.headers[name.lower()]

    def __contains__(self, name):
        return name.lower() in self.headers

    def __iter__(self):
        return self.headers.__iter__

    def __next__(self):
        return self.headers.__next__

    def get(self, name, default_val=None):
        if name in self.headers:
            return self.headers[name]
        return default_val

    def dict_headers(self):
        import copy
        return copy.deepcopy(self.headers)

    def input(self, header_line):
        data = header_line.decode('iso-8859-1')
        if ':' not in data:
            return

        first_sep = data.find(':')
        if first_sep == -1:
            print("bad header line: {0}".format(data))
            return

        key = data[:first_sep]
        val = data[first_sep+1:]
        self.headers[key.strip().lower()] = val.strip()

def init_curl_obj(proxy=None, socks_proxy=None, timeout=600, ipv4_only=False, ipv6_only=False):
    c = pycurl.Curl()
    c = set_curl_proxy(c, proxy, socks_proxy)
    c.setopt(pycurl.CONNECTTIMEOUT, timeout)
    c.setopt(pycurl.FOLLOWLOCATION, True)
    if ipv4_only:
        c.setopt(pycurl.DNS_LOCAL_IP4, None)
    elif ipv6_only:
        c.setopt(pycurl.DNS_LOCAL_IP6, None)

    c.setopt(pycurl.ACCEPT_ENCODING, "gzip, deflate")
    return c

def install_headers(c, headers_dict):
    for key in headers_dict:
        val = headers_dict[key]
        c.setopt(pycurl.HTTPHEADER, (key+':', val))

def set_curl_proxy(c, proxy, socks_proxy):
    if proxy:
        c.setopt(pycurl.PROXY, 'http://' + proxy)
    elif socks_proxy:
        c.setopt(pycurl.PROXY, 'socks5h://' + socks_proxy)
    return c

def unset_curl_proxy(c):
    c.unsetopt(pycurl.PROXY)
    return c

def get_response(url, faker=None, return_headers=False):
    c = init_curl_obj()
    headers = Recv_headers()
    buffer = io.BytesIO()
    if faker:
        install_headers(faker)
    c.setopt(pycurl.URL, url)
    c.setopt(pycurl.WRITEFUNCTION, buffer.write)
    if return_headers:
        c.setopt(pycurl.HEADERFUNCTION, headers.input)
    c.perform()

    if return_headers:
        return (buffer.getvalue(), headers)

    return buffer.getvalue()

def get_html(url, encoding=None, faker=None):
    content = get_response(url, faker)
    return content.decode('utf-8', 'ignore')

def get_decoded_html(url, faker=None):
    response_bytes, recv_headers = get_response(url, faker, True)
    content_type = recv_headers.get('content-type')
    charset = match1(content_type, r'charset=([\w-]+)')
    if charset:
        return response_bytes.decode(charset, 'ignore')
    else:
        return response_bytes

def get_location(url):
    c = init_curl_obj()
    c.setopt(pycurl.URL, url)
    c.perform()
    return c.getinfo(pycurl.EFFECTIVE_URL)

#urlopen_with_retry is non-trivial to impl with pycurl

def get_content(url, headers={}, decoded=True):
    c = init_curl_obj()
    buffer = io.BytesIO()
    recv_headers = Recv_headers()
    install_headers(c, headers)
    c.setopt(pycurl.URL, url)
    c.setopt(pycurl.WRITEFUNCTION, buffer.write)
    c.setopt(pycurl.HEADERFUNCTION, recv_headers.input)
    for i in range(10):
        try:
            c.perform()
            break
        except pycurl.error as e:
            logging.debug('pycurl reports {0}'.format(e))

    buffer = buffer.getvalue()

    if decoded:
        content_type = recv_headers.get('content-type')
        charset = match1(content_type, r'charset=([\w-]+)')

        if charset is not None:
            data = buffer.decode(charset)
        else:
            data = buffer.decode('utf-8', 'ignore')

    return data

def post_content(url, headers={}, post_data={}, decoded=True):
    c = init_curl_obj()
    recv_headers = Recv_headers()
    buffer = io.BytesIO()
    c.setopt(pycurl.URL, url)
    install_headers(c, headers)
    import urllib.parse
    postfields = urllib.parse.urlencode(post_data)
    c.setopt(pycurl.HEADERFUNCTION, recv_headers.input)
    c.setopt(pycurl.POSTFIELDS, postfields)
    for i in range(10):
        try:
            c.perform()
            break
        except pycurl.error as e:
            print('pycurl reports {0}'.format(e))
    buffer = buffer.getvalue()
    if decoded:
        content_type = recv_headers.get('content-type')
        charset = match1(content_type, r'charset=([\w-]+)')

        if charset is not None:
            data = buffer.decode(charset)
        else:
            data = buffer.decode('utf-8', 'ignore')

#get_head and url_info, duplicated codes?
def get_head(url, headers={}, get_method='HEAD'):
    c = init_curl_obj()
    recv_headers = Recv_headers()
    install_headers(c, headers)
    c.setopt(pycurl.URL, url)
#"HEAD" and "GET"? Is "POST" possible?
    if get_method == 'HEAD':
        c.setopt(pycurl.NOBODY, True)
    elif get_method == 'GET':
        buffer = io.BytesIO()
        c.setopt(pycurl.WRITEFUNCTION, buffer.write)
#write to buffer... or it will be dumped to stdout (or stderr?)
    else:
        print("net_pycurl.get_head: Not supported method {0}".format(get_method))
    c.setopt(pycurl.HEADERFUNCTION, recv_headers.input)
    for i in range(10):
        try:
            c.perform()
            break
        except pycurl.error as e:
            print("pycurl report {0}".format(e))

    return recv_headers.dict_headers()

def url_size(url, faker=False, headers={}):
    if faker:
        recv_headers = get_head(url, fake_headers, 'GET')
    elif headers:
        recv_headers = get_head(url, headers, 'GET')
    else:
        recv_headers = get_head(url, {}, 'GET')

    size = recv_headers.get('content-length')

    if size is None:
        return float('inf')
    return int(size)

def urls_sizes(url, faker=False, headers={}):
    summation = 0
    has_inf = False
    for u in url:
        size = url_size(u, faker, headers)
        if size == float('inf'):
            has_inf = True
        else:
            summation += size

    return (summation, has_inf)

def urls_size(url, faker=False, headers={}):
    return urls_sizes(url, faker, headers)[0]

def url_info(url, faker=False, headers={}):
    if faker:
        recv_headers = get_head(url, faker, 'GET')
    elif headers:
        recv_headers = get_head(url, headers, 'GET')
    else:
        recv_headers = get_head(url, {}, 'GET')

    type = recv_headers['content-type']
#fix for netease from common.py
    if type == 'image/jpg; charset=UTF-8' or type =='image/jpg':
        type = 'audio/mpeg'

    import mime_types
    if type in mime_types.mapping:
        ext = mapping[type]
    else:
        type = None
        ext = None
        if recv_headers.get('content-disposition'):
            disposition = urllib.parse.unquote(recv_headers.get('content-disposition'))
            try:
                filename = match1(disposition, r'filename="?([^"]+)"?')
                if len(filename.split('.')) > 1:
                    ext = filename.split('.')[-1]
            except:
                ext = None

    if recv_headers.get('transfer-encoding') != 'chunked':
        if recv_headers.get('content-length'):
            size = int(recv_headers.get('content-length'))
    else:
        size = None

    return type, ext, size

def location_helper(url, headers={}):
#no urlopen_With_retry... need a helper to impl url_locations
#with GET
    c = init_curl_obj()
    install_headers(c, headers)
    c.setopt(pycurl.URL, url)
    buffer = io.BytesIO()
    c.setopt(pycurl.WRITEFUNCTION, buffer.write)
    for i in range(10):
        try:
            c.perform()
            break
        except pycurl.error as e:
            print("pycurl reports {0}".format(e))

    return c.getinfo(pycurl.EFFECTIVE_URL)

def url_locations(urls, faker=False, headers={}):
    locations = []
    for u in urls:
        if faker:
            final_url = location_helper(u, fake_headers)
        elif headers:
            final_url = location_helper(u, headers)
        else:
            final_url = location_helper(u)

        locations.append(final_url)

    return locations

def url_save(url, filepath, bar, refer=None, is_part=False, faker=False, headers={}):
    import os
    file_size = url_size(url, faker=faker, headers=headers)
    file_name = os.path.basename(filepath)
    dir_name = os.path.dirname(filepath)
    temp_filepath = filepath
    if file_size != float('inf'):
        temp_filepath += '.download'

    if os.path.exists(filepath):
        if not force and file_size == os.path.getsize(filepath):
            if not is_part:
                if bar:
                    bar.done()
                print('Skipping {0}: already there'.format(file_name))
            else:
                if bar:
                    bar.update_received(file_size)
            return
        else:
            if not is_part:
                if bar:
                    bar.done()
                print('Overwriting {0}...'.format(filename))
    elif not os.path.exists(dir_name):
        os.mkdir(dir_name)

    received_bytes = 0
    if not force:
        open_mode = 'ab'

        if os.path.exists(temp_filepath):
            downloaded_size = os.path.getsize(temp_filepath)
            received_bytes += downloaded_size 
            if bar:
                bar.update_received(downloaded_size)
    else:
        open_mode = 'wb'

    if received_bytes > file_size:
        os.remove(temp_filepath)

    while received_bytes != file_size:
        with open(temp_filepath, open_mode) as f:
            c = init_curl_obj()
            #recv_headers = Recv_headers()
            c.setopt(pycurl.URL, url)
            #c.setopt(pycurl.HEADERFUNCTION, recv_headers.input)
#header? really? check downloaded file size is adequate
            c.setopt(pycurl.WRITEFUNCTION, f.write)
            if faker:
                headers = fake_headers
            install_headers(c, headers)
            if received_bytes:
                #really? Range: bytes 200-1000 in MDN example.
                range_val = str(received_bytes) + '-'
                c.setopt(pycurl.RANGE, range_val)
            if refer:
                c.setopt(pycurl.REFERER, refer)

            try:
                c.perform()
            except pycurl.error as e:
                print("pycurl reports {0}".format(e))

        current_size = os.path.getsize(temp_filepath)
        print(current_size)
        if bar:
            bar.update_received(current_size - received_bytes)
        received_bytes = current_size
        open_mode = 'wb'
    assert received_bytes == os.path.getsize(temp_filepath), '{0} == {1} == {2}'.format(received_bytes, os.path.getsize(temp_filepath), temp_filepath)

    if os.access(filepath, os.W_OK):
        os.remove(filepath)
    os.rename(temp_filepath, filepath)

#chunk? libcurl should handle it all by itself
def url_save_chunked(url, filepath, bar, dyn_callback=None, chunk_size=0, ignore_range=False, refer=None, is_part=False, faker=False, headers={}):
    if dyn_callback:
        raise NotImplementedError('dyn_callback is not supported')
    url_save(url, filpath, bar, refer=refer, is_part=is_part, faker=faker, headers=headers)

def match1(text, patterns):
    import re
    match = re.search(patterns, text)
    if match is None:
        return None
    return match.group(1)
