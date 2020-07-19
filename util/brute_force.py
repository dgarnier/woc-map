import requests
import time
import os

'''
headers = {
    'Connection': 'close'
}
with requests.Session() as s:
    for i in range(1670, 0, -1):
        r = s.get(f'http://localhost:5000/admin/check_event/{i}',
                    headers=headers )
        answer = r.text
        print(f'{i}, {answer[:50]}')
    # requests.session().close()
        time.sleep(1)
'''

for i in range(1655, 0, -1):
    url = f'http://localhost:5000/admin/check_event/{i}'
    r = os.popen(f'curl -s {url}').read()
    print(f'{i}, {r[:50]}')
    time.sleep(1)
