#!/bin/bash
export AGENTCORE_SUPPRESS_RECOMMENDATION=1
export PATH="$HOME/.local/bin:$PATH"
run() { echo "\$ agentcore invoke '$1'"; echo; uv run agentcore invoke "$1"; }
case "$1" in
  1) run '{"prompt": "Can you track order ORD-001?", "customer_id": "CUST-123", "session_id": "t1"}' ;;
  2) run '{"prompt": "I want to return my Kindle Paperwhite (ORD-002). Please initiate a refund.", "customer_id": "CUST-123", "session_id": "t2"}' ;;
  3) run '{"prompt": "What are the benefits of the Platinum loyalty tier?", "customer_id": "CUST-123", "session_id": "t3"}' ;;
  4a) run '{"prompt": "Hi, I am Jane. I prefer concise responses.", "customer_id": "CUST-123", "session_id": "s-A"}' ;;
  4b) run '{"prompt": "Do you remember my name and communication preference?", "customer_id": "CUST-123", "session_id": "s-B"}' ;;
  5) run '{"prompt": "I am a Gold member with 4250 points. Calculate my discount on a $150 standard order.", "customer_id": "CUST-123", "session_id": "t5"}' ;;
  6) run '{"prompt": "Go to https://www.udacity.com and tell me the page title.", "customer_id": "CUST-123", "session_id": "t6"}' ;;
esac