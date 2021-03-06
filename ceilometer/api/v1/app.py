# -*- encoding: utf-8 -*-
#
# Copyright © 2012 New Dream Network, LLC (DreamHost)
#
# Author: Doug Hellmann <doug.hellmann@dreamhost.com>
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.
"""Set up the API server application instance
"""

import flask

from ceilometer.openstack.common import cfg
from ceilometer.openstack.common import jsonutils
from ceilometer import storage
from ceilometer.api.v1 import blueprint as v1_blueprint
from ceilometer.api import acl


storage.register_opts(cfg.CONF)


def make_app(enable_acl=True, attach_storage=True):
    app = flask.Flask('ceilometer.api')
    app.register_blueprint(v1_blueprint.blueprint, url_prefix='/v1')

    try:
        with open("sources.json", "r") as f:
            sources = jsonutils.load(f)
    except IOError:
        sources = {}

    @app.before_request
    def attach_config():
        flask.request.cfg = cfg.CONF
        flask.request.sources = sources

    if attach_storage:
        @app.before_request
        def attach_storage():
            storage_engine = storage.get_engine(cfg.CONF)
            flask.request.storage_engine = storage_engine
            flask.request.storage_conn = \
                storage_engine.get_connection(cfg.CONF)

    # Install the middleware wrapper
    if enable_acl:
        app.wsgi_app = acl.install(app.wsgi_app, cfg.CONF)
    return app

# For documentation
app = make_app(enable_acl=False, attach_storage=False)
