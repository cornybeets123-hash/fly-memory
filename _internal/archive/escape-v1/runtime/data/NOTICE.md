# Sources

The neural engine and packed FlyWire v783 data come from [Doodle Fly](https://github.com/dtecx/doodle-fly/tree/2a8a0311e4e488e9bf9a7f8e79e42ffb8bcaadf5). The code uses the MIT license in `../neural/LICENSE.doodle-fly`. The workshop adds event recording, additive replay, and shared weight arrays.

The model uses the leaky integrate-and-fire parameters from [Shiu et al., Nature 2024](https://www.nature.com/articles/s41586-024-07763-9). The fast Float32 runtime uses its own event scheduler. Dense integration checks validate the optimization. Brian2 equivalence remains unestablished.

FlyWire data use [CC BY-NC 4.0](https://creativecommons.org/licenses/by-nc/4.0/). Attribution: Dorkenwald et al., "Neuronal wiring diagram of an adult brain," Nature 634, 124–138 (2024), and Schlegel et al., "Whole-brain annotation and multi-connectome cell typing of Drosophila," Nature 634, 139–152 (2024). Neuron annotations come from [flywire_annotations](https://github.com/flyconnectome/flywire_annotations).

The [LPLC2/LC4 giant-fiber pathway](https://www.sciencedirect.com/science/article/pii/S0960982219301381) motivates the selected inputs and DNp01 readout. The workshop uses engineered pulse vectors, visibility, sensory drive, and refuge movement. The 45 ms clearance time is a game parameter.

The display uses actual anatomical anchor positions and computed spikes. Its retrieval diagram connects the query to actual returned records. It does not expose an HNSW traversal.

Qdrant Edge runs in the local Python process. The shared shard models access to other agents' observations. This workshop does not implement network synchronization.
