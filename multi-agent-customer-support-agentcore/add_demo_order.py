import boto3, config
from datetime import date, timedelta
from boto3.dynamodb.conditions import Key

t = boto3.resource('dynamodb', region_name='us-east-1').Table(config.ORDERS_TABLE)
items = t.query(KeyConditionExpression=Key('customer_id').eq('CUST-001'))['Items']
base = next((i for i in items if i.get('status') == 'delivered'), items[0])
item = dict(base)
item['order_id'] = 'ORD-27176'
item['status'] = 'delivered'
item['order_date'] = str(date.today() - timedelta(days=5))
item['delivery_date'] = str(date.today() - timedelta(days=2))
for k in ('product', 'product_name', 'item', 'item_name'):
    if k in item:
        item[k] = 'Sony Wireless Headphones'
for k in ('return_status', 'return_reference', 'return_reason', 'return_requested_at'):
    item.pop(k, None)
t.put_item(Item=item)
print({k: item[k] for k in item if k in ('customer_id', 'order_id', 'status', 'order_date', 'delivery_date')})