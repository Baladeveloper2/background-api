import urllib.request, json

# Try login
token_data = json.dumps({'username': 'admin', 'password': 'admin123'}).encode()
try:
    req = urllib.request.Request('http://localhost:8000/auth/login', data=token_data, headers={'Content-Type': 'application/json'})
    resp = urllib.request.urlopen(req, timeout=5)
    token_resp = json.loads(resp.read())
    token = token_resp.get('access_token', '')
    print('Login OK, token:', token[:30], '...')
except Exception as e:
    print('Login ERROR:', e)
    # Try alternate login endpoint
    try:
        req = urllib.request.Request('http://localhost:8000/login', data=token_data, headers={'Content-Type': 'application/json'})
        resp = urllib.request.urlopen(req, timeout=5)
        token_resp = json.loads(resp.read())
        token = token_resp.get('access_token', '')
        print('Alt-login OK, token:', token[:30], '...')
    except Exception as e2:
        print('Alt-login ERROR:', e2)
        token = None

if token:
    # Get billing clients
    try:
        req2 = urllib.request.Request(
            'http://localhost:8000/billing/clients',
            headers={'Authorization': f'Bearer {token}'}
        )
        resp2 = urllib.request.urlopen(req2, timeout=8)
        clients = json.loads(resp2.read())
        print(f'\nTotal clients: {len(clients)}')
        for c in clients[:10]:
            print(f"  {c['name']}: {c['billable_cases_count']} billable, outstanding={c['outstanding_amount']}")
    except Exception as e:
        print('Clients ERROR:', e)

    # Get dashboard stats
    try:
        req3 = urllib.request.Request(
            'http://localhost:8000/billing/dashboard-stats',
            headers={'Authorization': f'Bearer {token}'}
        )
        resp3 = urllib.request.urlopen(req3, timeout=8)
        stats = json.loads(resp3.read())
        print('\nDashboard stats:', stats)
    except Exception as e:
        print('Stats ERROR:', e)
