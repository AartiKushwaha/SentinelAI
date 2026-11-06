from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker


class Store:
    def __init__(self, url: str):
        self.engine = create_engine(url, pool_pre_ping=True, hide_parameters=True)
        if self.engine.dialect.name == "sqlite":

            @event.listens_for(self.engine, "connect")
            def foreign_keys(conn, _):
                conn.execute("PRAGMA foreign_keys=ON")

        self.session = sessionmaker(self.engine, expire_on_commit=False)
