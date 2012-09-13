# -*- encoding: utf-8 -*-
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
"""Tests for ceilometer/storage/impl_sqlalchemy.py
"""

import datetime
import logging
import os
import re
import unittest

import mox

from nose.plugins import skip

from ceilometer import counter
from ceilometer import meter
from ceilometer import storage
from ceilometer.storage import migration
from ceilometer.storage import impl_sqlalchemy
from ceilometer.storage.sqlalchemy.models import User, UserSource, Resource
from ceilometer.storage.sqlalchemy.models import Project, ProjectSource, Meter
import ceilometer.openstack.common.cfg as cfg


LOG = logging.getLogger(__name__)


class Connection(impl_sqlalchemy.Connection):

    def _get_connection(self, conf):
        try:
            return super(Connection, self)._get_connection(conf)
        except:
            LOG.debug('Unable to connect to %s' % conf.database_connection)
            raise


class SQLAlchemyEngineTestBase(unittest.TestCase):

    def setUp(self):
        super(SQLAlchemyEngineTestBase, self).setUp()

        self.conf = cfg.CONF
        self.conf.database_connection = 'sqlite:///testdb.sqlite'
        testdbf = os.path.join('../tests/testdb.sqlite')
        if os.path.exists(testdbf):
            os.remove(testdbf)
        migration.db_sync()
        self.conn = Connection(self.conf)
        self.session = self.conn.session

        self.counter = counter.Counter(
            'test-1',
            'instance',
            'cumulative',
            volume=1,
            user_id=11,
            project_id=1,
            resource_id=111,
            timestamp=datetime.datetime(2012, 7, 2, 10, 40),
            duration=0,
            resource_metadata={'display_name': 'test-server',
                               'tag': 'self.counter',
                               }
            )
        self.msg1 = meter.meter_message_from_counter(self.counter)
        self.conn.record_metering_data(self.msg1)

        self.counter2 = counter.Counter(
            'test-2',
            'instance',
            'cumulative',
            volume=1,
            user_id=11,
            project_id=1,
            resource_id=112,
            timestamp=datetime.datetime(2012, 7, 2, 10, 41),
            duration=0,
            resource_metadata={'display_name': 'test-server',
                               'tag': 'self.counter2',
                               }
            )
        self.msg2 = meter.meter_message_from_counter(self.counter2)
        self.conn.record_metering_data(self.msg2)

        self.counter3 = counter.Counter(
            'test-3',
            'instance',
            'cumulative',
            volume=1,
            user_id=12,
            project_id=1,
            resource_id=112,
            timestamp=datetime.datetime(2012, 7, 2, 10, 41),
            duration=0,
            resource_metadata={'display_name': 'test-server',
                               'tag': 'self.counter3',
                               }
            )
        self.msg3 = meter.meter_message_from_counter(self.counter3)
        self.conn.record_metering_data(self.msg3)

        for i in range(2, 4):
            c = counter.Counter(
                'test',
                'instance',
                'cumulative',
                1,
                '%s' % i,
                '%s' % i,
                '%s' % i,
                timestamp=datetime.datetime(2012, 7, 2, 10, 40 + i),
                duration=0,
                resource_metadata={'display_name': 'test-server',
                                   'tag': 'counter-%s' % i,
                                  }
                )
            msg = meter.meter_message_from_counter(c)
            self.conn.record_metering_data(msg)


class UserTest(SQLAlchemyEngineTestBase):

    def test_new_user(self):
        user = self.session.query(User).get(11)
        assert user is not None

    def test_new_user_source(self):
        user = self.session.query(User).get(11)
        assert hasattr(user, 'sources')
        assert map(lambda x: x.name, user.sources) == ['test-1', 'test-2']

    def test_get_users(self):
        assert set(self.conn.get_users()) == set([2, 3, 11, 12])

    def test_get_users_by_source(self):
        users = self.conn.get_users(source='test-1')
        assert len(users) == 1
        assert users == [11]


class ProjectTest(SQLAlchemyEngineTestBase):

    def test_new_project(self):
        project = self.session.query(Project).get(1)
        assert project is not None

    def test_new_project_source(self):
        project = self.session.query(Project).get(1)
        assert hasattr(project, 'sources')
        sources = map(lambda x: x.name, project.sources)
        assert sources == ['test-1', 'test-2', 'test-3']

    def test_get_projects(self):
        projects = self.session.query(Project).all()
        projects = map(lambda x: x.id, projects)
        assert set(projects) == set([1, 2, 3])

    def test_get_projects_by_source(self):
        projects = self.conn.get_projects(source='test-1')
        assert len(projects) == 1
        assert projects == [1]


class ResourceTest(SQLAlchemyEngineTestBase):

    def test_new_resource(self):
        resource = self.session.query(Resource).get(111)
        assert resource is not None

    def test_new_resource_project(self):
        resource = self.session.query(Resource).get(111)
        assert hasattr(resource, 'project')
        assert resource.project.id == 1

    def test_new_resource_user(self):
        resource = self.session.query(Resource).get(111)
        assert hasattr(resource, 'user')
        assert resource.user.id  == 11

    def test_new_resource_meter(self):
        assert self.session.query(Resource).filter_by(id=111).join(Meter).\
                            filter(Meter.counter_name == 'instance').\
                            filter(Meter.counter_type == 'cumulative').first()

    def test_new_resource_metadata(self):
        resource = self.session.query(Resource).get(111)
        assert hasattr(resource, 'metadata')
        metadata = resource.resource_metadata
        assert metadata['display_name'] == 'test-server'

    def test_get_resources(self):
        resources = list(self.conn.get_resources())
        assert len(resources) == 4
        resource = self.session.query(Resource).get(111)
        assert resource.project.id == 1
        assert resource.user.id == 11
        assert hasattr(resource, 'metadata')
        foo = map(lambda x: [x.counter_name, x.counter_type], resource.meters)
        assert ['instance', 'cumulative'] in foo

    def test_get_resources_start_timestamp(self):
        timestamp = datetime.datetime(2012, 7, 2, 10, 42)
        resources = list(self.conn.get_resources(start_timestamp=timestamp))
        resource_ids = [r['resource_id'] for r in resources]
        expected = set([2, 3])
        assert set(resource_ids) == expected

    def test_get_resources_end_timestamp(self):
        timestamp = datetime.datetime(2012, 7, 2, 10, 42)
        resources = list(self.conn.get_resources(end_timestamp=timestamp))
        resource_ids = [r['resource_id'] for r in resources]
        expected = set([111, 112, 2])
        assert set(resource_ids) == expected

    def test_get_resources_both_timestamps(self):
        start_ts = datetime.datetime(2012, 7, 2, 10, 42)
        end_ts = datetime.datetime(2012, 7, 2, 10, 43)
        resources = list(self.conn.get_resources(start_timestamp=start_ts,
                                                 end_timestamp=end_ts)
                        )
        resource_ids = [r['resource_id'] for r in resources]
        expected = set([2, 3])
        assert set(resource_ids) == expected

    def test_get_resources_by_source(self):
        resources = list(self.conn.get_resources(source='test-1'))
        assert len(resources) == 1
        ids = set(r['resource_id'] for r in resources)
        assert ids == set([111])

    def test_get_resources_by_user(self):
        resources = list(self.conn.get_resources(user=11))
        assert len(resources) == 1
        ids = set(r['resource_id'] for r in resources)
        assert ids == set([111])

    def test_get_resources_by_project(self):
        resources = list(self.conn.get_resources(project=1))
        assert len(resources) == 2
        ids = set(r['resource_id'] for r in resources)
        assert ids == set([111, 112])


class MeterTest(SQLAlchemyEngineTestBase):

    def _compare_raw(self, msg_dict, result_dict):
        for k, v in msg_dict.items():
            if k in ['timestamp', 'source']:
                continue
            if k == 'resource_metadata':
               key = result_dict[k]
               value = v
            else:
               key = str(result_dict[k])
               value = str(v)
            assert key == value

    def _iterate_msgs(self, results):
        for meter in results:
            labels = map(lambda x: x['name'], meter['sources'])
            # should only have one source
            assert len(labels) == 1
            count = re.match('test-(\d+)', labels[0]).group(1)
            self._compare_raw(getattr(self, 'msg'+count), meter)

    def test_new_meter(self):
        meter = self.session.query(Meter).first()
        assert meter is not None

    def test_get_raw_events_by_user(self):
        f = storage.EventFilter(user=11)
        results = list(self.conn.get_raw_events(f))
        assert len(results) == 2
        self._iterate_msgs(results)

    def test_get_raw_events_by_project(self):
        f = storage.EventFilter(project=1)
        results = list(self.conn.get_raw_events(f))
        assert len(results) == 3
        self._iterate_msgs(results)

    def test_get_raw_events_by_resource(self):
        f = storage.EventFilter(user=11, resource=111)
        results = list(self.conn.get_raw_events(f))
        assert len(results) == 1
        self._compare_raw(self.msg1, results[0])

    def test_get_raw_events_by_start_time(self):
        f = storage.EventFilter(
            user=11,
            start=datetime.datetime(2012, 7, 2, 10, 41),
            )
        results = list(self.conn.get_raw_events(f))
        assert len(results) == 1
        assert results[0]['timestamp'] == datetime.datetime(2012, 7, 2, 10, 41)

    def test_get_raw_events_by_end_time(self):
        f = storage.EventFilter(
            user=11,
            end=datetime.datetime(2012, 7, 2, 10, 41),
            )
        results = list(self.conn.get_raw_events(f))
        length = len(results)
        assert length == 1
        assert results[0]['timestamp'] == datetime.datetime(2012, 7, 2, 10, 40)

    def test_get_raw_events_by_both_times(self):
        f = storage.EventFilter(
            start=datetime.datetime(2012, 7, 2, 10, 42),
            end=datetime.datetime(2012, 7, 2, 10, 43),
            )
        results = list(self.conn.get_raw_events(f))
        length = len(results)
        assert length == 1
        assert results[0]['timestamp'] == datetime.datetime(2012, 7, 2, 10, 42)

    def test_get_raw_events_by_meter(self):
        f = storage.EventFilter(user=11, meter='no-such-meter')
        results = list(self.conn.get_raw_events(f))
        assert not results

    def test_get_raw_events_by_meter2(self):
        f = storage.EventFilter(user=11, meter='instance')
        results = list(self.conn.get_raw_events(f))
        assert results

class TestGetEventInterval(SQLAlchemyEngineTestBase):

    def setUp(self):
        super(TestGetEventInterval, self).setUp()

        # Create events relative to the range and pretend
        # that the intervening events exist.

        self.start = datetime.datetime(2012, 8, 28, 0, 0)
        self.end = datetime.datetime(2012, 8, 29, 0, 0)

        self.early1 = self.start - datetime.timedelta(minutes=20)
        self.early2 = self.start - datetime.timedelta(minutes=10)


        self.middle1 = self.start + datetime.timedelta(minutes=10)
        self.middle2 = self.end - datetime.timedelta(minutes=10)


        self.late1 = self.end + datetime.timedelta(minutes=10)
        self.late2 = self.end + datetime.timedelta(minutes=20)

        self._filter = storage.EventFilter(
            resource='111',
            meter='instance',
            start=self.start,
            end=self.end,
            )

    def _make_events(self, *timestamps):
        for t in timestamps:
            c = counter.Counter(
                'test',
                'instance',
                'cumulative',
                1,
                '11',
                '1',
                '111',
                timestamp=t,
                duration=0,
                resource_metadata={'display_name': 'test-server',
                                   }
                )
            msg = meter.meter_message_from_counter(c)
            self.conn.record_metering_data(msg)

    def test_before_range(self):
        self._make_events(self.early1, self.early2)
        s, e = self.conn.get_event_interval(self._filter)
        assert s is None
        assert e is None

    def test_overlap_range_start(self):
        self._make_events(self.early1, self.start, self.middle1)
        s, e = self.conn.get_event_interval(self._filter)
        assert s == self.start
        assert e == self.middle1

    def test_within_range(self):
        self._make_events(self.middle1, self.middle2)
        s, e = self.conn.get_event_interval(self._filter)
        assert s == self.middle1
        assert e == self.middle2

    def test_within_range_zero_duration(self):
        self._make_events(self.middle1)
        s, e = self.conn.get_event_interval(self._filter)
        assert s == self.middle1
        assert e == self.middle1

    def test_within_range_zero_duration_two_events(self):
        self._make_events(self.middle1, self.middle1)
        s, e = self.conn.get_event_interval(self._filter)
        assert s == self.middle1
        assert e == self.middle1

    def test_overlap_range_end(self):
        self._make_events(self.middle2, self.end, self.late1)
        s, e = self.conn.get_event_interval(self._filter)
        assert s == self.middle2
        assert e == self.middle2

    def test_overlap_range_end_with_offset(self):
        self._make_events(self.middle2, self.end, self.late1)
        self._filter.end = self.late1
        s, e = self.conn.get_event_interval(self._filter)
        assert s == self.middle2
        assert e == self.end

    def test_after_range(self):
        self._make_events(self.late1, self.late2)
        s, e = self.conn.get_event_interval(self._filter)
        assert s is None
        assert e is None
