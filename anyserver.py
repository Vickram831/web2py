#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
This file is part of the web2py Web Framework
Copyrighted by Massimo Di Pierro <mdipierro@cs.depaul.edu>
License: LGPLv3 (http://www.gnu.org/licenses/lgpl.html)

This file is based, although a rewrite, on MIT-licensed code from the Bottle web framework.
"""

import os
import sys
import optparse
import urllib

path = os.path.dirname(os.path.abspath(__file__))
os.chdir(path)
sys.path = [path] + [p for p in sys.path if p != path]

class Servers:
    @staticmethod
    def cgi(app, address=None, **options):
        from wsgiref.handlers import CGIHandler
        CGIHandler().run(app)

    @staticmethod
    def flup(app, address, **options):
        import flup.server.fcgi
        flup.server.fcgi.WSGIServer(app, bindAddress=address).run()

    @staticmethod
    def wsgiref(app, address, **options):
        from wsgiref.simple_server import make_server, WSGIRequestHandler

        class QuietHandler(WSGIRequestHandler):
            def log_request(self, *args, **kw):
                pass

        srv = make_server(address[0], address[1], app, handler_class=QuietHandler)
        srv.serve_forever()

    @staticmethod
    def cherrypy(app, address, **options):
        from cheroot.wsgi import Server as WSGIServer
        server = WSGIServer(address, app)
        server.start()

    @staticmethod
    def rocket(app, address, **options):
        from gluon.rocket import CherryPyWSGIServer
        server = CherryPyWSGIServer(address, app)
        server.start()

    @staticmethod
    def rocket_with_repoze_profiler(app, address, **options):
        from gluon.rocket import CherryPyWSGIServer
        from repoze.profile.profiler import AccumulatingProfileMiddleware
        from gluon.settings import global_settings
        global_settings.web2py_crontype = 'none'
        wrapped = AccumulatingProfileMiddleware(
            app,
            log_filename='wsgi.prof',
            discard_first_request=True,
            flush_at_shutdown=True,
            path='/__profile__'
        )
        server = CherryPyWSGIServer(address, wrapped)
        server.start()

    @staticmethod
    def paste(app, address, **options):
        from paste import httpserver
        httpserver.serve(app, host=address[0], port=address[1], **options)

    @staticmethod
    def fapws(app, address, **options):
        import fapws._evwsgi as evwsgi
        from fapws import base
        evwsgi.start(address[0], str(address[1]))
        evwsgi.set_base_module(base)

        def app(environ, start_response):
            environ['wsgi.multiprocess'] = False
            return app(environ, start_response)

        evwsgi.wsgi_cb(('', app))
        evwsgi.run()

    @staticmethod
    def gevent(app, address, **options):
        from gevent import pywsgi
        from gevent.pool import Pool
        workers = options['options'].workers
        pywsgi.WSGIServer(address, app, spawn=(int(workers) if workers else 'default'), log=None).serve_forever()

    @staticmethod
    def bjoern(app, address, **options):
        import bjoern
        bjoern.run(app, *address)

    @staticmethod
    def tornado(app, address, **options):
        import tornado.wsgi
        import tornado.httpserver
        import tornado.ioloop
        container = tornado.wsgi.WSGIContainer(app)
        server = tornado.httpserver.HTTPServer(container)
        server.listen(address=address[0], port=address[1])
        tornado.ioloop.IOLoop.instance().start()

    @staticmethod
    def twisted(app, address, **options):
        from twisted.web import server, wsgi
        from twisted.python.threadpool import ThreadPool
        from twisted.internet import reactor
        thread_pool = ThreadPool()
        thread_pool.start()
        reactor.addSystemEventTrigger('after', 'shutdown', thread_pool.stop)
        factory = server.Site(wsgi.WSGIResource(reactor, thread_pool, app))
        reactor.listenTCP(address[1], factory, interface=address[0])
        reactor.run()

    @staticmethod
    def diesel(app, address, **options):
        from diesel.protocols.wsgi import WSGIApplication
        app = WSGIApplication(app, port=address[1])
        app.run()

    @staticmethod
    def gunicorn(app, address, **options):
        from gunicorn.app.base import Application
        config = {'bind': f"{address[0]}:{address[1]}"}
        config.update(options)
        sys.argv = ['anyserver.py']

        class GunicornApplication(Application):
            def init(self, parser, opts, args):
                return config

            def load(self):
                return app

        g = GunicornApplication()
        g.run()

    @staticmethod
    def eventlet(app, address, **options):
        from eventlet import wsgi, listen
        wsgi.server(listen(address), app)

    @staticmethod
    def mongrel2(app, address, **options):
        import uuid
        from mongrel2 import handler
        conn = handler.Connection(str(uuid.uuid4()), "tcp://127.0.0.1:9997", "tcp://127.0.0.1:9996")
        mongrel2_handler(app, conn, debug=False)

    @staticmethod
    def motor(app, address, **options):
        import motor
        app = motor.WSGIContainer(app)
        http_server = motor.HTTPServer(app)
        http_server.listen(address[0], port=address[1])
        motor.IOLoop.instance().start()

    @staticmethod
    def pulsar(app, address, **options):
        from pulsar.apps import wsgi
        sys.argv = ['anyserver.py']
        s = wsgi.WSGIServer(callable=app, bind=f"{address[0]}:{address[1]}")
        s.start()

    @staticmethod
    def waitress(app, address, **options):
        from waitress import serve
        serve(app, host=address[0], port=address[1], _quiet=True)

def mongrel2_handler(application, conn, debug=False):
    from wsgiref.handlers import SimpleHandler
    try:
        import cStringIO as StringIO  # For Python 2
    except ImportError:
        import io as StringIO  # For Python 3

    while True:
        if debug:
            print("WAITING FOR REQUEST")

        req = conn.recv()
        if debug:
            print("REQUEST BODY: %r\n" % req.body)

        if req.is_disconnect():
            if debug:
                print("DISCONNECT")
            continue

        environ = req.headers
        environ['SERVER_PROTOCOL'] = 'HTTP/1.1'
        environ['REQUEST_METHOD'] = environ['METHOD']
        if ':' in environ['Host']:
            environ['SERVER_NAME'], environ['SERVER_PORT'] = environ['Host'].split(':')
        else:
            environ['SERVER_NAME'] = environ['Host']
            environ['SERVER_PORT'] = ''

        environ['SCRIPT_NAME'] = ''
        environ['PATH_INFO'] = urllib.parse.unquote(environ['PATH'])  # Use urllib.parse for Python 3
        environ['QUERY_STRING'] = environ['URI'].split('?')[1] if '?' in environ['URI'] else ''
        if 'Content-Length' in environ:
            environ['CONTENT_LENGTH'] = environ['Content-Length']
        environ['wsgi.input'] = req.body

        if debug:
            print("ENVIRON: %r\n" % environ)

        reqIO = StringIO.StringIO(req.body)
        errIO = StringIO.StringIO()
        respIO = StringIO.StringIO()

        handler = SimpleHandler(reqIO, respIO, errIO, environ, multithread=False, multiprocess=False)
        handler.run(application)

        response = respIO.getvalue().split("\r\n")
        data = response[-1]
        headers = dict(r.split(": ") for r in response[1:-2])
        code = response[0][9:12]
        status = response[0][13:]

        data = data.replace('\xef\xbb\xbf', '')
        errors = errIO.getvalue()

        if debug:
            print("RESPONSE: %r\n" % response)
        if errors:
            if debug:
                print("ERRORS: %r" % errors)
            data = "%s\r\n\r\n%s" % (data, errors)
        conn.reply_http(req, data, code=code, status=status, headers=headers)

def run(servername, ip, port, softcron=True, logging=False, profiler=None, options=None):
    if servername == 'gevent':
        from gevent import monkey
        monkey.patch_all()
    elif servername == 'eventlet':
        import eventlet
        eventlet.monkey_patch()

    import gluon.main

    application = (gluon.main.appfactory(wsgiapp=gluon.main.wsgibase,
                                          logfilename='httpserver.log', profiler_dir=profiler)
                   if logging else gluon.main.wsgibase)

    if
