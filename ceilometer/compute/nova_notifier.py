# -*- encoding: utf-8 -*-
#
# Copyright © 2012 New Dream Network, LLC (DreamHost)
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

from ceilometer.compute.manager import AgentManager


class CeilometerNovaNotifier(object):
    """Special notifier for Nova, doing special jobs for Ceilometer."""

    def __init__(self):
        self.manager = AgentManager()
        self.manager.init_host()
        self.nova_client = self.manager.nova_client

    def __call__(self, context, message):
        if message['event_type'] == 'compute.instance.delete.start':
            instance_id = message['payload']['instance_id']
            self.manager.poll_instance(context,
                                       self.nova_client.instance_get(
                                                         instance_id))

notify = CeilometerNovaNotifier()
