import faust
import redis
import json
import logging
from app.config import get_settings

settings = get_settings()
app = faust.App(
    'kovalent-pipeline',
    broker=f'kafka://{settings.kafka_bootstrap_servers}',
    value_serializer='json',
)

# Topics
cpu_topic = app.topic('metrics.cpu')
memory_topic = app.topic('metrics.memory')

# Redis for feature store
r = redis.Redis.from_url(settings.redis_url)

@app.agent(cpu_topic)
async def process_cpu(stream):
    async for event in stream:
        pod_id = event['pod']
        value = event['value']
        
        # Update feature store in Redis
        # key format: feature:pod_id:cpu
        # We store a rolling list for simple aggregations
        key = f"feature:{pod_id}:cpu"
        r.lpush(key, value)
        r.ltrim(key, 0, 59) # Keep last 60 points (5 mins at 5s cadence)
        
        # Compute features
        points = [float(x) for x in r.lrange(key, 0, -1)]
        if points:
            features = {
                "mean": sum(points) / len(points),
                "max": max(points),
                "p95": sorted(points)[int(0.95 * len(points))],
                "last_updated": event['timestamp']
            }
            r.set(f"store:{pod_id}:cpu", json.dumps(features))

@app.agent(memory_topic)
async def process_memory(stream):
    async for event in stream:
        pod_id = event['pod']
        value = event['value']
        key = f"feature:{pod_id}:memory"
        r.lpush(key, value)
        r.ltrim(key, 0, 59)
        
        points = [float(x) for x in r.lrange(key, 0, -1)]
        if points:
            features = {
                "mean": sum(points) / len(points),
                "max": max(points),
                "p95": sorted(points)[int(0.95 * len(points))],
                "last_updated": event['timestamp']
            }
            r.set(f"store:{pod_id}:memory", json.dumps(features))

if __name__ == '__main__':
    app.main()
