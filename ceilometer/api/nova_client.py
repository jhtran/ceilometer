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

import os
from novaclient.v1_1 import client as nova_client

from ceilometer.openstack.common import cfg

opts = [
    cfg.StrOpt('os-username',
               default=os.environ.get('OS_USERNAME', 'glance'),
               help='Username to use for openstack service access'),
    cfg.StrOpt('os-password',
               default=os.environ.get('OS_PASSWORD', 'admin'),
               help='Password to use for openstack service access'),
    cfg.StrOpt('os-tenant-id',
               default=os.environ.get('OS_TENANT_ID', ''),
               help='Tenant ID to use for openstack service access'),
    cfg.StrOpt('os-tenant-name',
               default=os.environ.get('OS_TENANT_NAME', 'admin'),
               help='Tenant name to use for openstack service access'),
    cfg.StrOpt('os-auth-url',
               default=os.environ.get('OS_AUTH_URL',
                                      'http://localhost:5000/v2.0'),
               help='Auth URL to use for openstack service access'),
       ]

cfg.CONF.register_opts(opts)


class Client(object):

    def __init__(self):
        """Returns nova client"""
        conf = cfg.CONF
        tenant = conf.os_tenant_id and conf.os_tenant_id or conf.os_tenant_name
        self.nova_client = nova_client.Client(username=cfg.CONF.os_username,
                                              api_key=cfg.CONF.os_password,
                                              project_id=tenant,
                                              auth_url=cfg.CONF.os_auth_url,
                                              no_cache=True)

    def instance_get_all_by_host(self, hostname):
        """Returns list of instances on particular host"""
        search_opts = {'host': hostname}
        return self.nova_client.servers.list(detailed=True, all_tenants=True,
                                             search_opts=search_opts)

    def floating_ip_get_all(self):
        """Returns all floating ips"""
        return self.nova_client.floating_ips.list()

    def instance_get(self, instance_id):
        """Returns instance"""
        return self.nova_client.servers.get(instance_id)
