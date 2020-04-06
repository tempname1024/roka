#!/usr/bin/env python3

import hashlib
import json
import math
import os
from datetime import timedelta
from flask import Flask
from lib.tinytag import TinyTag

def get_books(root_path):
    '''
    Discover audiobooks under :root_path: and populate books object
    '''
    if not os.path.exists(root_path):
        raise ValueError('root path does not exist: %s' % root_path)

    SIZES = ('B', 'KB', 'MB', 'GB', 'TB', 'PB', 'EB', 'ZB', 'YB')
    _books = dict()
    book_dirs = list()
    for root, dirs, _ in os.walk(root_path):
        for d in dirs:
            book_dirs.append(os.path.join(root, d))

    for book_path in book_dirs:
        print('[+] processing: %s' % book_path)

        # initial set of attributes to be populated
        book = {
            'duration': 0,
            'path': book_path,
            'files': dict(),
            'size_bytes': 0,
            'size_str': None,
        }

        # hash of each file in directory w/ MP3 extension
        folder_hash = hashlib.md5()
        is_book = False

        # a book_path is only a book if it contains at least one MP3
        for f in os.listdir(book_path):
            file_path = os.path.join(book_path, f)
            if not os.path.isfile(file_path) or not f.endswith('.mp3'):
                continue

            # update folder hash with MD5 of current file
            BLOCK = 1024
            file_hash = hashlib.md5()
            with open(file_path, 'rb') as f:
                while True:
                    data = f.read(BLOCK)
                    if not data:
                        break
                    folder_hash.update(data)
                    file_hash.update(data)

            # skip if no duration attribute (required)
            tag = TinyTag.get(file_path)
            if not tag.duration:
                continue
            is_book = True

            # populate file-specific attributes
            attr = dict()
            attr['path'] = file_path
            attr['duration'] = tag.duration
            if tag.title and not tag.title.isspace():
                attr['title'] = tag.title
            else:
                attr['title'] = os.path.split(file_path)[1]

            if tag.album and not tag.album.isspace():
                attr['album'] = tag.album
                book['title'] = tag.album
            else:
                attr['album'] = os.path.split(book_path)[1]
                book['title'] = os.path.split(book_path)[1]

            if tag.artist and not tag.artist.isspace():
                attr['author'] = tag.artist
                book['author'] = tag.artist
            else:
                attr['author'] = 'Unknown'
                book['author'] = 'Unknown'

            attr['duration'] = tag.duration
            attr['track'] = tag.track
            attr['size_bytes'] = tag.filesize

            duration_str = str(timedelta(seconds=attr['duration']))
            attr['duration_str'] = duration_str.split('.')[0]

            book['duration'] += tag.duration
            book['files'][file_hash.hexdigest()] = attr
            book['size_bytes'] += tag.filesize

        if is_book:
            folder_hash = folder_hash.hexdigest()

            total_size = book['size_bytes']
            try:
                _i = int(math.floor(math.log(total_size, 1024)))
                _p = math.pow(1024, _i)
                _s = round(total_size / _p, 2)
            except:
                _i = 1
                _s = 0

            # e.g. 1.48 GB
            book['size_str'] = '%s %s' % (str(_s), SIZES[_i])

            # e.g. 2 days, 5:47:47
            duration_str = str(timedelta(seconds=book['duration']))
            book['duration_str'] = duration_str.split('.')[0]

            _books[folder_hash] = book

    return _books

def write_cache(books, json_path):
    '''
    Dump contents of :books: to :json_path:
    '''
    cache_path = os.path.dirname(json_path)
    if not os.path.exists(cache_path):
        os.mkdir(cache_path)
    with open(json_path, 'w') as f:
        json.dump(books, f, indent=4)

if __name__ == '__main__':
    ABS_PATH = os.path.dirname(os.path.abspath(__file__))
    CACHE_PATH = os.path.join(ABS_PATH, 'cache')
    JSON_PATH = os.path.join(CACHE_PATH, 'audiobooks.json')

    # use Flask's config parser, configparser would be hacky
    APP = Flask(__name__)
    APP.config.from_pyfile(os.path.join(ABS_PATH, 'app.cfg'))

    BOOKS = get_books(APP.config['ROOT_PATH'])
    write_cache(BOOKS, JSON_PATH)
