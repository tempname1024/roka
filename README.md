# Roka

Stream a directory of audiobooks to podcast apps over an RSS XML feed uniquely
generated for each audiobook. A screenshot of the web interface is 
[available here](screenshots/web.png).

## Installation

1. Copy and populate `app.cfg` and `uwsgi.ini` from examples, or pass
   configuration key/values as a JSON string with the `--config` parameter.

2. Install Python dependencies flask and uwsgi.

    ```bash
    pip install --user flask uwsgi
    ```

3. Populate audiobook JSON cache; can be re-run to update cache upon download of
   new books.

    ```bash
    ./roka.py --scan
    ```

4. Run uwsgi.sh to start the server.

    ```bash
    ./uwsgi.sh
    ```

## Static generation

In addition to running as a server, Roka can also generate a static index and
set of RSS feeds that can be deployed to static hosting. This mode does not
support a username and password.

1. Populate `BASE_URL` in `app.cfg` to the base url where the static site will
   be uploaded.

2. Run `roka.py` with the `--generate <output_directory>` parameter, where
   `<output_directory>` is an output directory to place the generated site. All
   audiobook files will be copied to this location.

   ```bash
   ./roka.py --generate ./static
   ```

3. Upload the static site to any static web hosting. Make sure it is accessible
   at the URL set as `BASE_URL`

## Design decisions

1. Directories contained within `ROOT_PATH` are marked as audiobooks if and only
   if they contain at least one MP3 file.

2. Audiobooks are uniquely identified in the web interface by the collective
   hash of each MP3 file contained in the audiobook directory. If the directory
   structure is changed or files are moved, RSS/download link integrity is
   maintained, preserving app-side listening progress and history.

3. XML `pubDate` and list order is derived from MP3 track attributes; if not
   present or duplicates exist, tracks are sorted alphanumerically. If a book's
   track numbers are unique but incorrect, a preference for filename sort can be
   established by creating an 'ignore_tracknum' file in the audiobook's path.

4. No rebuild endpoint exists; cache-affecting routines are executed by calling
   `roka.py` directly.
