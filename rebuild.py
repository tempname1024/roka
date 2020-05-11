#!/usr/bin/env python3

import hashlib
import json
import math
import os
from datetime import timedelta
from flask import Flask
from lib.tinytag import TinyTag

def get_books(root_path, cache=None):
    '''
    Discover audiobooks under :root_path: and populate books object

    :cache: existing JSON cache, used to determine which content is new
            (existing content is not re-hashed)
    '''
    if not os.path.exists(root_path):
        raise ValueError('root path does not exist: %s' % root_path)

    # '/home/user/audiobooks/book': d815c7a3cc11f08558b4d91ca93de023
    cached = {}
    if cache:
        for k, _ in cache.items():
            cached[cache[k]['path']] = k

    books = dict()
    book_dirs = list()
    for root, dirs, _ in os.walk(root_path):
        for d in dirs:
            book_dirs.append(os.path.join(root, d))

    for book_path in book_dirs:
        print('[+] processing: %s' % book_path)

        # if already cached, populate _books with existing k/v
        if book_path in cached:
            _hash = cached[book_path]
            books[_hash] = cache[_hash]
            continue

        book = is_book(book_path)
        if book: books[0] = book[1]

    return books

def is_book(book_path):
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

        # must be MP3 file, ignore anything else
        if not os.path.isfile(file_path) or not f.endswith('.mp3'):
            continue

        # skip if no duration attribute (required)
        tag = TinyTag.get(file_path)
        if not tag.duration:
            continue

        # previous conditions met, we're a book! :D
        is_book = True

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

        # populate per-file and book attribute
        mp3 = dict()
        mp3['path'] = file_path
        mp3['duration'] = tag.duration
        mp3['filename'] = os.path.split(file_path)[1]

        # attribute values must be populated and non-space
        if tag.title and not tag.title.isspace():
            mp3['title'] = tag.title
        else:
            mp3['title'] = os.path.split(file_path)[1]

        # we overwrite existing book title/author in assuming MP3 tags are
        # consistent between MP3s, perhaps we shouldn't
        if tag.album and not tag.album.isspace():
            mp3['album'] = tag.album
            book['title'] = tag.album
        else:
            mp3['album'] = os.path.split(book_path)[1]
            book['title'] = os.path.split(book_path)[1]

        if tag.artist and not tag.artist.isspace():
            mp3['author'] = tag.artist
            book['author'] = tag.artist
        else:
            mp3['author'] = 'Unknown'
            book['author'] = 'Unknown'

        mp3['duration'] = tag.duration
        mp3['track'] = tag.track
        mp3['size_bytes'] = tag.filesize

        duration_str = str(timedelta(seconds=mp3['duration']))
        mp3['duration_str'] = duration_str.split('.')[0]

        # increment book total size/duration, store MP3
        book['duration'] += tag.duration
        book['files'][file_hash.hexdigest()] = mp3
        book['size_bytes'] += tag.filesize

    # if we're a book, store formatted book size and duration
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

    return False

def write_cache(books, json_path):
    '''
    Dump contents of :books: to :json_path:
    '''
    cache_path = os.path.dirname(json_path)
    if not os.path.exists(cache_path):
        os.mkdir(cache_path)
    with open(json_path, 'w') as f:
        json.dump(books, f, indent=4)

def read_cache(json_path):
    with open(json_path, 'r') as cache:
        books = json.load(cache)

    return books

if __name__ == '__main__':
    ABS_PATH = os.path.dirname(os.path.abspath(__file__))
    CACHE_PATH = os.path.join(ABS_PATH, 'cache')
    JSON_PATH = os.path.join(CACHE_PATH, 'audiobooks.json')

    # use Flask's config parser, configparser would be hacky
    APP = Flask(__name__)
    APP.config.from_pyfile(os.path.join(ABS_PATH, 'app.cfg'))

    if os.path.exists(CACHE_PATH):
        cache = read_cache(JSON_PATH)
        BOOKS = get_books(APP.config['ROOT_PATH'], cache)
    else:
        BOOKS = get_books(APP.config['ROOT_PATH'])

    write_cache(BOOKS, JSON_PATH)
