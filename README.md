# Roka

Stream directory of audiobooks to podcasting apps via RSS.

A screenshot of the web interface is [available here](screenshots/web.png).

## Installation

1. Copy and populate app.cfg and uwsgi.ini from examples

2. Install python dependencies flask and uwsgi

    ```bash
    pip install --user flask uwsgi
    ```

3. Run roka.py with --scan to populate audiobook JSON cache (can be re-run to
   update cache upon download of new books)

    ```bash
    ./roka.py --scan
    ```

4. Execute uwsgi.sh to start the server

    ```bash
    ./uwsgi.sh
    ```

## Design decisions

1. Directories contained within config:ROOT_PATH are marked as audiobooks if and
   only if they contain at least one MP3 file

2. Audiobooks are uniquely identifiable by the collective hash of each MP3 file
   contained in the audiobook directory

   * Pro: If the directory structure is changed or files are moved, RSS/download
     link integrity is maintained, preserving app-side listening progress and
     history

   * Con: Each MP3 file is hashed, which can be slow on spinning rust w/ large
     collections

3. XML pubDate and list order is derived from MP3 track attributes; if not
   present or duplicates exist, tracks are sorted alphanumerically

   if a book's track numbers are unique but incorrect, a preference for filename
   sort can be established by creating an 'ignore_tracknum' file in the
   audiobook's path

4. No rebuild endpoint exists; cache-affecting routines are run externally by
   calling roka.py directly
