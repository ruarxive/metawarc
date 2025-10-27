from sqlalchemy import Integer, String, Column, ForeignKey, DateTime, JSON
from sqlalchemy.orm import declarative_base
from sqlalchemy.orm import relationship

Base = declarative_base()

class Record(Base):
     __tablename__ = "record"

     id = Column(Integer, primary_key=True)
     warc_id = Column(String(50))
     rec_date = DateTime()
     content_type = Column(String(40))
     status_code = Column(Integer)
     url = Column(String)
     filename = Column(String)
     ext = Column(String(10))
     source = Column(String)
     offset = Column(Integer)
     length = Column(Integer)
     content_length = Column(Integer)
     headers = Column(JSON)
     

     def __repr__(self):
         return f"Record(id={self.id!r}, offset={self.offset!r}, length={self.length!r})"