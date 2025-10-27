import os
import csv
from datetime import datetime
import logging
import json
import io
from warcio import ArchiveIterator
from warcio.utils import BUFF_SIZE
from ..constants import MIME_EXT_MAP

READ_SIZE = BUFF_SIZE * 4

import duckdb



def get_ext_from_content_type(content_type):
    """Returns base extension for content types"""
    if content_type is not None:
        content_type = content_type.split(';', 1)[0]
        if content_type in MIME_EXT_MAP.keys():
            return MIME_EXT_MAP[content_type]
    return 'unknown'

class Dumper:
    """Dumps data files from WARC file"""

    def __init__(self):
        pass

    def listfiles(self, warcfileids:str=None, dbfile:str='warcindex.db', mimes:list=None, exts:list=None, query:str=None, start:int=0, limit:int=1000, output:str=None, silent:bool=False):
        """Lists files in WARC file"""
        from rich.table import Table
        from rich import print

        con = duckdb.connect(dbfile)

        if not os.path.exists(dbfile):
            print('Plese generate %s database with "metawarc index <filename.warc> command"' % dbfile)
            return

        if warcfileids  is None:
            ids = [item['id'] for item in con.sql('select id from files;').df().to_dict('records')]
        else:
            ids = warcfilesids            

        headers = ['offset', 'url', 'length', 'content_type', 'ext', 'warc_id']
        prep_headers = ','.join(['"' + sub + '"' for sub in headers]) 
        results = None
        outdata = []

        for wf_id in ids:
            rectables = con.sql(f"select * from tables where type = 'records' and wf_id = \'{wf_id}\';").df().to_dict('records')
            if len(rectables) == 0:
                if not silent:
                    print(f'Records table for {wf_id} not found. Please reindex')
                continue
            else:
                recfilepath = rectables[0]['path']

            if not os.path.exists(recfilepath):
                if not silent:
                    print(f'Records table file {recfilepath} for {wf_id} not found. Please reindex or ignore')
                continue


            if mimes is not None:
                prep_mimes = ','.join(["'" + sub + "'" for sub in mimes.split(',')])
                s = f"select {prep_headers} from '{recfilepath}' where c_type in ({prep_mimes})"
    #            print('Query', s)
                results = con.sql(s).fetchall()
            elif exts is not None:
                prep_exts = ','.join(["'" + sub + "'" for sub in exts.split(',')])
                s = f"select {prep_headers} from '{recfilepath}' where ext in ({prep_exts})"
                #print('Query', s)
                results = con.sql(s).fetchall()
            elif query is not None:
                s = f"select {prep_headers} from '{recfilepath}' where {query}"            
                results = con.sql(s).fetchall()
            else:
                s = f"select {prep_headers} from '{recfilepath}' offset {start} limit {limit}"            
                results = con.sql(s).fetchall()
            if results is None:
                if not silent:
                    print('At least one parameter: query, exts or mimes should be provided')
                return 
            else:
                for record in results:
                    outdata.append(record)
        
        if output is None:
            title = 'URL/file list'
            reptable = Table(title=title)
#            reptable.add_column(headers[0], justify="left", style="magenta")
            for key in headers:#[1:-1]:
                reptable.add_column(key, justify="left", style="cyan", no_wrap=False)
#            reptable.add_column(headers[-1], justify="right", style="cyan")
            for row in outdata:
                reptable.add_row(*map(str, row))
            print(reptable)
        else:
            writer = csv.writer(open(output, 'w', encoding='utf8'))
            writer.writerow(headers)
            writer.writerows(outdata)

    def dump(self, warcfiles:str=None, dbfile='warcindex.db', mimes:str=None, exts:str=None, query:str=None, start:int=0, limit:int=1000, output:str=None, silent:bool=False):
        """Dump WARC file contents"""
        from rich.table import Table
        from rich import print
        if not os.path.exists(dbfile):
            print('Plese generate %s database with "metawarc index <filename.warc> command"' % dbfile)
            return


        con = duckdb.connect(dbfile)

        if warcfiles  is None:
            files = [item['filename'] for item in con.sql('select filename from files;').df().to_dict('records')]
        else:
            files = warcfiles            

        headers = ['offset', 'filename', 'url', 'length', 'content_type', 'ext', 'status_code', 'warc_id', 'source']
        prep_headers = ','.join(['"' + sub + '"' for sub in headers]) 
        results = None
        outdata = []

        for filename in files:
            rectables = con.sql(f"select * from tables where type = 'records' and warcfile = \'{filename}\';").df().to_dict('records')
            if len(rectables) == 0:
                if not silent:
                    print(f'Records table for {filename} not found. Please reindex')
                continue
            else:
                recfilepath = rectables[0]['path']

            if not os.path.exists(recfilepath):
                if not silent:
                    print(f'Records table file {recfilepath} for {filename} not found. Please reindex or ignore')
                continue

            if mimes is not None:
                prep_mimes = ','.join(["'" + sub + "'" for sub in mimes.split(',')])
                s = f"select {prep_headers} from '{recfilepath}' where c_type in ({prep_mimes})"
    #            print('Query', s)
                results = con.sql(s).fetchall()
            elif exts is not None:
                prep_exts = ','.join(["'" + sub + "'" for sub in exts.split(',')])
                s = f"select {prep_headers} from '{recfilepath}' where ext in ({prep_exts})"
                #print('Query', s)
                results = con.sql(s).fetchall()
            elif query is not None:
                s = f"select {prep_headers} from '{recfilepath}' where {query}"            
                results = con.sql(s).fetchall()
            else:
                s = f"select {prep_headers} from '{recfilepath}' offset {start} limit {limit}"            
                results = con.sql(s).fetchall()
            if results is None:
                if not silent:
                    print('At least one parameter: query, exts or mimes should be provided')
                return                 
            else:
                for record in results:
                    outdata.append(record)
        os.makedirs(output, exist_ok=True)
        opened_files = {}
        final_data = []
        for record in outdata:            
            if record[8] in opened_files.keys():
                fileobj = opened_files[record[8]]
            else:
                fileobj = open(record[8], "rb")
                opened_files[record[8]] = fileobj
            fileobj.seek(record[0])
            it = iter(ArchiveIterator(fileobj))
            warcrec = next(it)
            filename = record[7] + '.' + get_ext_from_content_type(record[4])
            final_data.append(record)            
            out_raw = open(os.path.join(output, filename), 'wb')
            stream = warcrec.content_stream()
            buf = stream.read(READ_SIZE)
            while buf:
                out_raw.write(buf)
                buf = stream.read(READ_SIZE)
            out_raw.close()
            print('Wrote %s, url %s' % (filename, record[2]))
        output_file = os.path.join(output, 'records.csv')
        writer = csv.writer(open(output_file, 'w', encoding='utf8'))
        writer.writerow(headers)
        writer.writerows(final_data)


    def get_file(self, fileid:str=None, dbfile='warcindex.db', output:str=None, silent:bool=False):
        """Dump WARC file contents"""
        from rich.table import Table
        from rich import print
        if not os.path.exists(dbfile):
            print('Plese generate %s database with "metawarc index <filename.warc> command"' % dbfile)
            return

        con = duckdb.connect(dbfile)


        files = [item['filename'] for item in con.sql('select filename from files;').df().to_dict('records')]

        headers = ['offset', 'filename', 'url', 'length', 'content_type', 'ext', 'status_code', 'warc_id', 'source']
        prep_headers = ','.join(['"' + sub + '"' for sub in headers]) 
        results = None
        outdata = []
        found = False

        for filename in files:
            rectables = con.sql(f"select * from tables where type = 'records' and warcfile = \'{filename}\';").df().to_dict('records')
            if len(rectables) == 0:
                if not silent:
                    print(f'Records table for {filename} not found. Please reindex')
                continue
            else:
                recfilepath = rectables[0]['path']
            if not os.path.exists(recfilepath):
                if not silent:
                    print(f'Records table file {recfilepath} for {filename} not found. Please reindex or ignore')
                continue
            s = f"select {prep_headers} from '{recfilepath}' where warc_id = \'{fileid}\' or url = \'{fileid}\'"
            results = con.sql(s).fetchall()
                
            if results is None or len(results) == 0:                
                continue
            else:
                found = True
                record = results[0]
                fileobj = open(record[8], "rb")
                fileobj.seek(record[0])
                it = iter(ArchiveIterator(fileobj))
                warcrec = next(it)
                filename = record[7] + '.' + get_ext_from_content_type(record[4])
                if output is None: output = filename
                out_raw = open(output, 'wb')
                stream = warcrec.content_stream()
                buf = stream.read(READ_SIZE)
                while buf:
                    out_raw.write(buf)
                    buf = stream.read(READ_SIZE)
                out_raw.close()
            if not silent:
                print('Wrote %s, url %s' % (filename, record[2]))
        if not found:
            if not silent:
                print('File not found')
