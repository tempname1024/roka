#!/usr/bin/env python3

import argparse
import os
from flask import Flask, request, Response, render_template, send_file
from lib.books import Books
from lib.util import check_auth, escape, generate_rss, read_cache

abs_path = os.path.dirname(os.path.abspath(__file__))
app = Flask(__name__)
app.config.from_pyfile(os.path.join(abs_path, 'app.cfg'))
cache_path = os.path.join(abs_path, 'cache')
json_path = os.path.join(cache_path, 'audiobooks.json')

@app.route('/')
def list_books():
    '''
    Book listing and audiobook RSS/file download

    :a: audiobook hash; if provided without :f: (file) return RSS
    :f: file hash; requires associated audiobook (:a:) to download

    Listing of audiobooks returned if no params provided
    '''
    books = read_cache(json_path)

    a = request.args.get('a') # audiobook hash
    f = request.args.get('f') # file hash

    # audiobook and file parameters provided: serve up file
    if a and f:
        if not books.get(a) or not books[a]['files'].get(f):
            return 'book or file not found', 404

        f_path = books[a]['files'][f]['path']
        return send_file(f_path, conditional=True)

    # serve up audiobook RSS feed; only audiobook hash provided
    elif a:
        if not books.get(a):
            return 'book not found', 404

        rss = generate_rss(request, books)
        return Response(rss, mimetype='text/xml')

    else:
        auth = request.authorization
        if not auth or not check_auth(app, auth.username, auth.password):
            form = {'WWW-Authenticate': 'Basic realm="o/"'}
            return Response('unauthorized', 401, form)

        return render_template('index.html', books=books,
                               show_path=app.config.get('SHOW_PATH', True))

if __name__ == '__main__':
    desc = 'roka: listen to audiobooks with podcast apps via RSS'
    parser = argparse.ArgumentParser(description=desc)
    parser.add_argument('--scan', dest='scan', action='store_true',
                        help='scan audiobooks directory for new books',
                        required=False)
    args = parser.parse_args()

    if args.scan:
        books = Books()
        books.scan_books()
        books.write_cache()
    else:
        app.run(host='127.0.0.1', port='8085', threaded=True)
