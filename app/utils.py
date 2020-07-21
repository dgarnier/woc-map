import io
import csv
import re
from flask import send_file


def cvsfileify(dict_list, keys, filename):

    output = io.StringIO()
    writer = csv.DictWriter(output, keys,
                            extrasaction='ignore', dialect=csv.excel)
    writer.writeheader()
    for d in dict_list:
        writer.writerow(d)
    csv_string = output.getvalue()
    mem = io.BytesIO(csv_string.encode('utf-8'))
    return send_file(mem, as_attachment=True,
                     attachment_filename=filename,
                     mimetype='text/csv'
                     )


def hashtags(line):
    if not line:
        line = ""
    tags = re.split('[ :!.,\'"&\\?\t\n]', line.lower())
    return set([i[1:] for i in tags if i.startswith("#")])
