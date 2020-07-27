import requests
import time
# import os

with requests.Session() as s:
    for i in range(1800, 0, -1):
        r = s.get(f'http://app.wheelsofchange.us/admin/check_event/{i}',
                  )
        answer = r.text
        print(f'{i}, {answer[:50]}')
        time.sleep(.25)


'''
for i in range(1655, 0, -1):
    url = f'http://localhost:5000/admin/check_event/{i}'
    r = os.popen(f'curl -s {url}').read()
    print(f'{i}, {r[:50]}')
    time.sleep(1)
'''
