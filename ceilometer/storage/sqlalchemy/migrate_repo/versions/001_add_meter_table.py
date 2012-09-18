from sqlalchemy import *
from ceilometer.openstack.common import timeutils

meta = MetaData()

meter = Table(
    'meter', meta,
    Column('id', Integer, primary_key=True),
    Column('counter_name', String(255)),
    Column('user_id', String(255)),
    Column('project_id', String(255)),
    Column('resource_id', String(255)),
    Column('resource_metadata', String(5000)),
    Column('counter_type', String(255)),
    Column('counter_volume', Integer),
    Column('counter_duration', Integer),
    Column('timestamp', DateTime(timezone=False)),
    Column('message_signature', String(1000)),
    Column('message_id', String(1000))
)

resource = Table(
    'resource', meta,
    Column('id', String(255), primary_key=True),
    Column('resource_metadata', String(5000)),
    Column('project_id', String(255)),
    Column('received_timestamp', DateTime(timezone=False)),
    Column('timestamp', DateTime(timezone=False)),
    Column('user_id', String(255))
)

user = Table(
    'user', meta,
    Column('id', String(255), primary_key=True),
)

project = Table(
    'project', meta,
    Column('id', String(255), primary_key=True),
)

sourceassoc = Table(
    'sourceassoc', meta,
    Column('source_id', String(255)),
    Column('user_id', String(255)),
    Column('project_id', String(255)),
    Column('resource_id', String(255)),
    Column('meter_id', Integer)
)

source = Table(
    'source', meta,
    Column('id', String(255), primary_key=True),
    UniqueConstraint('id')
)


tables = [meter, project, resource, user, source, sourceassoc ]


def upgrade(migrate_engine):
    meta.bind = migrate_engine
    for i in tables:
        i.create()


def downgrade(migrate_engine):
    meta.bind = migrate_engine
    for i in tables:
        i.drop()
