"""
Fetches the Giant Fiber (GF) escape circuit from the MaleCNS connectome
(a unified whole-CNS EM reconstruction covering both the brain and the
ventral nerve cord, VNC).

We deliberately stay within the direct (1-hop) synaptic neighborhood of
GF: its sensory/interneuron inputs in the brain, and its real motor
outputs in the VNC (GFC relay neurons, TTMn, DNp11). This keeps the
network to under ~1000 neurons -- a small fraction of the full CNS
(tens of thousands of neurons) -- so it stays fast enough to simulate
in real time on a Raspberry Pi.

Earlier iterations of this script used the hemibrain dataset, which only
covers the central brain. GF's real motor targets (GFC1-4, TTMn, DNp11)
live in the VNC, so hemibrain's "downstream of GF" query only ever found
a handful of weak (<=13 synapse) local recurrent connections within the
brain -- the escape command never actually reached a motor neuron.
MaleCNS captures GF's full axon, brain to VNC, in one consistent volume.
"""

import os
import json
import logging
import numpy as np
from vfb_connect.cross_server_tools import VfbConnect

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

# DNp01 is the accepted descending-neuron name for the Giant Fiber. GF is a
# bilateral pair; MaleCNS resolves left and right as separate instances.
GF_INSTANCES = {
    'VFB_jrmc30my': 'DNp01(GF)_R',
    'VFB_jrmc30mz': 'DNp01(GF)_L',
}

WEIGHT_THRESHOLD = 3


def get_functional_group(label):
    """Classify neuron into functional groups based on name prefixes."""
    if not isinstance(label, str):
        return 'other'

    label_upper = label.upper()
    if 'LC4' in label_upper:
        return 'LC4'
    elif 'LPLC2' in label_upper:
        return 'LPLC2'
    elif 'JO-A' in label_upper or 'JO-B' in label_upper or 'JO-C' in label_upper or 'JO' in label_upper:
        return 'JO'
    elif 'AVLP' in label_upper:
        return 'AVLP'
    elif 'PVLP' in label_upper:
        return 'PVLP'
    elif 'SAD' in label_upper:
        return 'SAD'
    elif 'CL' in label_upper:
        return 'CL'
    elif 'GFC' in label_upper:
        return 'GFC'
    elif 'TTMN' in label_upper:
        return 'TTMn'
    elif 'GIANT FIBER' in label_upper or '(GF)' in label_upper:
        return 'GF'
    elif 'DN' in label_upper:
        return 'DN'
    else:
        return 'other'


def main():
    out_dir = os.path.join(os.path.dirname(__file__), 'connectome_data')
    os.makedirs(out_dir, exist_ok=True)

    vc = VfbConnect()

    neurons = {}
    connection_list = []

    for gf_id, gf_label in GF_INSTANCES.items():
        neurons[gf_id] = {'id': gf_id, 'label': gf_label, 'group': 'GF'}

    for gf_id, gf_label in GF_INSTANCES.items():
        logging.info(f"Fetching downstream targets of {gf_label}...")
        try:
            df_down = vc.get_neurons_downstream_of(
                neuron=gf_id, weight=WEIGHT_THRESHOLD, query_by_label=False, return_dataframe=True)
        except Exception as e:
            logging.error(f"Error fetching downstream neurons for {gf_label}: {e}")
            df_down = None

        logging.info(f"Fetching upstream inputs to {gf_label}...")
        try:
            df_up = vc.get_neurons_upstream_of(
                neuron=gf_id, weight=WEIGHT_THRESHOLD, query_by_label=False, return_dataframe=True)
        except Exception as e:
            logging.error(f"Error fetching upstream neurons for {gf_label}: {e}")
            df_up = None

        if df_down is not None and not df_down.empty:
            for _, row in df_down.iterrows():
                target_id = row['target_neuron_id']
                target_label = row['target_neuron_name']
                weight = row['weight']

                if target_id not in neurons:
                    neurons[target_id] = {'id': target_id, 'label': target_label, 'group': get_functional_group(target_label)}

                connection_list.append({
                    'source_id': gf_id,
                    'target_id': target_id,
                    'weight': int(weight)
                })

        if df_up is not None and not df_up.empty:
            for _, row in df_up.iterrows():
                query_id = row['query_neuron_id']
                query_label = row['query_neuron_name']
                weight = row['weight']

                if query_id not in neurons:
                    neurons[query_id] = {'id': query_id, 'label': query_label, 'group': get_functional_group(query_label)}

                connection_list.append({
                    'source_id': query_id,
                    'target_id': gf_id,
                    'weight': int(weight)
                })

    # Assign indices
    neuron_list = list(neurons.values())
    for i, n in enumerate(neuron_list):
        n['index'] = i

    id_to_index = {n['id']: n['index'] for n in neuron_list}

    # Build Adjacency Matrix. Parallel edges (e.g. both GF_L and GF_R
    # synapsing onto the same downstream neuron) accumulate their weights.
    N = len(neuron_list)
    adj_matrix = np.zeros((N, N), dtype=int)

    for conn in connection_list:
        src_idx = id_to_index[conn['source_id']]
        tgt_idx = id_to_index[conn['target_id']]
        adj_matrix[src_idx, tgt_idx] += conn['weight']

    # Save outputs
    logging.info("Saving outputs...")

    np.save(os.path.join(out_dir, 'adjacency_matrix.npy'), adj_matrix)

    with open(os.path.join(out_dir, 'neuron_metadata.json'), 'w') as f:
        json.dump(neuron_list, f, indent=4)

    with open(os.path.join(out_dir, 'connection_list.json'), 'w') as f:
        json.dump(connection_list, f, indent=4)

    # Summary
    group_counts = {}
    for n in neuron_list:
        grp = n['group']
        group_counts[grp] = group_counts.get(grp, 0) + 1

    logging.info(f"Total neurons: {N}")
    logging.info("Neuron counts by group:")
    for grp, count in sorted(group_counts.items(), key=lambda kv: -kv[1]):
        logging.info(f"  {grp}: {count}")

    logging.info("Done.")


if __name__ == '__main__':
    main()
