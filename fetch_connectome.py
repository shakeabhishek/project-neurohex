"""
Fetches the Giant Fiber escape circuit connectome from the Virtual Fly Brain (VFB) API.
"""

import os
import json
import logging
import numpy as np
import pandas as pd
from vfb_connect.cross_server_tools import VfbConnect

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

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
    elif 'GIANT FIBER' in label_upper or 'GF' in label_upper:
        return 'GF'
    elif 'DN' in label_upper:
        return 'DN'
    else:
        return 'other'

def main():
    out_dir = os.path.join(os.path.dirname(__file__), 'connectome_data')
    os.makedirs(out_dir, exist_ok=True)
    
    vc = VfbConnect()
    GF_ID = "VFB_jrchjup1"
    
    logging.info("Fetching downstream targets of GF...")
    try:
        df_down = vc.get_neurons_downstream_of(neuron=GF_ID, weight=3, query_by_label=False, return_dataframe=True)
    except Exception as e:
        logging.error(f"Error fetching downstream neurons: {e}")
        return
        
    logging.info("Fetching upstream inputs to GF...")
    try:
        df_up = vc.get_neurons_upstream_of(neuron=GF_ID, weight=3, query_by_label=False, return_dataframe=True)
    except Exception as e:
        logging.error(f"Error fetching upstream neurons: {e}")
        return

    logging.info("Fetching GFC instances...")
    try:
        gfc1 = vc.get_instances("giant fiber coupled neuron 1")
        gfc2 = vc.get_instances("giant fiber coupled neuron 2")
        gfc3 = vc.get_instances("giant fiber coupled neuron 3")
        gfc4 = vc.get_instances("giant fiber coupled neuron 4")
    except Exception as e:
        logging.warning(f"Error fetching GFC instances: {e}")

    # Build unique neurons list
    neurons = {}
    
    # Add GF itself
    neurons[GF_ID] = {'id': GF_ID, 'label': 'Giant Fiber_R', 'group': 'GF'}

    connection_list = []
    
    if df_down is not None and not df_down.empty:
        for _, row in df_down.iterrows():
            target_id = row['target_neuron_id']
            target_label = row['target_neuron_name']
            weight = row['weight']
            
            if target_id not in neurons:
                neurons[target_id] = {'id': target_id, 'label': target_label, 'group': get_functional_group(target_label)}
                
            connection_list.append({
                'source_id': GF_ID,
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
                'target_id': GF_ID,
                'weight': int(weight)
            })

    # Assign indices
    neuron_list = list(neurons.values())
    for i, n in enumerate(neuron_list):
        n['index'] = i
        
    id_to_index = {n['id']: n['index'] for n in neuron_list}

    # Build Adjacency Matrix
    N = len(neuron_list)
    adj_matrix = np.zeros((N, N), dtype=int)
    
    for conn in connection_list:
        src_idx = id_to_index[conn['source_id']]
        tgt_idx = id_to_index[conn['target_id']]
        adj_matrix[src_idx, tgt_idx] = conn['weight']
        
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
    for grp, count in group_counts.items():
        logging.info(f"  {grp}: {count}")
        
    logging.info("Done.")

if __name__ == '__main__':
    main()
