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

import copy

from lxml import etree

from nova import flags

from ceilometer import counter
from ceilometer.compute import plugin
from ceilometer.compute import instance as compute_instance
from ceilometer.openstack.common import importutils
from ceilometer.openstack.common import log
from ceilometer.openstack.common import timeutils

FLAGS = flags.FLAGS


def _instance_name(instance):
    """Shortcut to get instance name"""
    return getattr(instance, 'OS-EXT-SRV-ATTR:instance_name', None)


def get_libvirt_connection():
    """Return an open connection for talking to libvirt."""
    # The direct-import implementation only works with Folsom because
    # the configuration setting changed.
    try:
        return importutils.import_object_ns('nova.virt',
                                            FLAGS.compute_driver)
    except ImportError:
        # Fall back to the way it was done in Essex.
        import nova.virt.connection
        return nova.virt.connection.get_connection(read_only=True)


def make_counter_from_instance(instance, name, type, volume):
    return counter.Counter(
        source='?',
        name=name,
        type=type,
        volume=volume,
        user_id=instance.user_id,
        project_id=instance.tenant_id,
        resource_id=instance.id,
        timestamp=timeutils.isotime(),
        resource_metadata=compute_instance.get_metadata_from_object(instance),
        )


class InstancePollster(plugin.ComputePollster):

    def get_counters(self, manager, instance):
        yield make_counter_from_instance(instance,
                                         name='instance',
                                         type=counter.TYPE_GAUGE,
                                         volume=1,
        )


class DiskIOPollster(plugin.ComputePollster):

    LOG = log.getLogger(__name__ + '.diskio')

    DISKIO_USAGE_MESSAGE = ' '.join(["DISKIO USAGE:",
                                     "%s %s:",
                                     "read-requests=%d",
                                     "read-bytes=%d",
                                     "write-requests=%d",
                                     "write-bytes=%d",
                                     "errors=%d",
                                     ])

    def _get_disks(self, conn, instance):
        """Get disks of an instance, only used to bypass bug#998089."""
        domain = conn._conn.lookupByName(instance)
        tree = etree.fromstring(domain.XMLDesc(0))
        return filter(bool,
                      [target.get('dev')
                       for target in tree.findall('devices/disk/target')
                       ])

    def get_counters(self, manager, instance):
        if FLAGS.compute_driver == 'libvirt.LibvirtDriver':
            conn = get_libvirt_connection()
            # TODO(jd) This does not work see bug#998089
            # for disk in conn.get_disks(instance_name):
            instance_name = _instance_name(instance)
            try:
                disks = self._get_disks(conn, instance_name)
            except Exception as err:
                self.LOG.warning('Ignoring instance %s: %s',
                                 instance_name, err)
                self.LOG.exception(err)
            else:
                r_bytes = 0
                r_requests = 0
                w_bytes = 0
                w_requests = 0
                for disk in disks:
                    stats = conn.block_stats(instance_name, disk)
                    self.LOG.info(self.DISKIO_USAGE_MESSAGE,
                                  instance, disk, stats[0], stats[1],
                                  stats[2], stats[3], stats[4])
                    r_bytes += stats[0]
                    r_requests += stats[1]
                    w_bytes += stats[3]
                    w_requests += stats[2]
                yield make_counter_from_instance(instance,
                                                 name='disk.read.requests',
                                                 type=counter.TYPE_CUMULATIVE,
                                                 volume=r_requests,
                                                 )
                yield make_counter_from_instance(instance,
                                                 name='disk.read.bytes',
                                                 type=counter.TYPE_CUMULATIVE,
                                                 volume=r_bytes,
                                                 )
                yield make_counter_from_instance(instance,
                                                 name='disk.write.requests',
                                                 type=counter.TYPE_CUMULATIVE,
                                                 volume=w_requests,
                                                 )
                yield make_counter_from_instance(instance,
                                                 name='disk.write.bytes',
                                                 type=counter.TYPE_CUMULATIVE,
                                                 volume=w_bytes,
                                                 )


class CPUPollster(plugin.ComputePollster):

    LOG = log.getLogger(__name__ + '.cpu')

    def get_counters(self, manager, instance):
        conn = get_libvirt_connection()
        self.LOG.info('checking instance %s', instance.id)
        try:
            cpu_info = conn.get_info({'name': _instance_name(instance)})
            self.LOG.info("CPUTIME USAGE: %s %d",
                          instance, cpu_info['cpu_time'])
            yield make_counter_from_instance(instance,
                                             name='cpu',
                                             type=counter.TYPE_CUMULATIVE,
                                             volume=cpu_info['cpu_time'],
                                             )
        except Exception as err:
            self.LOG.error('could not get CPU time for %s: %s',
                           instance.id, err)
            self.LOG.exception(err)


class NetPollster(plugin.ComputePollster):

    LOG = log.getLogger(__name__ + '.net')

    NET_USAGE_MESSAGE = ' '.join(["NETWORK USAGE:", "%s %s:", "read-bytes=%d",
                                  "write-bytes=%d"])

    def _get_vnics(self, conn, instance):
        """Get disks of an instance, only used to bypass bug#998089."""
        domain = conn._conn.lookupByName(_instance_name(instance))
        tree = etree.fromstring(domain.XMLDesc(0))
        vnics = []
        for interface in tree.findall('devices/interface'):
            vnic = {}
            vnic['name'] = interface.find('target').get('dev')
            vnic['mac'] = interface.find('mac').get('address')
            vnic['fref'] = interface.find('filterref').get('filter')
            for param in interface.findall('filterref/parameter'):
                vnic[param.get('name').lower()] = param.get('value')
            vnics.append(vnic)
        return vnics

    @staticmethod
    def make_vnic_counter(instance, name, type, volume, vnic_data):
        resource_metadata = copy.copy(vnic_data)
        resource_metadata['instance_id'] = instance.id

        return counter.Counter(
            source='?',
            name=name,
            type=type,
            volume=volume,
            user_id=instance.user_id,
            project_id=instance.tenant_id,
            resource_id=vnic_data['fref'],
            timestamp=timeutils.isotime(),
            resource_metadata=resource_metadata
        )

    def get_counters(self, manager, instance):
        conn = get_libvirt_connection()
        instance_name = _instance_name(instance)
        self.LOG.info('checking instance %s', instance.id)
        try:
            vnics = self._get_vnics(conn, instance)
        except Exception as err:
            self.LOG.warning('Ignoring instance %s: %s',
                             instance_name, err)
            self.LOG.exception(err)
        else:
            domain = conn._conn.lookupByName(instance_name)
            for vnic in vnics:
                rx_bytes, rx_packets, _, _, \
                    tx_bytes, tx_packets, _, _ = \
                    domain.interfaceStats(vnic['name'])
                self.LOG.info(self.NET_USAGE_MESSAGE, instance_name,
                              vnic['name'], rx_bytes, tx_bytes)
                yield self.make_vnic_counter(instance,
                                             name='network.incoming.bytes',
                                             type=counter.TYPE_CUMULATIVE,
                                             volume=rx_bytes,
                                             vnic_data=vnic,
                                             )
                yield self.make_vnic_counter(instance,
                                             name='network.outgoing.bytes',
                                             type=counter.TYPE_CUMULATIVE,
                                             volume=tx_bytes,
                                             vnic_data=vnic,
                                             )
                yield self.make_vnic_counter(instance,
                                             name='network.incoming.packets',
                                             type=counter.TYPE_CUMULATIVE,
                                             volume=rx_packets,
                                             vnic_data=vnic,
                                             )
                yield self.make_vnic_counter(instance,
                                             name='network.outgoing.packets',
                                             type=counter.TYPE_CUMULATIVE,
                                             volume=tx_packets,
                                             vnic_data=vnic,
                                             )
