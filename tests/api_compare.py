#!env python3
import requests
import json
import sys
from pprint import pprint

def print_compare(old, new):
    old_standings = old['standings']
    new_standings = new['standings']

    i = 0
    while i < len(old_standings):
        print("- %s" % i)
        if old_standings[i] != new_standings[i]:
            print("MISMATCH")
            print(old_standings[i])
            print("---")
            print(new_standings[i])
        i += 1

new_base = "http://localhost:5000/api/v1"
old_base = "http://localhost:5900/api/v1"

url = f"{new_base}/tournaments"
res = requests.get(url)
print(res.status_code)
# print(res.text)
body = json.loads(res.text)
# print(tournaments)

for t in body['tournaments']:
    t_url = f"{url}/{t['tid']}"
    body = requests.get(t_url).json()
    t_info = body['tournament']
    print(t_info)
    pods = t_info['pods']
    if pods and len(pods) > 0:
        for pod in t_info['pods']:
            pod_url = f"{t_url}/standings?pod={pod}"
            print(pod_url)
            new_pod_standings = requests.get(pod_url).json()

            # pprint(new_pod_standings)
            old_pod_url = f"{old_base}/tournaments/{t['tid']}/standings?pod={pod}"
            old_pod_standings = requests.get(old_pod_url).json()

            # pprint(old_pod_standings)
            if not (old_pod_standings['standings'] == new_pod_standings['standings']):
                pprint(new_pod_standings)
                print("=====================================================================================")
                pprint(old_pod_standings)
                print("Standings mismatch, %s" % pod_url)
                sys.exit(1)
    else:
        continue
        for div in t_info['divisions']:
            print("DIVISIONAL STANDINGS")
            pod_url = f"{t_url}/standings?div={div}"
            print(pod_url)
            new_pod_standings = requests.get(pod_url).json()

            # pprint(new_pod_standings)
            old_pod_url = f"{old_base}/tournaments/{t['tid']}/standings?div={div}"
            old_pod_standings = requests.get(old_pod_url).json()

            # pprint(old_pod_standings)
            if not (old_pod_standings['standings'] == new_pod_standings['standings']):
                pprint(new_pod_standings)
                print("=====================================================================================")
                pprint(old_pod_standings)
                print("Standings mismatch, %s" % pod_url)
                print_compare(old_pod_standings, new_pod_standings)
                sys.exit(1)
