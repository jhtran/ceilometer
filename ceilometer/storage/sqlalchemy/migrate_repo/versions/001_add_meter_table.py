from sqlalchemy import *
from ceilometer.openstack.common import timeutils

meta = MetaData()

meter = Table(
    'meter', meta,
    Column('id', Integer, primary_key=True),
    Column('counter_name', String(255)),
    Column('user_id', Integer),
    Column('project_id', Integer),
    Column('resource_id', Integer),
    Column('resource_metadata', String),
    Column('counter_type', String(255)),
    Column('counter_volume', Integer),
    Column('counter_duration', Integer),
    Column('timestamp', DateTime(timezone=False)),
    Column('message_signature', String),
    Column('message_id', String)
)

resource = Table(
    'resource', meta,
    Column('id', Integer, primary_key=True),
    Column('resource_metadata', String),
    Column('project_id', Integer),
    Column('received_timestamp', DateTime(timezone=False)),
    Column('timestamp', DateTime(timezone=False)),
    Column('user_id', Integer)
)

user = Table(
    'user', meta,
    Column('id', Integer, primary_key=True),
)

project = Table(
    'project', meta,
    Column('id', Integer, primary_key=True),
)

source = Table(
    'source', meta,
    Column('id', Integer, primary_key=True),
    Column('meter_id', Integer),
    Column('project_id', Integer),
    Column('resource_id', Integer),
    Column('user_id', Integer),
    Column('name', String(255))
)


tables = [meter, project, resource, user, source ]


def upgrade(migrate_engine):
    meta.bind = migrate_engine
    for i in tables:
        i.create()


def downgrade(migrate_engine):
    meta.bind = migrate_engine
    for i in tables:
        i.drop()
