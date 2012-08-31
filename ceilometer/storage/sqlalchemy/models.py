# vim: tabstop=4 shiftwidth=4 softtabstop=4

# Copyright (c) 2011 X.commerce, a business unit of eBay Inc.
# Copyright 2010 United States Government as represented by the
# Administrator of the National Aeronautics and Space Administration.
# Copyright 2011 Piston Cloud Computing, Inc.
# All Rights Reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.
"""
SQLAlchemy models for nova data.
"""

from sqlalchemy import Column, Integer, BigInteger, String, schema
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import ForeignKey, DateTime, Boolean, Text, Float
from sqlalchemy.orm import relationship, backref, object_mapper

from ceilometer.storage.sqlalchemy.session import get_session
from ceilometer.openstack.common import timeutils


BASE = declarative_base()


class CeilometerBase(object):
    """Base class for Ceilometer Models."""
    __table_args__ = {'mysql_engine': 'InnoDB'}
    __table_initialized__ = False

    def save(self, session=None):
        """Save this object."""
        if not session:
            session = get_session()
        session.add(self)
        try:
            session.flush()
        except Exception:
            raise

    def delete(self, session=None):
        """Delete this object."""
        self.save(session=session)

    def __setitem__(self, key, value):
        setattr(self, key, value)

    def __getitem__(self, key):
        return getattr(self, key)

    def get(self, key, default=None):
        return getattr(self, key, default)

    def __iter__(self):
        columns = dict(object_mapper(self).columns).keys()
        # NOTE(russellb): Allow models to specify other keys that can be looked
        # up, beyond the actual db columns.  An example would be the 'name'
        # property for an Instance.
        if hasattr(self, '_extra_keys'):
            columns.extend(self._extra_keys())
        self._i = iter(columns)
        return self

    def next(self):
        n = self._i.next()
        return n, getattr(self, n)

    def update(self, values):
        """Make the model object behave like a dict"""
        for k, v in values.iteritems():
            setattr(self, k, v)

    def iteritems(self):
        """Make the model object behave like a dict.

        Includes attributes from joins."""
        local = dict(self)
        joined = dict([(k, v) for k, v in self.__dict__.iteritems()
                      if not k[0] == '_'])
        local.update(joined)
        return local.iteritems()


class Meter(BASE, CeilometerBase):
    """Metering data"""

    __tablename__ = 'meter'
    id = Column(Integer, primary_key=True)
    counter_name = Column(String(255))
    source = Column(String(255))
    user_id = Column(Integer, ForeignKey('user.id'))
    project_id = Column(Integer, ForeignKey('project.id'))
    resource_id = Column(Integer, ForeignKey('resource.id'))
    resource_metadata = Column(String(1000))
    counter_type = Column(String(255))
    counter_volume = Column(Integer)
    counter_duration = Column(Integer)
    timestamp = Column(DateTime, default=timeutils.utcnow())
    message_signature = Column(String(255))
    message_id = Column(String(255))


class User(BASE, CeilometerBase):
    __tablename__ = 'user'
    id = Column(Integer, primary_key=True)
    sources = relationship("UserSource")
    resources = relationship("Resource", backref='user')
    meters = relationship("Meter", backref='user')


class UserSource(BASE, CeilometerBase):
    __tablename__ = 'user_source'
    id = Column(Integer, primary_key=True)
    name = Column(String(255))
    user_id = Column(Integer, ForeignKey('user.id'))


class Project(BASE, CeilometerBase):
    __tablename__ = 'project'
    id = Column(Integer, primary_key=True)
    sources = relationship("ProjectSource")
    resources = relationship("Resource", backref='project')
    meters = relationship("Meter", backref='project')


class ProjectSource(BASE, CeilometerBase):
    __tablename__ = 'project_source'
    id = Column(Integer, primary_key=True)
    name = Column(String(255))
    project_id = Column(Integer, ForeignKey('project.id'))


class Resource(BASE, CeilometerBase):
    __tablename__ = 'resource'
    id = Column(Integer, primary_key=True)
    source = Column(String(255))
    meter = Column(String(1000))
    timestamp = Column(DateTime)
    resource_metadata = Column(String(1000))
    received_timestamp = Column(DateTime, default=timeutils.utcnow())
    user_id = Column(Integer, ForeignKey('user.id'))
    project_id = Column(Integer, ForeignKey('project.id'))
    meters = relationship("Meter", backref='resource')
