import boto3, config
t = boto3.resource('dynamodb', region_name='us-east-1').Table(config.ORDERS_TABLE)
t.update_item(Key={'customer_id': 'CUST-001', 'order_id': 'ORD-27176'},
  UpdateExpression='SET estimated_delivery = :e, return_eligible = :r REMOVE return_status, return_reference, return_reason, return_requested_at',
  ExpressionAttributeValues={':e': '2026-10-25', ':r': True})
print('reset ok')