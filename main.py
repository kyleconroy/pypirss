#!/usr/bin/env python
#
# Copyright 2007 Google Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
import datetime
import logging
import os
import PyRSS2Gen
import xmlrpclib
from django.utils import simplejson as json
from google.appengine.api import memcache
from google.appengine.ext import webapp
from google.appengine.ext.webapp import template
from google.appengine.ext.webapp import util


class MainHandler(webapp.RequestHandler):

    def get(self):
        path = os.path.join(os.path.dirname(__file__), 'index.html')
        self.response.out.write(template.render(path, {}))

    def post(self):
        package = self.request.get("package")

        if package is not None:
            self.redirect("/%s" % package)
        else:
            self.redirect("/")


class PackageHandler(webapp.RequestHandler):

    def get(self, package):
        self.response.headers["Content-Type"] = "application/rss+xml"

        rss = memcache.get(package)

        if rss is not None:
            rss.write_xml(self.response.out)
            return

        client = xmlrpclib.ServerProxy('http://pypi.python.org/pypi')
        releases = client.package_releases(package, True)
        updates = []

        for release in releases[:10]:

            urls = memcache.get(release, namespace=package)

            if urls is None:
                urls = client.release_urls(package, release)
                memcache.set(release, urls, namespace=package)

            url = urls[0]
            link = "http://pypi.python.org/pypi/%s/%s" % (package, release)

            logging.error(url["upload_time"].value)
            dt = datetime.datetime.strptime(url["upload_time"].value,
                                            "%Y%m%dT%M:%S:%f")

            # Sort by md5?
            updates.append(
                PyRSS2Gen.RSSItem(
                    title="Version %s of %s release" % (package, release),
                    link=link,
                    guid=PyRSS2Gen.Guid(link),
                    pubDate=dt,
                    )
                )

        rss = PyRSS2Gen.RSS2(
            title = "PyPi Version feed for %s" % package,
            link = "http://pypi.python.org/pypi/%s" % package,
            description = "The latest releases for package %s" % package,
            lastBuildDate = datetime.datetime.utcnow(),
            items = updates)

        memcache.add(package, rss, 60 * 60 * 12) # Save for half a day
        rss.write_xml(self.response.out)


def main():
    ROUTES = [
        ('/(.+)', PackageHandler),
        ('/', MainHandler),
        ]

    application = webapp.WSGIApplication(ROUTES, debug=True)
    util.run_wsgi_app(application)


if __name__ == '__main__':
    main()
