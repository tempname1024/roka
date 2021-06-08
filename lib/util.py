import json
import os
import re
import sys
import xml.etree.cElementTree as ET
from collections import OrderedDict
from datetime import date, timedelta
from flask import Flask, request, Response, send_file, send_from_directory
from xml.dom import minidom

def read_cache(json_path):
    '''
    Populate books dict from cache at :json_path:
    '''
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
        raise ValueError('cache not found, run ./roka.py --scan')

    return books

def check_auth(app, username, password):
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
    s = s.replace('\'', '&apos;')
    s = s.replace('\"', '&quot;')

    # https://stackoverflow.com/a/22273639
    illegal_unichrs = [
        (0x00, 0x08),
        (0x0B, 0x0C),
        (0x0E, 0x1F),
        (0x7F, 0x84),
        (0x86, 0x9F),
        (0xFDD0, 0xFDDF),
        (0xFFFE, 0xFFFF),
        (0xA9, 0xA9)
    ]

    if sys.maxunicode >= 0x10000:
        illegal_unichrs.extend(
            [(0x1FFFE, 0x1FFFF), (0x2FFFE, 0x2FFFF),
             (0x3FFFE, 0x3FFFF), (0x4FFFE, 0x4FFFF),
             (0x5FFFE, 0x5FFFF), (0x6FFFE, 0x6FFFF),
             (0x7FFFE, 0x7FFFF), (0x8FFFE, 0x8FFFF),
             (0x9FFFE, 0x9FFFF), (0xAFFFE, 0xAFFFF),
             (0xBFFFE, 0xBFFFF), (0xCFFFE, 0xCFFFF),
             (0xDFFFE, 0xDFFFF), (0xEFFFE, 0xEFFFF),
             (0xFFFFE, 0xFFFFF), (0x10FFFE, 0x10FFFF)]
        )

    illegal_ranges = ["%s-%s" % (chr(low), chr(high))
                       for (low, high) in illegal_unichrs]
    illegal_xml_chars_RE = re.compile(u'[%s]' % u''.join(illegal_ranges))

    s = illegal_xml_chars_RE.sub('', s)

    return s

def generate_rss(request, books):
    book = request.args.get('a') # audiobook hash

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
    book_title.text = escape(books[book]['title'])

    # use filename sort if ignore_tracknum file present in book dir
    ignore_tracknum = os.path.join(books[book]['path'], 'ignore_tracknum')
    if os.path.exists(ignore_tracknum):
        # remove leading zeros from digits (natural sort)
        conv = lambda s: [int(x) if x.isdigit() else x.lower() for x in
            re.split('(\d+)', s)]
        key = lambda x: conv(books[book]['files'][x]['filename'])
    else:
        # sort by track number, alphanumerically if track is absent
        track_list = [] # account for duplicates
        for a_file in books[book]['files']:
            track = books[book]['files'][a_file]['track']
            if not track or track in track_list:
                # remove leading zeros from digits (natural sort)
                conv = lambda s: [int(x) if x.isdigit() else x.lower()
                        for x in re.split('(\d+)', s)]
                key = lambda x: conv(books[book]['files'][x]['filename'])
                break
            track_list.append(track)
        else:
            # we have populated and unique track values, use those
            key = lambda x: int(books[book]['files'][x]['track'])

    # populate XML attribute values required by Apple podcasts
    for idx, f in enumerate(sorted(books[book]['files'], key=key)):
        item = ET.SubElement(channel, 'item')

        title = ET.SubElement(item, 'title')
        title.text = escape(books[book]['files'][f]['title'])

        author = ET.SubElement(item, 'itunes:author')
        author.text = escape(books[book]['files'][f]['author'])

        category = ET.SubElement(item, 'itunes:category')
        category.text = 'Book'

        explicit = ET.SubElement(item, 'itunes:explicit')
        explicit.text = 'no'

        summary = ET.SubElement(item, 'itunes:summary')
        summary.text = 'Audiobook served by audiobook-rss'

        description = ET.SubElement(item, 'description')
        description.text = 'Audiobook served by audiobook-rss'

        duration = ET.SubElement(item, 'itunes:duration')
        duration.text = str(books[book]['files'][f]['duration_str'])

        guid = ET.SubElement(item, 'guid', isPermaLink='false')
        guid.text = f # file hash

        # pubDate descending, day decremented w/ each iteration
        pub_date = ET.SubElement(item, 'pubDate')
        pub_format = '%a, %d %b %Y %H:%M:%S %z'
        pub_date.text = (date(2000, 12, 31) - timedelta(days=idx)).strftime(
                pub_format)
        enc_attr = {
            'url': '{}?a={}&f={}'.format(request.base_url, book, f),
            'length': str(books[book]['files'][f]['size_bytes']),
            'type': 'audio/mpeg'
        }
        ET.SubElement(item, 'enclosure', enc_attr)

    return ET.tostring(rss, encoding='utf8', method='xml')

