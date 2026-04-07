# Viability Analysis

## Short Answer

Yes, the idea is possible with today's technology, but only some versions of the idea are attractive.

The most viable version today is:

- trusted or semi-trusted machines
- whole-request routing to one worker at a time
- batch or async workloads first

The least viable version today is:

- public strangers
- globally scattered home computers
- one live chat response split across those machines token by token

## Why The Idea Is Real

There is strong evidence that distributed AI compute is technically possible:

- Petals showed distributed LLM inference over the internet and reported a real-world setup spanning two continents.
- exo is actively building multi-device local AI clusters and focuses on topology-aware model splitting.
- Prima.cpp specifically targets heterogeneous home clusters with slow links and limited memory.
- Vast.ai demonstrates that there is already demand for marketplace-style GPU supply from community and datacenter providers.

## What Makes Or Breaks It

### 1. Latency

Latency is the main constraint.

If every generated token requires cross-machine coordination, then long-distance links hurt user experience badly. That makes globally sharded interactive chat much harder than it sounds.

Inference feels much better when:

- the entire request runs on one selected machine, or
- the machines are in the same fast local network, or
- the workload is batch-oriented instead of interactive

### 2. Reliability

Home computers disappear. They reboot, sleep, lose internet, or overheat.

That is survivable for:

- queues
- async jobs
- retries
- redundant scheduling

It is much worse for:

- live sessions
- streaming responses
- strict SLAs

### 3. Trust And Safety

A public network raises hard problems:

- prompt privacy
- model theft
- malware risk
- fake benchmark claims
- result poisoning
- billing fraud

That is why the trusted-friends pilot is the right first step.

### 4. Economics

The business challenge is not just "can it run?"

It is also:

- can you beat cheap hosted GPU markets
- can you keep uptime high enough
- can you price in a way that covers power, hardware wear, support, and failure

This is where many technically possible ideas become weak businesses.

## Best Use Cases

These are the strongest early targets:

- overnight batch jobs
- embeddings
- transcription
- image generation
- fine-tuning experiments
- scheduled agent jobs

These are weaker early targets:

- premium real-time chat
- public API inference with strict latency
- mission-critical enterprise workloads

## Best Product Shape

If you pursue this as a product, the best first version is probably:

- "Airbnb for trusted idle GPUs" is not the first product
- "send my queued AI jobs to trusted community workers" is the better first product

In other words, start as:

- a scheduler
- a worker agent
- a metering layer
- a reliability layer

Not as:

- a globally sharded real-time inference fabric

## Sources

- Petals paper: https://arxiv.org/abs/2312.08361
- exo repository: https://github.com/exo-explore/exo
- Prima.cpp paper: https://arxiv.org/abs/2504.08791
- Vast.ai docs: https://docs.vast.ai/documentation/get-started
