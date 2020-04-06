#!/usr/bin/env python3

import json
import mimetypes
import os
import re
import xml.etree.cElementTree as ET
from collections import OrderedDict
from operator import getitem
from datetime import date, timedelta
from flask import Flask, request, Response, render_template, send_file

abs_path = os.path.dirname(os.path.abspath(__file__))
app = Flask(__name__)
app.config.from_pyfile(os.path.join(abs_path, 'app.cfg'))
cache_path = os.path.join(abs_path, 'cache')
json_path = os.path.join(cache_path, 'audiobooks.json')

# populate books object from JSON cache sorted by title
if os.path.exists(json_path):
    try:
        with open(json_path, 'r') as cache:
            books = json.load(cache)
        books = OrderedDict(sorted(
            books.items(),
            key=lambda x: x[1]['title']
        ))

    except Exception:
        raise ValueError('error loading JSON cache')
else:
    raise ValueError('cache not found, run rebuild.py')

def check_auth(username, password):
    '''
    Authenticate against configured user/pass
    '''
    ret = (username == app.config['USERNAME'] and
           password == app.config['PASSWORD'])

    return ret

def escape(s):
    '''
    Ensure XML-safety of attribute values
    '''
    s = s.replace('&', '&amp;')
    s = s.replace('<', '&lt;')
    s = s.replace('>', '&gt;')
    s = s.replace('\'', '&quot;')

    return s

@app.route('/')
def list_books():
    '''
    Book listing and audiobook RSS/file download

    :a: audiobook hash; if provided without :f: (file) return RSS
    :f: file hash; requires associated audiobook (:a:) to download

    Listing of audiobooks returned if no params provided
    '''
    a = request.args.get('a') # audiobook hash
    f = request.args.get('f') # file hash

    # audiobook and file parameters provided: serve up file
    if a and f:
        if not books.get(a) or not books[a]['files'].get(f):
            return 'book or file not found', 404

        f_path = books[a]['files'][f]['path']

        # ship the whole file if we don't receive a Range header
        range_header = request.headers.get('Range', None)
        if not range_header:
            return send_file(
                f_path,
                mimetype=mimetypes.guess_type(f_path)[0]
            )

        # partial request handling--certain podcast apps (iOS) and browsers
        # (Safari) require correct replies to Range requests; if we serve the
        # entire file, we're treated like a stream (no seek, duration...)
        size = books[a]['files'][f]['size_bytes']

        # if no lower bound provided, start at beginning
        byte1, byte2 = 0, None
        m = re.search(r'(\d+)-(\d*)', range_header)
        g = m.groups()
        if g[0]:
            byte1 = int(g[0])
        if g[1]:
            byte2 = int(g[1])

        # if no upper bound provided, serve rest of file
        length = size - byte1
        if byte2 is not None:
            length = byte2 - byte1

        # read file at byte1 for length
        data = None
        with open(f_path, 'rb') as f:
            f.seek(byte1)
            data = f.read(length)

        # create response with partial data, populate Content-Range
        response = Response(
            data,
            206,
            mimetype=mimetypes.guess_type(f_path)[0],
            direct_passthrough=True
        )
        response.headers.add(
            'Content-Range',
            'bytes {0}-{1}/{2}'.format(byte1, byte1 + length, size)
        )
        response.headers.add('Accept-Ranges', 'bytes')

        return response

    # serve up audiobook RSS feed; only audiobook hash provided
    elif a:
        if not books.get(a):
            return 'book not found', 404

        # we only make use of the itunes ns, others provided for posterity
        namespaces = {
            'itunes':'http://www.itunes.com/dtds/podcast-1.0.dtd',
            'googleplay':'http://www.google.com/schemas/play-podcasts/1.0',
            'atom':'http://www.w3.org/2005/Atom',
            'media':'http://search.yahoo.com/mrss/',
            'content':'http://purl.org/rss/1.0/modules/content/',
        }

        rss = ET.Element('rss')
        for k, v in namespaces.items():
            rss.set('xmlns:%s' % k, v)
        rss.set('version', '2.0')

        channel = ET.SubElement(rss, 'channel')

        book_title = ET.SubElement(channel, 'title')
        book_title.text = books[a]['title']

        # sort by track number, alphanumerically if track is absent
        track_list = [] # account for duplicates
        for a_file in books[a]['files']:
            track = books[a]['files'][a_file]['track']
            if not track or track in track_list:
                key = lambda x: books[a]['files'][x]['title']
                break
            track_list.append(track)
        else:
            key = lambda x: books[a]['files'][x]['track']

        # populate XML attribute values required by Apple podcasts
        for idx, f in enumerate(sorted(books[a]['files'], key=key)):
            item = ET.SubElement(channel, 'item')

            title = ET.SubElement(item, 'title')
            title.text = escape(books[a]['files'][f]['title'])

            author = ET.SubElement(item, 'itunes:author')
            author.text = escape(books[a]['files'][f]['author'])

            category = ET.SubElement(item, 'itunes:category')
            category.text = 'Book'

            explicit = ET.SubElement(item, 'itunes:explicit')
            explicit.text = 'no'

            summary = ET.SubElement(item, 'itunes:summary')
            summary.text = 'Audiobook served by audiobook-rss'

            description = ET.SubElement(item, 'description')
            description.text = 'Audiobook served by audiobook-rss'

            duration = ET.SubElement(item, 'itunes:duration')
            duration.text = str(books[a]['files'][f]['duration_str'])

            guid = ET.SubElement(item, 'guid')
            guid.text = f # file hash

            # pubDate descending, day decremented w/ each iteration
            pub_date = ET.SubElement(item, 'pubDate')
            pub_date.text = (date(2000, 12, 31) - timedelta(days=idx)).ctime()
            enc_attr = {
                'url': '{}?a={}&f={}'.format( request.base_url, a, f),
                'length': str(books[a]['files'][f]['size_bytes']),
                'type': 'audio/mpeg'
            }
            ET.SubElement(item, 'enclosure', enc_attr)

        return Response(
            ET.tostring(rss, encoding='utf8', method='xml'),
            mimetype='text/xml'
        )
    else:
        auth = request.authorization
        if not auth or not check_auth(auth.username, auth.password):
            form = {'WWW-Authenticate': 'Basic realm="o/"'}
            return Response('unauthorized', 401, form)
        return render_template('index.html', books=books)

if __name__ == '__main__':
    app.run(host='127.0.0.1', port='8085', threaded=True)
