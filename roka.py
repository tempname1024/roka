#!/usr/bin/env python3

import argparse
import os
import shutil
import json
from flask import Flask, request, Response, render_template, send_file, templating
from flask.globals import app_ctx
from lib.books import Books
from lib.util import check_auth, escape, generate_rss, read_cache

abs_path = os.path.dirname(os.path.abspath(__file__))
app = Flask(__name__)
config_path = os.path.join(abs_path, 'app.cfg')
config_exists = os.path.exists(config_path)
if config_exists or __name__.startswith('uwsgi'):
    app.config.from_pyfile(config_path)
cache_path = os.path.join(abs_path, 'cache')
json_path = os.path.join(cache_path, 'audiobooks.json')

@app.route('/')
def list_books():
    '''
    Book listing and audiobook RSS/file download

    :a: audiobook hash; if provided without :f: (track) return RSS
    :f: file hash; requires associated audiobook (:a:) to download

    Listing of audiobooks returned if no params provided
    '''
    books = read_cache(json_path)

    book = request.args.get('a')  # audiobook hash
    track = request.args.get('f') # file hash

    # audiobook and file parameters provided: serve up file
    if book and track:
        if not books.get(book) or not books[book]['files'].get(track):
            return 'book or file not found', 404

        track_path = books[book]['files'][track]['path']
        return send_file(track_path, conditional=True)

    # serve up audiobook RSS feed; only audiobook hash provided
    elif book:
        if not books.get(book):
            return 'book not found', 404

        rss = generate_rss(request.base_url, book, books)
        return Response(rss, mimetype='text/xml')

    else:
        auth = request.authorization
        if not auth or not check_auth(app, auth.username, auth.password):
            form = {'WWW-Authenticate': 'Basic realm="o/"'}
            return Response('unauthorized', 401, form)

        return render_template('index.html', books=books,
                               show_path=app.config.get('SHOW_PATH', True))

def generate(static_path, base_url, audiobook_dirs):
    static_index_path = os.path.join(static_path, 'index.html')

    books = Books()
    books.scan_books(audiobook_dirs)
    books.write_cache()
    books = read_cache(json_path)
    # A bit of a hack, but push to the app context stack so we can render a
    # template outside of a Flask request
    with app.app_context():
        app_ctx.push()
        index = render_template('index.html', books=books, static=True)
        app_ctx.pop()

    os.makedirs(static_path, exist_ok=True)

    indexfile = open(static_index_path, 'w')
    indexfile.write(index)
    indexfile.close()

    for b_key, book in books.items():
        rss = generate_rss(base_url, b_key, books, static=True)
        rss_path = os.path.join(static_path, b_key + '.xml')
        rssfile = open(rss_path, 'w')
        rssfile.write(rss.decode('utf-8'))
        rssfile.close()

        book_dir = os.path.join(static_path, b_key)
        os.makedirs(book_dir, exist_ok=True)

        for f_key, file in book['files'].items():
            f_path = file['path']
            copy_path = os.path.join(book_dir, f_key + '.mp3')
            if not os.path.exists(copy_path):
                shutil.copyfile(f_path, copy_path)

if __name__ == '__main__':
    desc = 'roka: listen to audiobooks with podcast apps via RSS'
    parser = argparse.ArgumentParser(description=desc)
    parser.add_argument('--scan', dest='scan', action='store_true',
                        help='scan audiobooks directory for new books',
                        required=False)
    parser.add_argument('--generate', dest='static_path', type=str, action='store',
                        help='Output directory to generate static files',
                        required=False)
    parser.add_argument('--config', dest='config', type=str, action='store',
                        help='Json configuration instead of app.cfg',
                        required=False)
    args = parser.parse_args()

    if args.config:
        class objectview(object):
            def __init__(self, d):
                self.__dict__ = d
        config = objectview(json.loads(args.config))
        # override app.cfg
        app.config.from_object(config)
    elif not config_exists:
        raise Exception(f"Config file '{config_path}' doesn't exist")

    root_path = os.path.expanduser(app.config['ROOT_PATH'])

    if args.scan:
        books = Books()
        books.scan_books(root_path)
        books.write_cache()
    elif args.static_path:
        generate(args.static_path, app.config['BASE_URL'], root_path)
    else:
        app.run(host='127.0.0.1', port='8085', threaded=True)
