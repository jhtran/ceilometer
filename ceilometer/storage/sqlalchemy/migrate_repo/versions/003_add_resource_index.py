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

from sqlalchemy import *

meta = MetaData()

colnames = ['resource_id', 'counter_type', 'counter_volume', 'counter_name']


def upgrade(migrate_engine):
    meta.bind = migrate_engine
    meter = Table('meter', meta, autoload=True)
    for colname in colnames:
      idxname = "idx_%s" % colname
      col = getattr(meter.c, colname)
      idx = Index(idxname, col)
      idx.create(migrate_engine)
    idx_counters = Index('idx_counter_type_name',
                         meter.c.resource_id,
                         meter.c.counter_name, meter.c.counter_type)
    idx_counters.create(migrate_engine)


def downgrade(migrate_engine):
    meta.bind = migrate_engine
    meter = Table('meter', meta, autoload=True)
    for colname in colnames:
      idxname = "idx_%s" % colname
      col = getattr(meter.c, colname)
      idx = Index(idxname, col)
      idx.drop(migrate_engine)
    idx_counters = Index('idx_counter_type_name',
                         meter.c.resource_id,
                         meter.c.counter_name, meter.c.counter_type)
    idx_counters.drop(migrate_engine)
