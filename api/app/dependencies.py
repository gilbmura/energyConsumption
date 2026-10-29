import pymysql
from fastapi import Request

from api.app.repositories.mongo_repository import MongoRepository
from api.app.repositories.mysql_repository import MySQLRepository


def get_mysql_repository(request: Request):
    settings = request.app.state.settings
    connection = pymysql.connect(
        host=settings.mysql_host,
        port=settings.mysql_port,
        user=settings.mysql_user,
        password=settings.mysql_password,
        database=settings.mysql_database,
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=False,
        connect_timeout=5,
        read_timeout=10,
        write_timeout=10,
    )
    try:
        yield MySQLRepository(connection, settings)
    finally:
        connection.close()


def get_mongo_repository(request: Request):
    settings = request.app.state.settings
    return MongoRepository(
        request.app.state.mongo_client[settings.mongo_database][settings.mongo_collection]
    )
