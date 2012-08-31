from sqlalchemy import *
from ceilometer.openstack.common import timeutils

meta = MetaData()

meter = Table(
    'meter', meta,
    Column('id', Integer, primary_key=True),
    Column('counter_name', String(255)),
    Column('source', String(255)),
    Column('user_id', String(255)),
    Column('project_id', String(255)),
    Column('resource_id', String(255)),
    Column('resource_metadata', String(1000)),
    Column('counter_type', String(255)),
    Column('counter_volume', Integer),
    Column('counter_duration', Integer),
    Column('timestamp', DateTime(timezone=False)),
    Column('message_signature', String(255)),
    Column('message_id', String(255))
)

project = Table(
    'project', meta,
    Column('id', Integer, primary_key=True),
    Column('project_source_id', Integer)
)

resource = Table(
    'resource', meta,
    Column('id', Integer, primary_key=True),
    Column('resource_metadata', String(1000)),
    Column('meter', String(1000)),
    Column('project_id', Integer),
    Column('received_timestamp', DateTime(timezone=False)),
    Column('source', String(255)),
    Column('timestamp', DateTime(timezone=False)),
    Column('user_id', Integer)
)

user = Table(
    'user', meta,
    Column('id', Integer, primary_key=True),
    Column('user_source_id', Integer)
)

user_source = Table(
    'user_source', meta,
    Column('id', Integer, primary_key=True),
    Column('user_id', Integer),
    Column('name', String(255))
)

project_source = Table(
    'project_source', meta,
    Column('id', Integer, primary_key=True),
    Column('project_id', Integer),
    Column('name', String(255))
)


tables = [meter, project, resource, user, user_source, project_source]


def upgrade(migrate_engine):
    meta.bind = migrate_engine
    for i in tables:
        i.create()


def downgrade(migrate_engine):
    meta.bind = migrate_engine
    for i in tables:
        i.drop()
