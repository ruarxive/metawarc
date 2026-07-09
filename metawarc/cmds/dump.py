import os
import csv

from warcio import ArchiveIterator
from warcio.utils import BUFF_SIZE

from ..constants import MIME_EXT_MAP
from ..dbutil import build_record_filter, connect, list_wf_ids, records_table_path, require_db

READ_SIZE = BUFF_SIZE * 4


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

    def listfiles(self, warcfileids: str = None, dbfile: str = 'warcindex.db', mimes: str = None,
                  exts: str = None, query: str = None, start: int = 0, limit: int = 1000,
                  output: str = None, silent: bool = False):
        """Lists files in WARC file"""
        from rich.table import Table
        from rich import print

        try:
            require_db(dbfile)
        except FileNotFoundError:
            print('Plese generate %s database with "metawarc index <filename.warc> command"' % dbfile)
            return

        con = connect(dbfile)
        try:
            ids = list_wf_ids(con, warcfileids)
            headers = ['offset', 'url', 'length', 'content_type', 'ext', 'warc_id']
            prep_headers = ','.join(['"' + sub + '"' for sub in headers])
            outdata = []

            for wf_id in ids:
                recfilepath = records_table_path(con, wf_id)
                if recfilepath is None:
                    if not silent:
                        print(f'Records table for {wf_id} not found. Please reindex')
                    continue
                if not os.path.exists(recfilepath):
                    if not silent:
                        print(f'Records table file {recfilepath} for {wf_id} not found. Please reindex or ignore')
                    continue

                try:
                    where = build_record_filter(mimes=mimes, exts=exts, query=query)
                except ValueError as exc:
                    if not silent:
                        print(str(exc))
                    return

                if where:
                    s = f"select {prep_headers} from '{recfilepath}'{where}"
                    results = con.sql(s).fetchall()
                else:
                    s = f"select {prep_headers} from '{recfilepath}' offset {start} limit {limit}"
                    results = con.sql(s).fetchall()

                for record in results:
                    outdata.append(record)

            if output is None:
                title = 'URL/file list'
                reptable = Table(title=title)
                for key in headers:
                    reptable.add_column(key, justify="left", style="cyan", no_wrap=False)
                for row in outdata:
                    reptable.add_row(*map(str, row))
                print(reptable)
            else:
                with open(output, 'w', encoding='utf8', newline='') as outf:
                    writer = csv.writer(outf)
                    writer.writerow(headers)
                    writer.writerows(outdata)
        finally:
            con.close()

    def dump(self, warcfiles: str = None, dbfile='warcindex.db', mimes: str = None, exts: str = None,
             query: str = None, start: int = 0, limit: int = 1000, output: str = None, silent: bool = False):
        """Dump WARC file contents"""
        from rich import print

        try:
            require_db(dbfile)
        except FileNotFoundError:
            print('Plese generate %s database with "metawarc index <filename.warc> command"' % dbfile)
            return

        con = connect(dbfile)
        try:
            if warcfiles is None:
                ids = list_wf_ids(con)
            else:
                ids = [item.strip() for item in warcfiles.split(',') if item.strip()]

            headers = ['offset', 'filename', 'url', 'length', 'content_type', 'ext', 'status_code', 'warc_id', 'source']
            prep_headers = ','.join(['"' + sub + '"' for sub in headers])
            outdata = []

            for wf_id in ids:
                recfilepath = records_table_path(con, wf_id)
                if recfilepath is None:
                    if not silent:
                        print(f'Records table for {wf_id} not found. Please reindex')
                    continue
                if not os.path.exists(recfilepath):
                    if not silent:
                        print(f'Records table file {recfilepath} for {wf_id} not found. Please reindex or ignore')
                    continue

                try:
                    where = build_record_filter(mimes=mimes, exts=exts, query=query)
                except ValueError as exc:
                    if not silent:
                        print(str(exc))
                    return

                if where:
                    s = f"select {prep_headers} from '{recfilepath}'{where}"
                    results = con.sql(s).fetchall()
                else:
                    s = f"select {prep_headers} from '{recfilepath}' offset {start} limit {limit}"
                    results = con.sql(s).fetchall()

                for record in results:
                    outdata.append(record)

            if not outdata:
                if not silent:
                    print('No records matched the query')
                return

            os.makedirs(output, exist_ok=True)
            opened_files = {}
            final_data = []
            for record in outdata:
                if record[8] in opened_files:
                    fileobj = opened_files[record[8]]
                else:
                    fileobj = open(record[8], "rb")
                    opened_files[record[8]] = fileobj
                fileobj.seek(record[0])
                it = iter(ArchiveIterator(fileobj))
                warcrec = next(it)
                filename = record[7] + '.' + get_ext_from_content_type(record[4])
                final_data.append(record)
                with open(os.path.join(output, filename), 'wb') as out_raw:
                    stream = warcrec.content_stream()
                    buf = stream.read(READ_SIZE)
                    while buf:
                        out_raw.write(buf)
                        buf = stream.read(READ_SIZE)
                print('Wrote %s, url %s' % (filename, record[2]))

            output_file = os.path.join(output, 'records.csv')
            with open(output_file, 'w', encoding='utf8', newline='') as outf:
                writer = csv.writer(outf)
                writer.writerow(headers)
                writer.writerows(final_data)
        finally:
            con.close()

    def get_file(self, fileid: str = None, dbfile='warcindex.db', output: str = None, silent: bool = False):
        """Dump WARC file contents"""
        from rich import print

        try:
            require_db(dbfile)
        except FileNotFoundError:
            print('Plese generate %s database with "metawarc index <filename.warc> command"' % dbfile)
            return

        con = connect(dbfile)
        try:
            ids = list_wf_ids(con)
            headers = ['offset', 'filename', 'url', 'length', 'content_type', 'ext', 'status_code', 'warc_id', 'source']
            prep_headers = ','.join(['"' + sub + '"' for sub in headers])
            found = False
            safe_id = fileid.replace("'", "''")

            for wf_id in ids:
                recfilepath = records_table_path(con, wf_id)
                if recfilepath is None or not os.path.exists(recfilepath):
                    continue
                s = (
                    f"select {prep_headers} from '{recfilepath}' "
                    f"where warc_id = '{safe_id}' or url = '{safe_id}'"
                )
                results = con.sql(s).fetchall()
                if not results:
                    continue

                found = True
                record = results[0]
                with open(record[8], "rb") as fileobj:
                    fileobj.seek(record[0])
                    it = iter(ArchiveIterator(fileobj))
                    warcrec = next(it)
                    out_name = record[7] + '.' + get_ext_from_content_type(record[4])
                    if output is None or output == 'None':
                        output_path = out_name
                    else:
                        output_path = output
                    with open(output_path, 'wb') as out_raw:
                        stream = warcrec.content_stream()
                        buf = stream.read(READ_SIZE)
                        while buf:
                            out_raw.write(buf)
                            buf = stream.read(READ_SIZE)
                if not silent:
                    print('Wrote %s, url %s' % (out_name, record[2]))
                break

            if not found and not silent:
                print('File not found')
        finally:
            con.close()
