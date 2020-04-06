#!/bin/sh

# sandbox dir is virtualenv (python3 -m venv sandbox)
. sandbox/bin/activate

# uwsgi.ini.example provided as template
uwsgi --ini uwsgi.ini
