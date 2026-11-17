"""Read JSON log lines from the webhook container and print the useful fields."""
import sys, json
for line in sys.stdin:
    try:
        d = json.loads(line)
        event = d.get('json', {})
        if not event:
            continue
        print(json.dumps({
            'event': event['event'], 'object_type': event['object_type'],
            'address': event['data']['address'],
            'description': event['data']['description'],
            'method': event['request']['method'],
            'path': event['request']['path'],
        }, indent=2))
    except (ValueError, KeyError):
        pass
