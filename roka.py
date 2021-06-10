#!/usr/bin/env python3

import argparse
import os
import shutil
import json
from flask import Flask, request, Response, render_template, send_file, templating
from lib.books import Books
from lib.util import check_auth, escape, generate_rss, read_cache

abs_path = os.path.dirname(os.path.abspath(__file__))
app = Flask(__name__)
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

        rss = generate_rss(request.base_url, a, books)
        return Response(rss, mimetype='text/xml')

    else:
        auth = request.authorization
        if not auth or not check_auth(app, auth.username, auth.password):
            form = {'WWW-Authenticate': 'Basic realm="o/"'}
            return Response('unauthorized', 401, form)

        return render_template('index.html', books=books)

# TODO does this really need to be here?
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

def generate(static_path, base_url, audiobook_dirs):
    static_index_path = os.path.join(static_path, 'index.html')

    books = Books()
    books.scan_books(audiobook_dirs)
    books.write_cache()
    books = read_cache(json_path)
    index = my_render_template(app, 'index.html', books=books, static=True)

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
    parser.add_argument('--base_url', dest='base_url', type=str, action='store',
                        help='Base URL to use in static files',
                        required=False)
    parser.add_argument('--config', dest='config', type=str, action='store',
                        help='Json configuration instead of app.cfg',
                        required=False)
    args = parser.parse_args()

    if args.static_path and not args.base_url or args.base_url and not args.static_path:
        parser.error('--generate and --base_url must be included together')

    if args.config:
        class objectview(object):
            def __init__(self, d):
                self.__dict__ = d
        config = objectview(json.loads(args.config))
        app.config.from_object(config)
    elif os.path.exists(os.path.join(abs_path, 'app.cfg')):
        app.config.from_pyfile(os.path.join(abs_path, 'app.cfg'))

    root_path = os.path.expanduser(app.config['ROOT_PATH'])

    if args.scan:
        books = Books()
        books.scan_books(root_path)
        books.write_cache()
    elif args.static_path:
        generate(args.static_path, args.base_url, root_path)
    else:
        app.run(host='127.0.0.1', port='8085', threaded=True)
