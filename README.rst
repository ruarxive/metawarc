metawarc: a command-line tool for metadata extraction from files from WARC (Web ARChive)
########################################################################################

metawarc (pronounced *me-ta-warc*) is a command line WARC files processing tools.
Its goal is to make CLI interaction with files inside WARC archives so easy as possible.
It provides a simple ``metawarc`` command that allows to extract metadata from images, documents and other files inside
WARC archives.


.. contents::

.. section-numbering::



Main features
=============

* Built-in WARC support
* Metadata extraction for a lot of file formats
* Low memory footprint
* Documentation
* Test coverage


File formats supported
======================

* MS Office OLE: .doc, .xls, .ppt
* MS Office XML: .docx, .xlsx, .pptx
* Adobe PDF: .pdf
* Images: .png, .jpg, .tiff, .jpeg, .jp2


Installation
============


Any OS
-------------

A universal installation method (that works on Windows, Mac OS X, Linux, …,
and always provides the latest version) is to use pip:


.. code-block:: bash

    # Make sure we have an up-to-date version of pip and setuptools:
    $ pip install --upgrade pip setuptools

    $ pip install --upgrade metawarc


(If ``pip`` installation fails for some reason, you can try
``easy_install metawarc`` as a fallback.)


Python version
--------------

Python version 3.6 or greater is required.

Usage
=====


Synopsis:

.. code-block:: bash

    $ metawarc [command] [flags]  inputfile


See also ``metawarc --help`` and ``metawarc [command] --help`` for help for each command.


Quickstart
==========

Index all WARC files in all subfolders

.. code-block:: bash

    $ metawarc index '*/*.warc.gz'

View file extensions statistics

.. code-block:: bash

    $ metawarc stats -m exts


List all PDF files

.. code-block:: bash

    $ metawarc list-files -e pdf


Dumps all records with size greater than 10M and file extension 'pdf' to 'bigpdf' directory

.. code-block:: bash

    $ metawarc dump -q "content_length > 10000000 and ext = 'pdf'" -o bigpdf




Commands
========

Index command
-------------
Generates 'warcindex.db' DuckDB database with WARC files meta and for each WARC file generated two Parquet files in 'data' directory, they inherit WARC file name and have suffix '_records' and "_headers".
All of them registered in 'warcindex.db' with tables as "files" and "tables". 

Analyzes 'armstat.am.warc.gz' and writes 'warcindex.db' with records and headers metadata.

.. code-block:: bash

    $ metawarc index armstat.am.warc.gz

Analyzes all WARC files in all subfolders and writes 'warcindex.db' with records and headers metadata.

.. code-block:: bash

    $ metawarc index '*/*.warc.gz'


Index content command
---------------------
Analyzes WARC files records and extracts relevant metadata / content for future reuse. Supported metadata types: ooxmldocs, oledocs, pdfs, images, links
Results saved to Parquet file in 'data' directory with suffix of the related metdata. For example '_images' for images.

Collects PDF files metadata from all WARC files

.. code-block:: bash

    $ metawarc index-content -t pdfs

Collects all links for selected WARC file (should be listed in 'warcindex.db' after index command run)

.. code-block:: bash

    $ metawarc index-content -i armstat.am.warc.gz -t links



Stats command
-------------
Returns total length and count of records by each mime or file extension.

Processes data in 'metawarc.db' and prints total length and count for each mime

.. code-block:: bash

    $ metawarc stats -m mimes

Processes data in 'metawarc.db' and prints total length and count for each file extension

.. code-block:: bash

    $ metawarc stats -m exts


Dump metadata command
---------------------
Dumps metadata from tables. Supported metadata types: pdfs, ooxmldocs, oledocs, images, links

Exports PDF files metadata and writes as 'pdfs_metadata.jsonl'

.. code-block:: bash

    $ metawarc dump-metadata -t pdfs -o pdfs_metadata.jsonl


List files command
------------------
Prints list of records with id, offset, length and url using 'metawarc.db'. Accepts list of mime types or list of file extensions or query as WHERE clause

Prints all records with mime type (content type) 'application/zip'

.. code-block:: bash

    $ metawarc list-files -m 'application/zip'

Prints all records with file extensions 'xls' and 'xlsx'

.. code-block:: bash

    $ metawarc list-files -e xls,xlsx

Prints all records with size greater than 10M and file extension 'pdf'

.. code-block:: bash

    $ metawarc list-files -q "content_length > 10000000 and ext = 'pdf'"


Dump command
------------
Dumps records payloads as files using 'metawarc.db' as WARC index. Accepts list of mime types or list of file extensions or query as WHERE clause.
Adds CSV file 'records.csv' to the output directory with basic data about each dumped record.

Dumps all records with mime type (content type) 'application/zip' to 'allzip' directory

.. code-block:: bash

    $ metawarc dump -m 'application/zip' -o allzip

Dumps all records with file extensions 'xls' and 'xlsx' to 'sheets' directory

.. code-block:: bash

    $ metawarc dump -e xls,xlsx -o sheets

Dumps all records with size greater than 10M and file extension 'pdf' to 'bigpdf' directory

.. code-block:: bash

    $ metawarc dump -q "content_length > 10000000 and ext = 'pdf'" -o bigpdf

