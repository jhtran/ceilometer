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
"""SQLAlchemy storage backend
"""

import copy
import datetime

from ceilometer.openstack.common import log
from ceilometer.openstack.common import cfg
from ceilometer.storage import base
from ceilometer.storage.sqlalchemy.models import User, UserSource, Source
from ceilometer.storage.sqlalchemy.models import Resource, ResourceSource
from ceilometer.storage.sqlalchemy.models import Project, ProjectSource
from ceilometer.storage.sqlalchemy.models import Meter, MeterSource
from ceilometer.storage.sqlalchemy.recipes import unique_constructor
from ceilometer.storage.sqlalchemy.session import get_session
import ceilometer.storage.sqlalchemy.session as session

LOG = log.getLogger(__name__)


class SQLAlchemyStorage(base.StorageEngine):
    """Put the data into a SQLAlchemy database

    Tables:

    - user
      - { _id: user id
          source: [ array of source ids reporting for the user ]
          }
    - project
      - { _id: project id
          source: [ array of source ids reporting for the project ]
          }
    - meter
      - the raw incoming data
    - resource
      - the metadata for resources
      - { _id: uuid of resource,
          metadata: metadata dictionaries
          timestamp: datetime of last update
          user_id: uuid
          project_id: uuid
          meter: [ array of {counter_name: string, counter_type: string} ]
        }
    """

    OPTIONS = []

    def register_opts(self, conf):
        """Register any configuration options used by this engine.
        """
        conf.register_opts(self.OPTIONS)

    def get_connection(self, conf):
        """Return a Connection instance based on the configuration settings.
        """
        return Connection(conf)


def make_query_from_filter(query, event_filter, require_meter=True):
    """Return a query dictionary based on the settings in the filter.

    :param filter: EventFilter instance
    :param require_meter: If true and the filter does not have a meter,
                          raise an error.
    """

    if event_filter.meter:
        query = query.filter(Meter.counter_name == event_filter.meter)
    elif require_meter:
        raise RuntimeError('Missing required meter specifier')
    if event_filter.source:
        query = query.filter_by(source=event_filter.source)
    if event_filter.start:
        query = query = query.filter(Meter.timestamp >= event_filter.start)
    if event_filter.end:
        query = query = query.filter(Meter.timestamp < event_filter.end)
    if event_filter.user:
        query = query.filter_by(user_id=event_filter.user)
    elif event_filter.project:
        query = query.filter_by(project_id=event_filter.project)
    if event_filter.resource:
        query = query.filter_by(resource_id=event_filter.resource)

    return query


class Connection(base.Connection):
    """SqlAlchemy connection.
    """

    def __init__(self, conf):
        LOG.info('connecting to %s', conf.database_connection)
        self.session = self._get_connection(conf)
        self.source_model = self._unique_construct(Source)
        return

    def _get_connection(self, conf):
        """Return a connection to the database.
        """
        return session.get_session()

    def _unique_construct(self, model_class):
        """Return session specific unique constructed model class - see
           http://www.sqlalchemy.org/trac/wiki/UsageRecipes/UniqueObject
        """
        newclass = unique_constructor(self.session,
                lambda name:name,
                lambda query, name:query.filter(model_class.name==name)
        )(model_class)
        return newclass

    def record_metering_data(self, data):
        """Write the data to the backend storage system.

        :param data: a dictionary such as returned by
                     ceilometer.meter.meter_message_from_counter
        """
        # create/update user && project, add/update their sources list
        source = data['source']
        user = self.session.merge(User(id=data['user_id']))
        if source not in user.sources:
            user.sources.append(source)

        self.session.flush()

        project = self.session.merge(Project(id=data['project_id']))
        #if not filter(lambda x: x.name == source, project.sources):
        #    project.sources.append(ProjectSource(name=source))

        self.session.flush()

        # Record the updated resource metadata
        rtimestamp = datetime.datetime.utcnow()
        rmetadata = data['resource_metadata']

        resource = self.session.merge(Resource(id=data['resource_id']))
        #if not filter(lambda x: x.name == source, resource.sources):
        #    resource.sources.append(ResourceSource(name=source))
        resource.project = project
        resource.user = user
        resource.timestamp = data['timestamp']
        resource.received_timestamp = rtimestamp
        # Current metadata being used and when it was last updated.
        resource.resource_metadata = rmetadata

        self.session.flush()

        # Record the raw data for the event.
        meter = self.session.merge(Meter(counter_type=data['counter_type'],
                                         counter_name=data['counter_name'],
                                         resource=resource))
        meter.project = project
        meter.user = user
        #if not filter(lambda x: x.name == source, meter.sources):
        #    meter.sources.append(MeterSource(name=source))
        meter.timestamp = data['timestamp']
        meter.resource_metadata = rmetadata
        meter.counter_duration = data['counter_duration']
        meter.counter_volume = data['counter_volume']
        meter.message_signature = data['message_signature']
        meter.message_id = data['message_id']

        self.session.flush()

        return

    def get_users(self, source=None):
        """Return an iterable of user id strings.

        :param source: Optional source filter.
        """
        query = model_query(User.id, session=self.session)
        if source is not None:
            query = query.filter(User.sources.contains(source))
        return (x[0] for x in query.all())

    def get_projects(self, source=None):
        """Return an iterable of project id strings.

        :param source: Optional source filter.
        """
        query = model_query(Project, session=self.session)
        if source:
            query = query.join(ProjectSource).\
                        filter(ProjectSource.name == source)
        return [x.id for x in query.all()]

    def get_resources(self, user=None, project=None, source=None,
                      start_timestamp=None, end_timestamp=None,
                      session=None):
        """Return an iterable of dictionaries containing resource information.

        { 'resource_id': UUID of the resource,
          'project_id': UUID of project owning the resource,
          'user_id': UUID of user owning the resource,
          'timestamp': UTC datetime of last update to the resource,
          'metadata': most current metadata for the resource,
          'meter': list of the meters reporting data for the resource,
          }

        :param user: Optional ID for user that owns the resource.
        :param project: Optional ID for project that owns the resource.
        :param source: Optional source filter.
        :param start_timestamp: Optional modified timestamp start range.
        :param end_timestamp: Optional modified timestamp end range.
        """
        query = model_query(Resource, session=session)
        if user is not None:
            query = query.filter(Resource.user_id == user)

        query = query.join(Meter)
        if user is not None:
            query = query.filter(Meter.user_id == user)
        if start_timestamp is not None:
            query = query.filter(Meter.timestamp >= start_timestamp)
        if end_timestamp:
            query = query.filter(Meter.timestamp <= end_timestamp)
        if project is not None:
            query = query.filter(Meter.project_id == project)
        if source is not None:
            query = query.join(ResourceSource)
            query = query.filter(ResourceSource.name == source)

        for resource in query.all():
            r = row2dict(resource)
            # Replace the '_id' key with 'resource_id' to meet the
            # caller's expectations.
            r['resource_id'] = r['id']
            del r['id']
            yield r

    def get_raw_events(self, event_filter):
        """Return an iterable of raw event data as created by
        :func:`ceilometer.meter.meter_message_from_counter`.
        """
        query = model_query(Meter, session=self.session)
        query = make_query_from_filter(query, event_filter,
                                       require_meter=False)
        events = query.all()

        for e in events:
            # Remove the ObjectId generated by the database when
            # the event was inserted. It is an implementation
            # detail that should not leak outside of the driver.
            e = row2dict(e)
            del e['id']
            yield e

    def get_volume_sum(self, event_filter):
        # it isn't clear these are used
        pass

    def get_volume_max(self, event_filter):
        # it isn't clear these are used
        pass

    def get_event_interval(self, event_filter):
        """Return the min and max timestamps from events,
        using the event_filter to limit the events seen.

        ( datetime.datetime(), datetime.datetime() )
        """
        func = session.func()
        query = self.session.query(func.min(Meter.timestamp),
                                   func.max(Meter.timestamp))
        query = make_query_from_filter(query, event_filter)
        results = query.all()
        a_min, a_max = results[0]
        return (a_min, a_max)


############################


def user_get(user_id, session=None):
    result = model_query(User, session=session).\
                     filter_by(id=user_id).\
                     first()
    return result


def project_get(project_id, session=None):
    result = model_query(Project, session=session).\
                     filter_by(id=project_id).\
                     first()
    return result


def resource_get(resource_id, session=None):
    result = model_query(Project, session=session).\
                     filter_by(id=resource_id).\
                     first()
    return result


def model_query(*args, **kwargs):
    """Query helper

    :param session: if present, the session to use
    """
    session = kwargs.get('session') or get_session()
    query = session.query(*args)
    return query


def row2dict(row, srcflag=None):
    d = copy.copy(row.__dict__)
    for col in ['_sa_instance_state', 'sources']:
        if col in d:
            del d[col]
    if srcflag is None:
        d['sources'] = map(lambda x: row2dict(x, True), row.sources)
    return d
