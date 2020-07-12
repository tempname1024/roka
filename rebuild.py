#!/usr/bin/env python3

import datetime
import hashlib
import json
import math
import os
from datetime import timedelta
from flask import Flask
from lib.tinytag import TinyTag

ABS_PATH = os.path.dirname(os.path.abspath(__file__))
CACHE_PATH = os.path.join(ABS_PATH, 'cache')
JSON_PATH = os.path.join(CACHE_PATH, 'audiobooks.json')

# use Flask's config parser, configparser would be hacky
APP = Flask(__name__)
APP.config.from_pyfile(os.path.join(ABS_PATH, 'app.cfg'))

class Books:
    def __init__(self):
        if os.path.exists(JSON_PATH):
            self._cache = self._read_cache()
        else:
            self._cache = {}

        self.books = self._get_books()
        self._write_cache()

    def _get_dirs(self, path):
        '''
        Return list of directories recursively discovered in :path:
        '''
        ret = list()
        for root, dirs, _ in os.walk(path):
            for d in dirs:
                ret.append(os.path.join(root, d))

        return ret

    def _get_path_hash_dict(self):
        '''
        Return dict of book paths and their hash from cache, used to check paths
        against existing cache

        '/home/user/audiobooks/book': d815c7a3cc11f08558b4d91ca93de023
        '''
        ret = {}
        for k, _ in self._cache.items():
            path = self._cache[k]['path']
            if os.path.exists(path):
                ret[path] = k

        return ret

    def _write_cache(self):
        '''
        Dump contents of :books: to :json_path:
        '''
        if not os.path.exists(CACHE_PATH):
            os.mkdir(CACHE_PATH)
        with open(JSON_PATH, 'w') as cache:
            json.dump(self.books, cache, indent=4)

    def _read_cache(self):
        '''
        Return dict of existing cache
        '''
        with open(JSON_PATH, 'r') as cache:
            data = json.load(cache)

        return data

    def _validate(self, v, b):
        '''
        Returns :v: if :v: and v.isspace(), otherwise :b:
        '''
        if v and not v.isspace():
            return v

        return b

    def _log(self, msg):
        '''
        Prints :msg: with formatted ISO-8601 date
        '''
        now = datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
        print('%s %s' % (now, msg))

    def _get_books(self):
        '''
        Discover audiobooks under :root_path: and populate books object

        :cache: existing JSON cache, used to determine which content is new
                (existing content is not re-hashed)
        '''
        ex = self._get_path_hash_dict()
        dirs = self._get_dirs(APP.config['ROOT_PATH'])

        books = dict()
        for path in dirs:
            if path in ex:
                _hash = ex[path]
                books[_hash] = self._cache[_hash]
                continue
            book = self._check_dir(path)
            if book:
                books[book[0]] = book[1]

        return books

    def _check_dir(self, path):
        '''
        Determine if :path: contains (supported) audio files; return populated
        book dict or None
        '''
        ext = ['mp3'] # m4b seems to be unsupported by Apple
        is_book = False

        # book attributes to be populated
        book = {
            'author':       None,
            'duration':     0,
            'duration_str': None,
            'files':        dict(),
            'path':         path,
            'size_bytes':   0,
            'size_str':     None,
            'title':        None
        }

        # hash of each file in directory w/ track extension
        folder_hash = hashlib.md5()

        for f in os.listdir(path):
            file_path = os.path.join(path, f)
            if not os.path.isfile(file_path) or not f.split('.')[-1] in ext:
                continue

            tag = TinyTag.get(file_path)
            if not tag.duration:
                continue

            is_book = True
            self._log(f)

            file_hash = hashlib.md5()
            with open(file_path, 'rb') as f:
                while True:
                    data = f.read(1024)
                    if not data:
                        break
                    folder_hash.update(data)
                    file_hash.update(data)

            # 1 day, 10:59:58
            duration_str = str(timedelta(seconds=tag.duration))

            # per-file atributes, some values are populated conditionally
            track = {
                'album':        self._validate(tag.album, os.path.split(path)[1]),
                'author':       self._validate(tag.artist, 'Unknown'),
                'duration':     tag.duration,
                'duration_str': duration_str.split('.')[0],
                'filename':     os.path.split(file_path)[1],
                'path':         file_path,
                'size_bytes':   tag.filesize,
                'title':        self._validate(tag.title, os.path.split(file_path)[1]),
                'track':        tag.track
            }

            # we assume author and album attributes are unchanged between tracks
            book['author'] = track['author']
            book['title'] = track['album']

            # increment book total size/duration
            book['duration'] += tag.duration
            book['size_bytes'] += tag.filesize

            # hexdigest: track dict
            book['files'][file_hash.hexdigest()] = track

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
            SIZES = ('B', 'KB', 'MB', 'GB', 'TB', 'PB', 'EB', 'ZB', 'YB')
            book['size_str'] = '%s %s' % (str(_s), SIZES[_i])

            # e.g. 2 days, 5:47:47
            duration_str = str(timedelta(seconds=book['duration']))
            book['duration_str'] = duration_str.split('.')[0]
            return (folder_hash, book)

        return None

if __name__ == '__main__':
    books = Books()
