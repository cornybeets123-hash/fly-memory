# Sources

The neural engine and packed FlyWire v783 data come from [Doodle Fly](https://github.com/dtecx/doodle-fly/tree/2a8a0311e4e488e9bf9a7f8e79e42ffb8bcaadf5). The code uses the MIT license in `../LICENSE.doodle-fly`. The workshop adds shared weight arrays and a supervised neural worker.

The model uses the leaky integrate-and-fire parameters from [Shiu et al., Nature 2024](https://www.nature.com/articles/s41586-024-07763-9). The fast Float32 runtime uses its own event scheduler. Dense integration checks validate the optimization. Brian2 equivalence remains unestablished.

FlyWire data use [CC BY-NC 4.0](https://creativecommons.org/licenses/by-nc/4.0/). Attribution: Dorkenwald et al., "Neuronal wiring diagram of an adult brain," Nature 634, 124–138 (2024), and Schlegel et al., "Whole-brain annotation and multi-connectome cell typing of Drosophila," Nature 634, 139–152 (2024). Neuron annotations come from [flywire_annotations](https://github.com/flyconnectome/flywire_annotations).

The workshop uses Doodle Fly's LC10a bearing adapter and six descending cells per side. The fixed decoder turns their spike counts into yaw. At each fork, a 200 ms window of bilateral 30 Hz input drives neural branch selection. The decoded sign selects between two locally observed options. Retrieval suppresses one option’s sensory input. The option mapping, sensing, forward motion, braking, and observer are engineered. The connectome's weights stay fixed.

The display uses actual anatomical anchor positions and computed spikes. Its retrieval diagram connects the query to actual returned records. It does not expose an HNSW traversal.

Qdrant Edge runs in the local Python process. Each personal fly retrieves only its own observations. Newcomers read the completed A group from the same shard. This pool stays unchanged while the B group runs. The workshop demonstrates local shared access. Eight independent brains advance on one simulation clock. Writes follow all current-cycle decisions. The live display receives computed movement, observations, queries, and spikes in batches.
