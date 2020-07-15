import io
import csv
from flask import send_file


def cvsfileify(dict_list, filename):

    output = io.StringIO()
    keys = list(dict_list[0])
    keys.remove('resource_state')
    writer = csv.DictWriter(output, keys,
                            extrasaction='ignore', dialect=csv.excel)
    writer.writeheader()
    writer.writerows(dict_list)
    csv_string = output.getvalue()
    mem = io.BytesIO(csv_string.encode('utf-8'))
    return send_file(
        mem,
        as_attachment=True,
        attachment_filename=filename,
        mimetype='text/csv'
    )
