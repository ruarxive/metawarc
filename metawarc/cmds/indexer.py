import os
import sys
from datetime import datetime
import logging
import json
import io
from warcio import ArchiveIterator
from warcio.utils import BUFF_SIZE
import duckdb
import pyarrow as pa
import uuid
from io import BytesIO
import glob
import tqdm

#from lxml import etree, html
from bs4 import BeautifulSoup,SoupStrainer

from ..constants import SUPPORTED_FILE_TYPES, IMAGE_FILES, MS_XML_FILES, MIME_SHORT_MAP, ADOBE_FILES, MS_OLE_FILES, HTML_FILES, MIMES_EXT_TYPE_BY_GROUP

from hachoir.metadata import extractMetadata
from hachoir.parser import createParser
from pdfminer.pdfdocument import PDFDocument

# from hachoir.core.i18n import initLocale
from pdfminer.pdfparser import PDFParser

from .extractor import processWarcRecord


BUFF_SIZE = 16384
READ_SIZE = BUFF_SIZE * 4

THRESHOLD = 250

def bufcount(filename):
    """Count number of lines"""
    f = open(filename)                  
    lines = 0
    buf_size = 1024 * 1024
    read_f = f.read # loop optimization

    buf = read_f(buf_size)
    while buf:
        lines += buf.count('\n')
        buf = read_f(buf_size)
    f.close() 
    return lines

def cdx_size_counter(filename):
    return bufcount(filename) - 1


DEFAULT_LINK_ATTRS = ['href', 'class', 'id']


ALL_TABLES = ['records', 'headers','links', 'oledocs', 'ooxmldocs', 'images', 'pdfs']

def dump_table(filename:str, table:list, con=None):    
    if len(table) == 0: return
    table_records = pa.Table.from_pylist(table)    
    query = f"COPY (SELECT * FROM table_records) to '{filename}' (COMPRESSION zstd, COMPRESSION_LEVEL 9)"
    if con is not None:
        con.sql(query)
    else:
        duckdb.sql(query)


class Indexer:
    """Indexes WARC file metadata"""

    def __init__(self):
        pass

    def index_records(self, fromfiles:list, tofile:str='warcindex.db', tables:list=['records', 'headers'], rescan:bool=False, silent:bool=False):
        """Generates DuckDB database and parquet files as WARC index"""
        from rich.progress import track
        from rich import print
        
        real_tables = ALL_TABLES.copy() if tables is None or 'all' in tables else tables
        
        con = duckdb.connect(tofile)
        list_files = []
        list_tables = []
        glob_tables = [x[0] for x in con.sql('show tables').fetchall()]

        for fromfile in fromfiles:
            file_record = {'id' : uuid.uuid4().hex, 'fullpath' : fromfile, 'filename' : os.path.basename(fromfile), 'filesize' : os.path.getsize(fromfile)}
            logging.debug("Indexing %s" % fromfile)
            resp = open(fromfile, "rb")  
            file_basename = os.path.basename(fromfile).lower()
            if file_basename[-5:] == '.warc': 
                file_basename - file_basename[0:-5]
            elif file_basename[-8:] == '.warc.gz': 
                file_basename = file_basename[0:-8]

            table_filename = 'data/' + file_record['id'] + f'_records.parquet'
            if os.path.exists(table_filename):
                if not rescan:
                    if not silent:
                        print('Fole {table_filename} already exists and rescan option not set. Skipping')
                        continue
                else:
                    if not silent:
                        print('Fole {table_filename} already exists but rescan option set. Processing')                

            iterator = ArchiveIterator(resp)
                            
            cdx_filename = fromfile.rsplit('.', 2)[0] + '.cdx'
            records_num = -1
            if os.path.exists(cdx_filename):
                records_num = cdx_size_counter(cdx_filename)
                if not silent:
                    print('CDX file found. Estimated number of WARC records %d' % (records_num))
            else:
                if not silent:
                    print("No CDX file. Can't measure progress")
            n = 0 
            list_records = []
            list_headers = []

            it = iterator if silent else tqdm.tqdm(iterator, desc='Iterate records', total=records_num*2)
            for record in it:
                if record.rec_type != "response": continue

                n += 1      
#                if not silent:
#                    if records_> 0:
#                        if n % THRESHOLD == 0: print('Processed %d (%0.2f%%) records' % (n, n*100.0 / records_num))            
#                    else:
#                        if n % THRESHOLD == 0: print('Processed %d records' % (n))
                if record.http_headers is not None:
                    dbrec = {}
                    dbrec['warc_id'] = record.rec_headers["WARC-Record-ID"].rsplit(':', 1)[-1].strip('>')
                    dbrec['url'] = record.rec_headers["WARC-Target-URI"]
                    content_type = record.http_headers["content-type"] if 'content-type' in record.http_headers else None
                    dbrec['content_type'] = content_type
                    charset = None
                    content_type_no_ch = content_type
                    if content_type is not None and content_type.find(';') > -1:
                        content_type_no_ch, charset = content_type.split(';', 1)
                        content_type_no_ch = content_type_no_ch.strip().lower()
                        if charset.find('=') > -1:
                            charset = charset.split('=', 1)[-1].lower().strip()


                    filename = dbrec['url'].rsplit("?", 1)[0].rsplit("/", 1)[-1].lower()
                    ext = filename.rsplit(".", 1)[-1]

                    dbrec['c_type'] = content_type_no_ch
                    dbrec['c_type_charset'] = charset
                    dbrec['offset'] = it.iterable.get_record_offset()
                    dbrec['length'] = it.iterable.get_record_length()
                    warc_date  = record.rec_headers["WARC-Date"]
                    dbrec['rec_date'] = datetime.strptime(warc_date, "%Y-%m-%dT%H:%M:%S%z")
                    dbrec['content_length'] = int(record.rec_headers["Content-Length"])
                    dbrec['status_code'] = int(record.http_headers.statusline.split(' ', 1)[0])                
                    dbrec['source'] = fromfile
                    dbrec['filename'] = dbrec['url'].rsplit("?", 1)[0].rsplit("/", 1)[-1].lower() 
                    dbrec['ext'] = dbrec['filename'].rsplit(".", 1)[-1] if dbrec['filename'].find(".") > -1 else ""
                    properties = []
                    if 'records' in real_tables:
                        list_records.append(dbrec)
                    if 'headers' in real_tables:
                        for key, value in record.http_headers.headers:
                            properties.append({'key' : key, 'value' : value, 'warc_id' : dbrec['warc_id'], 'source': fromfile})
                        list_headers.extend(properties)        

            resp.close()

            os.makedirs('data', exist_ok=True)
            if 'records' in real_tables:               
                if len(list_records) > 0: 
                    dump_table(filename=table_filename, table=list_records, con=con)
                    list_tables.append({'wf_id' : file_record['id'], 'wf_filename' : fromfile, 'path' :table_filename, 'type' : 'records', 'num_items' : len(list_records)})
                    if not silent:
                        print('- saved %s with %s' % (table_filename, 'records'))
            if 'headers' in real_tables:
                if len(list_headers) > 0:
                    dump_table(filename='data/' + file_record['id'] + '_headers.parquet', table=list_headers, con=con)
                    list_tables.append({'wf_id' : file_record['id'], 'wf_filename' : fromfile, 'path' :'data/' + file_record['id'] + '_headers.parquet', 'type' : 'headers', 'num_items' : len(list_headers)})
                    if not silent:
                        print('- saved %s with %s' % ('data/' + file_record['id'] + '_headers.parquet', 'headers'))
            file_record['num_records'] = len(list_records)
            list_files.append(file_record)

        if len(list_files) == 0:
            return
        
        pa_files = pa.Table.from_pylist(list_files)
        if 'files' not in glob_tables:
            con.sql("CREATE TABLE files (id VARCHAR, fullpath VARCHAR, filename VARCHAR PRIMARY KEY,filesize BIGINT, num_records INTEGER);")
            con.sql("INSERT OR REPLACE INTO files SELECT * FROM pa_files")
        else:
            con.sql("INSERT OR REPLACE INTO files SELECT * FROM pa_files")        
        pa_tables = pa.Table.from_pylist(list_tables)
        if 'tables' not in glob_tables:
            con.sql("CREATE TABLE tables (wf_id VARCHAR, wf_filename VARCHAR, path VARCHAR PRIMARY KEY, type VARCHAR, num_items INTEGER);")
            con.sql("INSERT OR REPLACE INTO tables SELECT * FROM pa_tables")
        else:
            con.sql("INSERT OR REPLACE INTO tables SELECT * FROM pa_tables")        

       
    def index_by_table_type(self, fromfiles:list=None, tofile:str='warcindex.db', table_type:str='links', rescan:bool=False, silent:bool=True):
        """Generates parquet file with content type"""
        con = duckdb.connect(tofile)

        list_tables = []

        if fromfiles  is None:
            files = [item['filename'] for item in con.sql('select filename from files;').df().to_dict('records')]
        else:
            files = fromfiles

        content_group = 'html' if table_type == 'links' else table_type
        mimetypes = MIMES_EXT_TYPE_BY_GROUP[content_group]['mimes']
        filetypes = MIMES_EXT_TYPE_BY_GROUP[content_group]['exts']

        for filename in files:
            warc_file_rec = con.sql(f"select id from files where fullpath = '{filename}';").fetchone()
            wf_id = warc_file_rec[0]
            rectables = con.sql(f"select * from tables where type = 'records' and wf_id = \'{wf_id}\';").df().to_dict('records')
            if len(rectables) == 0:
                if not silent:
                    print(f'Records table for {filename} not found. Please reindex')
                continue
            else:
                recfilepath = rectables[0]['path']
                if not os.path.exists(recfilepath):
                    if not silent:
                        print(f'Records file for {filename} not found')
                    continue
            file_basename = os.path.basename(filename).lower()
            if file_basename[-5:] == '.warc': 
                file_basename - file_basename[0:-5]
            elif file_basename[-8:] == '.warc.gz': 
                file_basename = file_basename[0:-8]
            list_items = []            

            table_filename = 'data/' + wf_id + f'_{table_type}.parquet'
            if os.path.exists(table_filename):
                if not rescan:
                    if not silent:
                        print('File {table_filename} already exists and rescan option not set. Skipping')
                        continue
                else:
                    if not silent:
                        print('File {table_filename} already exists but rescan option set. Processing')

            warcf = open(filename, "rb")  
            content_types = ','.join(["'" + sub + "'" for sub in mimetypes])
            query = f"select url, c_type, ext, \"offset\", warc_id from '{recfilepath}' where c_type IN ({content_types})"

            records = con.sql(query).df().to_dict('records')
            it = records if silent else tqdm.tqdm(records, desc=f'Processing {table_type} records from {filename}', total=len(records))
            for item in it:
                warcf.seek(int(item['offset']))
                ait = iter(ArchiveIterator(warcf))
                dbrec = next(ait)
                if table_type == 'links':
                    out_raw = BytesIO()
                    buf = dbrec.content_stream().read(READ_SIZE)
                    while buf:
                        out_raw.write(buf)
                        buf = dbrec.content_stream().read(READ_SIZE)
                    try:
                        only_a_tags = SoupStrainer("a")
                        root = BeautifulSoup(out_raw.getvalue(), "lxml", parse_only=only_a_tags)
                        if root is not None:
                            for l in root:
                                lrec = {'warc_id' : item['warc_id'], 'wf_id' : wf_id, 'wf_filename' : filename, 'url' : item['url'], '_text' : l.text}
                                for att in DEFAULT_LINK_ATTRS:
                                    if att in l.attrs.keys(): 
                                        lrec[att] = l.attrs[att]
                                    else:
                                        lrec[att] = None
                                list_items.append(lrec)
                    except KeyboardInterrupt:
                        pass
                    except ValueError:
                        logging.info('Error parsing links from %s' % (item['url']))                    
                        pass                    
                else:                    
                    list_items.append(processWarcRecord(dbrec, item['url'], filename, mime=item['c_type'], source=filename))

            if len(list_items) > 0:
                dump_table(filename=table_filename, table=list_items, con=con)
                list_tables.append({'wf_id' : wf_id, 'wf_filename' : filename, 'path' :table_filename, 'type' : table_type, 'num_items' : len(list_items)})
                if not silent:
                    print(f'- saved {table_filename} with {table_type}')

        if len(list_tables) == 0:
            return

        if not silent:
            print('Writing final tables metadata to db file')
        pa_tables = pa.Table.from_pylist(list_tables)
        con.sql("INSERT OR REPLACE INTO tables SELECT * FROM pa_tables")      


    def dump_metadata(self, fromfiles:list=None, tofile:str='warcindex.db', metadata_type:str='ooxmldocs', output:str=None, silent:bool=True):
        """Dumps metadata"""
        con = duckdb.connect(tofile)

        list_tables = []

        if fromfiles is None:
            files = [item['filename'] for item in con.sql('select filename from files;').df().to_dict('records')]
        else:
            files = fromfiles

        for filename in files:
            mtables = con.sql(f"select * from tables where type = '{metadata_type}' and warcfile = \'{filename}\';").df().to_dict('records')
            if len(mtables) == 0:
                if not silent:
                    print(f'Metadata table for {filename} with metadata {metadata_type} not found. Please reindex WARC file')
                continue
            else:
                mfilepath = mtables[0]['path']

            if output is None:
                query = f"select * from '{mfilepath}'"
                records = con.sql(query).df().to_dict('records')
                for row in records:
                    print(json.dumps(row))
            else:
                f = open(output, 'a', encoding='utf8')
                query = f"select * from '{mfilepath}'"
                records = con.sql(query).df().to_dict('records')
                for row in records:
                    f.write(json.dumps(row) + '\n')
                f.close()
                if not silent: 
                    print(f'Writing final {metadata_type} for file {filename} metadata to {output}')

    def calc_stats(self, dbfile='warcindex.db', mode='mime'):
        from rich.table import Table
        from rich import print
        if not os.path.exists(dbfile):
            print(f'Plese generate {dbfile} database with "metawarc index <filename.warc> command"')
            return
        con = duckdb.connect(dbfile)  
       
        if mode == 'mimes':
             results = con.sql("select c_type, SUM(content_length), COUNT(warc_Id) from 'data/*_records.parquet' group by c_type ")
             title = 'Group by mime type'
             headers = ('mime', 'size', 'size share', 'count')
        elif mode == 'exts':
             results = con.sql("select ext, SUM(content_length), COUNT(warc_Id) from 'data/*_records.parquet' group by ext ")
             title = 'Group by file extension'
             headers = ('extension', 'size', 'size share', 'count')
        else:
            print('Plese select mode: mimes or exts')
            return 
  
        reptable = Table(title=title)
        reptable.add_column(headers[0], justify="left", style="magenta")
        for key in headers[1:-1]:
            reptable.add_column(key, justify="left", style="cyan", no_wrap=True)
        reptable.add_column(headers[-1], justify="right", style="cyan")
        total_size = 0
        for row in results.fetchall():
            total_size += row[1]
        for row in results.fetchall():
            result = [row[0], row[1], '%0.2f%%' % (row[1] *100.0 / total_size), row[2]]
            reptable.add_row(*map(str, result))
        print(reptable)

if __name__ == "__main__":
    indexer = Indexer()
    indexer.index_records(sys.argv[1])

