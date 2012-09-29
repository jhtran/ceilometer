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

from ceilometer import manager
from ceilometer.openstack.common import log
from ceilometer import publish


LOG = log.getLogger(__name__)

PLUGIN_NAMESPACE = 'ceilometer.poll.central'


class AgentManager(manager.AgentManager):

    def _load_plugins(self):
        super(AgentManager, self)._load_plugins(PLUGIN_NAMESPACE, LOG)

    def periodic_tasks(self, context, raise_on_error=False):
        """Tasks to be run at a periodic interval."""
        for name, pollster in self.pollsters:
            try:
                LOG.info('polling %s', name)
                for c in pollster.get_counters(self, context):
                    LOG.info('COUNTER: %s', c)
                    publish.publish_counter(context, c)
            except Exception as err:
                LOG.warning('Continuing after error from %s: %s', name, err)
                LOG.exception(err)
