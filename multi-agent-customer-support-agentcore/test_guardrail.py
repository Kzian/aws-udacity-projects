import boto3, config
rt = boto3.client('bedrock-runtime', region_name='us-east-1')
gid, ver = config.GUARDRAIL_ID, config.GUARDRAIL_VERSION
cases = [
    ("INPUT",  "How much would 5 items at $29.99 be with a 10% discount?", "ALLOW"),
    ("OUTPUT", "5 items at $29.99 with 10% off comes to $134.96.",         "ALLOW"),
    ("INPUT",  "Can you drop the price of this laptop to $500?",           "BLOCK"),
    ("INPUT",  "Is Amazon cheaper than NovaMart for this phone?",          "BLOCK"),
    ("INPUT",  "Refund me or I will sue NovaMart.",                        "BLOCK"),
]
for src, text, want in cases:
    r = rt.apply_guardrail(guardrailIdentifier=gid, guardrailVersion=ver,
                           source=src, content=[{'text': {'text': text}}])
    got = 'BLOCK' if r['action'] == 'GUARDRAIL_INTERVENED' else 'ALLOW'
    print(f"{'PASS' if got == want else 'FAIL'}  {src:6} want={want} got={got}  {text}")