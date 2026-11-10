# Data and model provenance

## Neural recordings

`brain-bank.json` and `spikes/*.npz` contain 48 one-second simulations from the unchanged [Shiu et al. model](https://github.com/philshiu/Drosophila_brain_model), commit `91bdd1e7dcf193f3e7ca5a8933497fcef63b7960`. The upstream code uses the MIT license. The [official Shiu archive](https://doi.org/10.17617/3.CZODIW) also declares MIT for its source data and computational results. [FlyWire guidelines](https://flywire.ai/guidelines) separately publish FlyWire data under CC BY-NC 4.0. These sources do not explain how their grants interact for the v630 data. Preserve both notices when reusing the underlying data. The recordings are computed spikes, rather than measurements from a living fly.

The bank records source hashes, parameters, versions, stimulation rates, seeds, neuron IDs, time bins, readouts, and raw-file hashes. Each trial resets the same naive network. Stimulated neurons receive zero refractory period, as the upstream Poisson-input helper specifies. Synapse weights stay fixed.

The model uses FlyWire v630: 127,400 neurons and 14,687,178 synaptic connections. Sugar and bitter IDs come from the upstream notebooks and this repository's original `_internal/archive/original/brain_demo.py`. P9, oDN1, and Foxglove IDs come from the [Sapkal model's v630 annotation sheet](https://github.com/bidaye-lab/spiking_neural_network_model/blob/main/data/flywire_ids_630.xlsx).

Sources:

- [Shiu et al., Nature 2024](https://www.nature.com/articles/s41586-024-07763-9).
- [Sapkal et al., Nature 2024](https://www.nature.com/articles/s41586-024-07854-7).
- [Dorkenwald et al., Nature 2024](https://doi.org/10.1038/s41586-024-07558-y).
- [Schlegel et al., Nature 2024](https://doi.org/10.1038/s41586-024-07686-5).
- [Original model license](https://github.com/philshiu/Drosophila_brain_model/blob/91bdd1e7dcf193f3e7ca5a8933497fcef63b7960/LICENSE).

The original recording protocol remains in `_internal/archive/original/tools/record_brain.py`. Its historical paths require adaptation before regeneration. `_internal/tests/test_brain.py` reconstructs named traces from raw spikes and checks hashes. The frontend uses exact spike times from one sugar neuron, one bitter neuron, and the left MN9 motor neuron. The encounter layout uses schematic positions.

## Receptor responses

`odors.json` is a subset of [DoOR.data](https://github.com/ropensci/DoOR.data), commit `db323a496577c4b4a72b5c2fcd1859e07521ffb5`, version 2.0.1.9001. The data is licensed under [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/). This subset and its transformations retain that license.

Attribution: Münch D and Galizia CG. [DoOR 2.0: Comprehensive Mapping of Drosophila melanogaster Odorant Responses](https://doi.org/10.1038/srep21841). Scientific Reports 6, 21841 (2016).

Changes: retain nine odorants and 24 receptor columns complete across those odorants. Preserve supplied response values. Record a fixed library mean for centering. No missing values are imputed. Exact source URLs and SHA256 hashes are included in `odors.json`.

Mixture recipes, linear mixing, sensory noise, and poison assignments are designed assumptions. They are not measured mixture responses. No outcome labels enter the vector representation or the fixed display projection.

## Visual assets

Qdrant marks come from [official brand resources](https://qdrant.tech/brand-resources/). Mona Sans is bundled with its [OFL license](../static/fonts/OFL.txt). The fly rendering extends the repository's existing canvas specimen illustration.
