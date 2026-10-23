"""
Seed Bank: the Gardiner Lab suite's record of plant lines, seed lots and plants.

Lines, the seed lots they are kept as, and the plants grown from them, with
how each descends from the others; which plasmids a line carries; phenotypes
with photos and 3D scans; segregation tests; storage; and labels with QR codes.
"""

import os

from flask import Flask, redirect, render_template, request

APP_VERSION = '0.5.0'


class PrefixMiddleware:
    """Mount the app under URL_PREFIX (/seeds), as the suite's proxy passes the full path."""

    def __init__(self, wsgi_app, prefix: str):
        self.wsgi_app = wsgi_app
        self.prefix = '/' + prefix.strip('/')

    def __call__(self, environ, start_response):
        path = environ.get('PATH_INFO', '')
        if path == self.prefix or path.startswith(self.prefix + '/'):
            environ['SCRIPT_NAME'] = environ.get('SCRIPT_NAME', '') + self.prefix
            environ['PATH_INFO'] = path[len(self.prefix):] or '/'
        return self.wsgi_app(environ, start_response)


def create_app() -> Flask:
    from app import db, people
    from app.api import api

    app = Flask(__name__)
    # 3D scans and photos can be large; each file is limited in app/attachments.py.
    app.config['MAX_CONTENT_LENGTH'] = 210 * 1024 * 1024
    db.initialize(os.environ.get('SEEDS_DATABASE_PATH', '/seeds/seeds.db'))
    app.register_blueprint(api, url_prefix='/api')

    def links() -> dict:
        return {
            'suite_home': os.environ.get('SUITE_HOME_URL', '/'),
            'editor': os.environ.get('EDITOR_URL', '/editor').rstrip('/'),
            'notebook': os.environ.get('NOTEBOOK_URL', '/notebook').rstrip('/'),
            # Lab Stocks copies the seed lots to eLabJournal; a lot's page asks it how far.
            'stocks': os.environ.get('STOCKS_URL', '/stocks').rstrip('/'),
            'logout': os.environ.get('SUITE_LOGOUT_URL', '/account/logout'),
            # Where phones reach the suite, for the codes on labels; unset, the
            # address the label page was opened at.
            'public': os.environ.get('SUITE_PUBLIC_URL', '').rstrip('/'),
        }

    def page(template: str):
        person = people.current()
        if person is None:
            login = os.environ.get('SUITE_LOGIN_URL', '/account/login')
            return redirect(f'{login}?next={request.script_root}/')
        return render_template(template, version=APP_VERSION, person=person, links=links())

    @app.route('/')
    def seeds_page():
        return page('seeds.html')

    @app.route('/labels')
    def labels_page():
        return page('labels.html')

    @app.route('/help')
    def help_page():
        return page('help.html')

    @app.route('/about')
    def about_page():
        return render_template('about.html', version=APP_VERSION, links=links())

    @app.route('/health')
    def health():
        return {'status': 'healthy', 'version': APP_VERSION}

    prefix = os.environ.get('URL_PREFIX', '').strip('/')
    if prefix:
        app.wsgi_app = PrefixMiddleware(app.wsgi_app, prefix)
    return app


app = create_app() if os.environ.get('SEEDS_NO_APP') != '1' else None

if __name__ == '__main__':
    create_app().run(host='0.0.0.0', port=int(os.environ.get('PORT', 5005)), debug=True)
