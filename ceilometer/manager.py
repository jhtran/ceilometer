# -*- encoding: utf-8 -*-
#
# Author: John Tran <jhtran@att.com>
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

import pkg_resources
import socket

from ceilometer import publish
from ceilometer.api import nova_client
from ceilometer.openstack.common import cfg, periodic_task
from ceilometer.openstack.common.rpc import dispatcher as rpc_dispatcher

opts = [
    cfg.StrOpt('host',
               default=socket.gethostname(),
               help='Name of this node.  This can be an opaque identifier.  '
                    'It is not necessarily a hostname, FQDN, or IP address. '
                    'However, the node name must be valid within '
                    'an AMQP key, and if using ZeroMQ, a valid '
                    'hostname, FQDN, or IP address'),
       ]

cfg.CONF.register_opts(opts)


class AgentManager(periodic_task.PeriodicTasks):

    def __init__(self, host=None):
        if not host:
            host = getattr(cfg.CONF, 'host')
        self.host = host
        self.nova_client = nova_client.Client()

    def init_host(self):
        self._load_plugins()
        return

    def _load_plugins(self, plugin_namespace, logger):
        self.pollsters = []
        for ep in pkg_resources.iter_entry_points(plugin_namespace):
            try:
                plugin_class = ep.load()
                plugin = plugin_class()
                # FIXME(dhellmann): Currently assumes all plugins are
                # enabled when they are discovered and
                # importable. Need to add check against global
                # configuration flag and check that asks the plugin if
                # it should be enabled.
                self.pollsters.append((ep.name, plugin))
                logger.info('loaded pollster %s:%s',
                         plugin_namespace, ep.name)
            except Exception as err:
                logger.warning('Failed to load pollster %s:%s',
                            ep.name, err)
                logger.exception(err)
        if not self.pollsters:
            logger.warning('Failed to load any pollsters for %s',
                        plugin_namespace)
        return

    def create_rpc_dispatcher(self):
        '''Get the rpc dispatcher for this manager.

        If a manager would like to set an rpc API version, or support more than
        one class as the target of rpc messages, override this method.
        '''
        return rpc_dispatcher.RpcDispatcher([self])


    def periodic_tasks(self, raise_on_error=False):
        """Tasks to be run at a periodic interval."""
        for task_name, task in self._periodic_tasks:
            full_task_name = '.'.join([self.__class__.__name__, task_name])

            ticks_to_skip = self._ticks_to_skip[task_name]
            if ticks_to_skip > 0:
                LOG.debug(_("Skipping %(full_task_name)s, %(ticks_to_skip)s"
                            " ticks left until next run"), locals())
                self._ticks_to_skip[task_name] -= 1
                continue

            self._ticks_to_skip[task_name] = task._ticks_between_runs
            LOG.debug(_("Running periodic task %(full_task_name)s"), locals())

            try:
                task(self, context)
                # NOTE(tiantian): After finished a task, allow manager to
                # do other work (report_state, processing AMPQ request etc.)
                eventlet.sleep(0)
            except Exception as e:
                if raise_on_error:
                    raise
                LOG.exception(_("Error during %(full_task_name)s: %(e)s"),
                              locals())
