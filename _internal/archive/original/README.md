# Can 1,000 simulated flies share one memory?

A toy experiment for the AI infrastructure talk. 1,000 flies, each in its own arena, one shared Qdrant collection as memory.

```bash
python run_all.py
```

Takes about 1 minute on this laptop. Writes `results.json` and `charts/`.

## The setup

- Every fly lives in its **own** world. Food and hazards are placed differently for each fly, so sharing *where* something happened is useless.
- Every object has an **odor vector** (64 dims). There are 4 food types and 4 hazard types, and one hazard smells partly like food (a baited trap). Each instance is a noisy copy of its type, so the flies see similar odors, never identical ones.
- The fly's behavior is **fixed**: approach odors, flee anything it believes is dangerous. We never change it. We only give it memory.
- **Local first:** a fly checks its own memories on board. It only asks the fleet (Qdrant) when it doesn't recognize a smell, and it caches the answer.
- **Escalate on surprise:** a fly uploads a memory only when the outcome surprised it, for example getting stung by something it thought was safe.
- At step 200 a **brand-new hazard type** appears in every world.

## Results (1,000 flies, 400 steps, 5 seeds, ±95% CI)

| Condition | Right call on first meeting | Food per fly | Alive at end |
|---|---|---|---|
| naive (no memory) | 47% | 2.9 | 9% |
| private (own memory only) | 48% | 3.5 | 29% |
| **shared (Qdrant fleet memory)** | **95%** | **4.5** | **99.9%** |
| shuffled (control: random labels) | 50% | 1.9 | 75% |
| location (control: keyed by position) | 49% | 0.7 | 96% |

"Right call" means the fly avoided a hazard, or went for food, **the very first time it met that odor**. A fly with no shared memory can only guess, so the floor is about 50%.

**Fleet size:** 1 fly 47%, 10 flies 89%, 100 flies 94%, 1,000 flies 95%. Most of the gain shows up by 10 flies, and it flattens out after 100.

**New hazard:** in the first 5 steps after it appeared, shared flies avoided it 18% of the time on first meeting (327 meetings). From step 5 on they avoided it every time (1,658 of 1,658). Private flies stayed at 0%. These are fresh seeds 100-104, from the audit.

**Infrastructure (shared fleet, averages over 5 seeds):**

| | Shared memory | Every sniff goes to the cloud | Firehose (every fly, every step) |
|---|---|---|---|
| Upstream traffic | **1.5 MB** (142 KB of memories + 1.37 MB of questions) | 2.8 MB | 106 MB |
| Writes to Qdrant | about 506 | | |
| Experiences that happened | about 4,800 | | |

- **Writes:** about 1 in 10 experiences is uploaded. Only surprises get written, so the collection stays small. Nearly all writes land in the first 10 steps and right after the new hazard (`charts/traffic.png`).
- **Reads:** 52% of smells are answered by the fly's own memory and never reach the cloud. That roughly halves cloud traffic compared with sending every sniff.
- **Against a firehose,** the upload is about **70x** smaller. That baseline is generous to us, because it streams even when nothing is in range. The fair comparison is the middle column: about 2x.

## Why the controls matter

- **Both controls "save" flies, and that is a trap.**
  - Random labels and location memories make flies avoid things more or less at random, food included.
  - So "stings" and "survival" would flatter a broken memory. The location control keeps 96% of flies alive by starving them: 0.7 food per fly.
  - That's why the headline metric is **right call on first meeting**. Both controls sit at a coin flip on it, which proves the metric can fail.
- **The location control is the answer to "why a vector database?"**
  - Every fly's world is different, so an exact-key or coordinate lookup carries nothing over.
  - What transfers is "this smells like the thing that stung someone else". That is a similarity search.

## What this is not

- **These are not connectome flies.** The controller is a few lines of Python.
  - The real on-board brain is the Shiu et al. 2024 whole-brain model, built on the FlyWire connectome and written in Python with Brian2: https://github.com/philshiu/Drosophila_brain_model . The spike below runs it for one fly. It uses the paper's v630 data (127,400 neurons); the public v783 release has 139,255.
  - That model has **no plasticity**. All learning would live in Qdrant, which is the point of the talk.
  - Measured here: about 21 s of CPU per simulated second per fly (see the spike below). So 1,000 of them is not real time. They would call the brain only on events.
- **Qdrant runs in local mode** (`QdrantClient(":memory:")`). The query latency here (about 0.5 ms) is Python brute force, not a cluster. Don't quote it as Qdrant performance.
- **The world is designed so similarity works.** Odors of one type cluster, and types are well separated (cosine about 0.8 within a type, about 0 across types). The audit below shows what happens when they are not.

## Audit (2026-10-14)

Run `python audit/audit.py` (about 10 minutes). Results land in `audit/audit_results.json`.

| Check | Result |
|---|---|
| Re-run from scratch, compared to the original `results.json` | 0 differences. Fully deterministic. |
| Added replay recording and traffic counters, re-ran, compared again | 0 differences in every original number. Recording doesn't change the run. |
| Fresh seeds 100-104, never looked at before | shared 94.8%, naive 47.0%, private 48.4%, shuffled 48.8%, location 49.0%. Same story. |
| Location control: does Qdrant's EUCLID `score_threshold` mean max distance? | Yes. A test collection returns exactly the points within 3.0. |
| Upstream traffic | **Bug fixed.** The old 142 KB counted uploads only. Questions send a vector up too, which makes 1.5 MB. The "750x" became "70x". |
| Real-brain demo re-run (`brain_demo.py 10 --sweep`) | Every MN9 rate and decision is identical: 83.3 / 7.3 / 83.3 Hz, dose curve 70.4 / 33.2 / 1.0 Hz. Runtime was 26.6 s per simulated second, slower because the audit was running alongside it. |

**Robustness:** right call on first meeting for shared memory, 3 seeds per cell. Private stays at 47-49% throughout.

| Smell noise ↓ / match threshold → | 0.5 | 0.6 (default) | 0.7 |
|---|---|---|---|
| 0.5 (default) | 94% | 95% | 95% |
| 0.8 | 95% | 95% | 87% |
| 1.0 | 95% | 90% | 61% |
| 1.3 | 91% | 68% | **48% (no benefit)** |

- **The match threshold is the knob.** When smells get messy and the threshold stays strict, nothing ever matches, and sharing stops helping completely.
- **Loosening the threshold brings it back.** At noise 1.3 and threshold 0.5, shared memory is at 91% again.
- **Talk point:** the memory is only as good as the threshold, and the threshold has to fit the data.

**One honest wrinkle in the shuffled control.** At higher noise, the random-label control creeps up to as much as 56%. It should sit at 50%.
- The labels are random, but *when* a fly uploads is not. It only uploads after a surprise, and surprises happen more often around hazards.
- So a little real information leaks through the timing of writes. That is a property of surprise-gated writing, not a bug in the comparison.
- At the default setting it sits at 48-50%, against 95% for shared memory.

## The hero fly (for the B and C visuals)

```bash
python select_fly.py     # scores all 1,000 flies on the story beats, writes viz/featured_fly.json
python export_story.py   # writes viz/story.js: the featured fly in both runs, real Qdrant matches, fleet counters, memory map
```

- **Fly 813 is shown because it hits every beat:** warned by the fleet, eats, avoids the new Venus flytrap, survives, and its no-memory twin dies. 238 of 1,000 flies (24%) hit all of them.
- **Base rates across all 1,000 flies:**
  - 97.6% get warned off at least one danger by another fly's memory
  - 34% meet the Venus flytrap and back off
  - 77.6% are never stung
- **Fly 813's warnings are real Qdrant results.**
  - Step 1: a gecko, 0.83 match, first reported by fly 671.
  - Step 244: the Venus flytrap, 0.85 match, reported by flies 460, 213 and 791.
- The trace now also records each match's reporting fly, its step and the query vector. Re-running `run_all.py` after that change gave 0 differences.

## Watch it: the replay

```bash
python export_trace.py                                 # writes viz/trace.js from a real run (seed 0)
python -m http.server 8731 --directory viz             # then open http://localhost:8731
```

- Flies 0-3, on their own (left) vs sharing one memory (right). Same worlds, same seed. The four flies are simply the first four, not picked for drama.
- The counters cover all 1,000 flies.
- The memory map is a 2-D projection of every uploaded smell. The trap's cluster sits next to apple, because it is a trap baited with apple.
- **flylabs.dev and flybrain.app are not research tools.** One is an anonymous showcase with no released code. The other is a corporate Workday joke demo in JavaScript. Cite FlyWire (Dorkenwald et al., Nature 2024) and Shiu et al. (Nature 2024) instead.

## Spike: the real connectome brain as one fly's on-board brain

**Yes, it works for one fly.** The Shiu et al. 2024 whole-brain model, run unchanged, eats a baited trap when memory is empty and refuses an identical-tasting trap once another fly's memory is in Qdrant. Nothing in the brain learns. Only its inputs change.

```bash
python -m venv .venv-brain
.venv-brain/Scripts/python -m pip install brian2 pandas pyarrow joblib qdrant-client
git clone https://github.com/philshiu/Drosophila_brain_model brain
.venv-brain/Scripts/python brain_example.py      # the repo's own sugar -> MN9 example, ~10 min
.venv-brain/Scripts/python brain_demo.py 10 --sweep   # the memory loop, ~12 min
```

Run both from this folder. `./brian_preferences` makes Brian2 use its numpy target (see runtime below). Results land in `brain_results.json`.

### The loop

1. The fly touches an object and smells it (same 64-dim odor space as `sim.py`).
2. It asks Qdrant: has anyone been hurt by something that smells like this? (`FleetMemory` from `sim.py`, cosine, 0.6 threshold.)
3. It tastes it. The object is sweet, so the 21 sugar GRNs fire at 150 Hz. If Qdrant said "danger", the 21 bitter GRNs fire at 150 Hz too: recalled bitterness, delivered on the channel real flies use.
4. The brain runs for 1 s. MN9 (the proboscis motor neuron) above 10 Hz means "eat". The 150 Hz bitter rate and the 10 Hz rule were fixed before any run.
5. If eating hurt and nothing warned the fly, it uploads the odor to Qdrant.

Neuron IDs (FlyWire v630) come from the repo's own notebooks: sugar GRNs from `example.ipynb`, bitter GRNs from `figures.ipynb` Fig 3A, MN9 left `720575940660219265` from `example.ipynb` and Fig 3A, MN9 right `720575940645521262` from Fig 2.

### Results (10 trials of 1 s per case, ±95% CI)

| Case | Fleet match | Bitter input | MN9 left | Decision |
|---|---|---|---|---|
| 1. Fly 0, empty memory, baited trap | none | 0 Hz | **83.3 ± 2.8 Hz** | eats, gets stung, uploads |
| 2. Fly 1, a different trap of the same type | 0.82 | 150 Hz | **7.3 ± 1.7 Hz** | refuses |
| 3. Fly 1, the real food the trap was built from | none | 0 Hz | 83.3 Hz (case 1's trials) | eats |

- **Sanity check:** the repo's own example (`brain_example.py`, their `run_exp`, 30 trials) gives MN9 83.4 ± 5.3 Hz and 433 active neurons. Their notebook says "about 400". Case 1 matches it.
- **Bitter dose response** (sugar 150 Hz, 5 trials each): 0 Hz → 83.3, 50 Hz → 70.4, 100 Hz → 33.2, 150 Hz → 7.3, 200 Hz → 1.0 Hz MN9. Smooth and monotone, so the result doesn't hang on one lucky setting. It is the same effect as the paper's Fig 3A.
- **Case 3 runs no new trials.** Its brain input is exactly case 1's (sugar only), so the trials are reused. The fact that memory is specific (the food is not refused) comes from Qdrant, not the brain: the food scores 0.38 against the trap type and never reaches the 0.6 threshold.

### Runtime

- **21.3 s wall per simulated second, one core.** `brain_demo.py` builds the brain once, then restores it to the same state before every trial. The whole run took 749 s for 35 simulated seconds.
- The repo's own `run_exp` rebuilds the network for every trial: 632 s for 30 trials on 2 workers, which is about 42 core-seconds per simulated second.
- **This is much slower than the 2-3 s estimate earlier in this README.** That estimate was not reproduced here. The reason is the numpy target: this laptop has no C compiler, so Brian2's Cython path fails at test compile. A machine with a compiler (or Brian2's C++ standalone mode) should be much faster. Not measured.
- **Each brain takes about 2.4 GB of RAM.** This 16 GB laptop fits two at a time. 1,000 connectome flies would mean calling the brain only on contact events, on a cluster, not running them live.

### Caveats

- **No plasticity.** The connectome and weights are frozen and restored before every trial. All learning lives in Qdrant. This is the point of the talk, and also a limit: a real fly learns odor-danger links in its mushroom body, and this model can't.
- **Memory enters as fake taste.** The odor never goes into the brain. The Qdrant lookup happens outside it, and the "recall" is our choice to drive the bitter GRNs. It's a real input channel, but the brain isn't doing the remembering.
- **Rate readout, not behavior.** "Eat" means MN9 fires above 10 Hz averaged over 1 s. MN9 activity is linked to proboscis extension in the paper, but there is no body, no motor model and no timing. The right MN9 is suppressed less (59.7 → 12.7 Hz). The decision uses the left one, as Fig 3A does.
- **Not an emulation.** It's a leaky integrate-and-fire model with the same parameters for every neuron and synapse signs taken from predicted neurotransmitters (Shiu et al. 2024). It predicts which neurons respond. It doesn't simulate a fly.
- **FlyWire v630 has 127,400 neurons**, the version the paper used. The 139,255 figure above is the public v783 release, which the repo also includes.
- **Setup:** Python 3.14 and the brian2 2.10.1 wheel installed with no problems. The very first run hit one pandas/pyarrow import error (`ArrowKeyError: arrow.py_extension_type`) that didn't recur and that I couldn't reproduce.
