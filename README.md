# Compute Share Pilot

**Project page:** https://andresblitz.com/projects/compute-share-pilot/

**Author:** [Andrés Blitz](https://andresblitz.com/) · [@andresblitz](https://x.com/andresblitz)

This is a tiny proof of concept for your idea: let trusted friends offer spare computer power over the internet so one machine can run AI work on another machine.

The pilot is intentionally opinionated:

- It routes each request to one remote worker.
- Workers poll the coordinator for jobs.
- Workers can sit behind NAT on home internet.
- It is for trusted friends, not a public marketplace.

That shape is deliberate. For computers spread around the world, whole-request routing is much more practical than splitting one live chat response across multiple far-away machines.

## What This Pilot Proves

This pilot can prove:

- A friend in another country can contribute compute without exposing their local model port directly.
- A central coordinator can route jobs to whichever trusted machine is online.
- You can test real-world latency, uptime, and failure cases before building a business.

This pilot does not prove:

- That token-by-token distributed inference across continents will feel fast.
- That strangers on the public internet can be trusted with prompts, models, or billing.
- That a public marketplace will be profitable.

## Architecture

1. A small coordinator receives jobs and keeps a worker registry in memory.
2. Each worker registers itself, then polls for work every few seconds.
3. When a worker gets a job, it either:
   - runs a local Ollama model, or
   - returns a mock response for testing
4. The worker posts the result back to the coordinator.

This is a better first experiment than sharding a single inference job across the WAN because:

- home networks are inconsistent
- NAT and port forwarding are annoying
- cross-world latency hurts every token if you shard the model itself
- routing a full request to one remote machine is operationally simpler

## Files

- `coordinator.py`: central registry and job queue
- `worker.py`: polling worker, with optional Ollama integration
- `submit_job.py`: tiny client for submitting a test prompt

## Local Demo

Start the coordinator:

```bash
python3 coordinator.py
```

Start a worker in another terminal:

```bash
WORKER_ID=friend-a WORKER_SECRET=demo-secret python3 worker.py
```

Submit a test job:

```bash
python3 submit_job.py "Summarize why whole-request routing is better than WAN sharding"
```

## Demo With a Real Local Model

If a friend already runs Ollama on their machine:

```bash
OLLAMA_MODEL=llama3.2 \
WORKER_ID=friend-a \
WORKER_SECRET=demo-secret \
COORDINATOR_URL=http://YOUR-COORDINATOR:8000 \
python3 worker.py
```

Then submit a job that prefers that model tag:

```bash
python3 submit_job.py \
  --coordinator http://YOUR-COORDINATOR:8000 \
  --preferred-model llama3.2 \
  "Explain the tradeoff between latency and privacy in community AI compute."
```

## Cross-World Pilot Setup

For a real small-scale test between friends:

1. Put `coordinator.py` on a cheap VPS or cloud instance with a public IP.
2. Give each trusted friend a unique `WORKER_ID` and `WORKER_SECRET`.
3. Have each friend run `worker.py` on their own machine.
4. Start with mock mode first, then switch one worker to Ollama.
5. Measure:
   - time to first result
   - job failure rate
   - how often workers disappear
   - whether the cost of electricity and annoyance is worth it

## Security Notes

This prototype is not production-safe. Before going beyond friends, you would need:

- real authentication, not shared secrets in env vars
- encrypted transport with TLS
- prompt privacy controls
- job sandboxing
- abuse prevention and rate limits
- billing, metering, and dispute handling
- proof that workers are running the model they claim to run

## Practical Recommendation

If you keep exploring this idea, do it in this order:

1. Trusted friend network with whole-request routing
2. Batch workloads like embeddings, image generation, or offline jobs
3. Regional worker pools
4. Only then consider model sharding, and only where the network is very fast
