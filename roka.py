#!/usr/bin/env python3

import argparse
import os
from flask import Flask, request, Response, render_template, send_file, templating
from lib.books import Books
from lib.util import check_auth, escape, generate_rss, read_cache

abs_path = os.path.dirname(os.path.abspath(__file__))
app = Flask(__name__)
app.config.from_pyfile(os.path.join(abs_path, 'app.cfg'))
cache_path = os.path.join(abs_path, 'cache')
json_path = os.path.join(cache_path, 'audiobooks.json')
static_path = os.path.join(abs_path, 'static')
static_index_path = os.path.join(static_path, 'index.html')
base_url = "blah.com/"

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

        rss = generate_rss(request.base_url, a, books)
        return Response(rss, mimetype='text/xml')

    else:
        auth = request.authorization
        if not auth or not check_auth(app, auth.username, auth.password):
            form = {'WWW-Authenticate': 'Basic realm="o/"'}
            return Response('unauthorized', 401, form)

        return render_template('index.html', books=books)

def my_render_template(
    app, template_name_or_list, **context
) -> str:
    """Renders a template from the template folder with the given
    context.

    :param template_name_or_list: the name of the template to be
                                  rendered, or an iterable with template names
                                  the first one existing will be rendered
    :param context: the variables that should be available in the
                    context of the template.
    """
    app.update_template_context(context)
    return templating._render(
        app.jinja_env.get_or_select_template(template_name_or_list),
        context,
        app,
    )

def generate():
    books = Books()
    books.scan_books()
    books.write_cache()
    books = read_cache(json_path)
    index = my_render_template(app, 'index.html', books=books, static=True)

    indexfile = open(static_index_path, 'w')
    indexfile.write(index)
    indexfile.close()

    for key in books.keys():
        rss = generate_rss(base_url, key, books, static=True)
        rss_path = os.path.join(static_path, key + '.xml')
        rssfile = open(rss_path, 'w')
        rssfile.write(rss.decode('utf-8'))
        rssfile.close()

if __name__ == '__main__':
    desc = 'roka: listen to audiobooks with podcast apps via RSS'
    parser = argparse.ArgumentParser(description=desc)
    parser.add_argument('--scan', dest='scan', action='store_true',
                        help='scan audiobooks directory for new books',
                        required=False)
    parser.add_argument('--generate', dest='generate', action='store_true',
                        help='',
                        required=False)
    args = parser.parse_args()

    if args.scan:
        books = Books()
        books.scan_books()
        books.write_cache()
    elif args.generate:
        generate()
    else:
        app.run(host='127.0.0.1', port='8085', threaded=True)
