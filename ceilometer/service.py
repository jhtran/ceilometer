#!/usr/bin/env python
# -*- encoding: utf-8 -*-
#
# Copyright © 2012 eNovance <licensing@enovance.com>
#
# Author: Julien Danjou <julien@danjou.info>
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

import os
import random

from ceilometer import manager, utils
from ceilometer.openstack.common import cfg, importutils, log, rpc, service

opts = [
    cfg.IntOpt('report_interval',
               default=10,
               help='seconds between nodes reporting state to datastore'),
    cfg.IntOpt('periodic_interval',
               default=60,
               help='seconds between running periodic tasks'),
    cfg.IntOpt('periodic_fuzzy_delay',
               default=60,
               help='range of seconds to randomly delay when starting the'
                    ' periodic task scheduler to reduce stampeding.'
                    ' (Disable by setting to 0)'),
       ]

cfg.CONF.register_opts(opts)

CONFS = cfg.CONF
LOG = log.getLogger(__name__)

def prepare_service(argv=[]):
    cfg.CONF(argv[1:])
    log.setup('ceilometer')


class Service(service.Service):
    """Service object for binaries running on hosts.

    A service takes a manager and enables rpc by listening to queues based
    on topic. It also periodically runs tasks on the manager"""

    def __init__(self, host, binary, topic, manager, report_interval=None,
                 periodic_interval=None, periodic_fuzzy_delay=None,
                 *args, **kwargs):
        self.host = host
        self.binary = binary
        self.topic = topic
        self.manager_class_name = manager
        manager_class = importutils.import_class(self.manager_class_name)
        self.manager = manager_class(host=self.host, *args, **kwargs)
        self.report_interval = report_interval
        self.periodic_interval = periodic_interval
        self.periodic_fuzzy_delay = periodic_fuzzy_delay
        self.saved_args, self.saved_kwargs = args, kwargs
        self.timers = []

    def start(self):
        LOG.audit(_('Starting %(topic)s node'), {'topic': self.topic})
        self.manager.init_host()
        self.model_disconnected = False

        self.conn = rpc.create_connection(new=True)
        LOG.debug(_("Creating Consumer connection for Service %s") %
                  self.topic)

        rpc_dispatcher = self.manager.create_rpc_dispatcher()

        # Share this same connection for these Consumers
        self.conn.create_consumer(self.topic, rpc_dispatcher, fanout=False)

        node_topic = '%s.%s' % (self.topic, self.host)
        self.conn.create_consumer(node_topic, rpc_dispatcher, fanout=False)

        self.conn.create_consumer(self.topic, rpc_dispatcher, fanout=True)

        # Consume from all consumers in a thread
        self.conn.consume_in_thread()

        if self.report_interval:
            pulse = utils.LoopingCall()
            pulse.start(interval=self.report_interval,
                        initial_delay=self.report_interval)
            self.timers.append(pulse)

        if self.periodic_interval:
            if self.periodic_fuzzy_delay:
                initial_delay = random.randint(0, self.periodic_fuzzy_delay)
            else:
                initial_delay = None

            periodic = utils.LoopingCall(self.periodic_tasks)
            periodic.start(interval=self.periodic_interval,
                           initial_delay=initial_delay)
            self.timers.append(periodic)

    def __getattr__(self, key):
        manager = self.__dict__.get('manager', None)
        return getattr(manager, key)

    @classmethod
    def create(cls, host=None, binary=None, topic=None, manager=None,
               report_interval=None, periodic_interval=None,
               periodic_fuzzy_delay=None):
        """Instantiates class and passes back application object.

        :param host: defaults to CONFS.host
        :param binary: defaults to basename of executable
        :param topic: defaults to bin_name - 'nova-' part
        :param manager: defaults to CONFS.<topic>_manager
        :param report_interval: defaults to CONFS.report_interval
        :param periodic_interval: defaults to CONFS.periodic_interval
        :param periodic_fuzzy_delay: defaults to CONFS.periodic_fuzzy_delay

        """
        if not host:
            host = CONFS.host
        if not binary:
            binary = os.path.basename(inspect.stack()[-1][1])
        if not topic:
            topic = binary.rpartition('nova-')[2]
        if not manager:
            manager = CONFS.get('%s_manager' % topic, None)
        if report_interval is None:
            report_interval = CONFS.report_interval
        if periodic_interval is None:
            periodic_interval = CONFS.periodic_interval
        if periodic_fuzzy_delay is None:
            periodic_fuzzy_delay = CONFS.periodic_fuzzy_delay
        service_obj = cls(host, binary, topic, manager,
                          report_interval=report_interval,
                          periodic_interval=periodic_interval,
                          periodic_fuzzy_delay=periodic_fuzzy_delay)

        return service_obj

    def kill(self):
        """Destroy the service object in the datastore."""
        self.stop()

    def stop(self):
        # Try to shut the connection down, but if we get any sort of
        # errors, go ahead and ignore them.. as we're shutting down anyway
        try:
            self.conn.close()
        except Exception:
            pass
        for x in self.timers:
            try:
                x.stop()
            except Exception:
                pass
        self.timers = []

    def wait(self):
        for x in self.timers:
            try:
                x.wait()
            except Exception:
                pass

    def periodic_tasks(self, raise_on_error=False):
        """Tasks to be run at a periodic interval."""
        self.manager.periodic_tasks(raise_on_error=raise_on_error)

_launcher = None


def serve(server, workers=None):
    global _launcher
    if _launcher:
        raise RuntimeError(_('serve() can only be called once'))

    if workers:
        _launcher = service.ProcessLauncher()
        _launcher.launch_service(server, workers=workers)
    else:
        _launcher = service.ServiceLauncher()
        _launcher.launch_service(server)


def wait():
    _launcher.wait()
