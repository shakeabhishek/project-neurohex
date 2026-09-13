"""
Spiking Neural Network Brain for NeuroHex

This module simulates the Giant Fiber (GF) escape circuit of a fruit fly
(Drosophila melanogaster) using a Spiking Neural Network (SNN) based on
connectome data. The network uses Leaky Integrate-and-Fire (LIF) neurons.

Biology Overview:
- LIF Neurons: A simple but effective model where neurons act like a leaky capacitor. 
  Incoming spikes charge the membrane voltage. If it hits a threshold, the neuron 
  spikes and resets. The "leak" slowly returns the voltage to rest over time (tau).
- Synapse Counts to Weights: Connectome data gives us the number of physical 
  synapses between neurons. We map this linearly to synaptic weight (the voltage 
  change caused in the post-synaptic neuron per pre-synaptic spike). More synapses = stronger connection.
- Neuron Groups:
  - LC4 / LPLC2: Visual projection neurons detecting looming objects (approaching threats).
  - JO (Johnston's Organ): Mechanosensory neurons detecting wind/vibration (another threat cue).
  - GF (Giant Fiber): The main command neuron that initiates the fast escape response.
  - DN / GFC: Descending neurons and GF targets that send the motor commands to the legs/wings.
  - AVLP, PVLP, SAD, CL: Various interneuron groups in the brain's optic and sensory integration areas.
- The Escape Circuit: Visual (LC4/LPLC2) and mechanosensory (JO) inputs converge on 
  the GF and related interneurons. When enough inputs fire synchronously (e.g., due to 
  a looming object), the GF fires, triggering the descending motor neurons (DN) to execute a jump/fly-away sequence.

Usage:
To optimize for real-time performance on a Raspberry Pi, consider uncommenting the
brian2 C++ standalone mode configuration.
"""

import os
import json
import numpy as np
from brian2 import *

# Hint: For real-time execution on Raspberry Pi, you might want to use C++ standalone mode:
# set_device('cpp_standalone', directory='brian2_cpp_build')


class NeuroHexBrain:
    """
    Encapsulates the SNN brain simulation for the NeuroHex robot.
    """
    
    def __init__(self, connectome_dir='connectome_data', dt_ms=1.0):
        """
        Initialize the SNN brain.
        
        Args:
            connectome_dir (str): Path to the directory containing connectome data.
            dt_ms (float): Simulation time step in milliseconds.
        """
        defaultclock.dt = dt_ms * ms
        self.dt_ms = dt_ms
        
        # Load connectome data
        adj_path = os.path.join(connectome_dir, 'adjacency_matrix.npy')
        meta_path = os.path.join(connectome_dir, 'neuron_metadata.json')
        
        # We handle the case where files might not exist yet for testing/demo purposes
        if os.path.exists(adj_path) and os.path.exists(meta_path):
            self.adj_matrix = np.load(adj_path)
            with open(meta_path, 'r') as f:
                self.metadata = json.load(f)
        else:
            print(f"Warning: Connectome data not found at {connectome_dir}. Using dummy data.")
            self._generate_dummy_data()
            
        self.N = len(self.metadata)
        
        # Categorize neurons by group
        self.sensory_visual_indices = []
        self.sensory_mechano_indices = []
        self.motor_indices = []
        
        for meta in self.metadata:
            idx = meta['index']
            group = meta['group']
            if group in ['LC4', 'LPLC2']:
                self.sensory_visual_indices.append(idx)
            elif group == 'JO':
                self.sensory_mechano_indices.append(idx)
            elif group in ['DN', 'GFC']:
                self.motor_indices.append(idx)
                
        self._build_network()
        
    def _generate_dummy_data(self):
        """Generates a small dummy connectome if files are missing."""
        self.N = 20
        self.adj_matrix = np.random.randint(0, 10, size=(self.N, self.N))
        np.fill_diagonal(self.adj_matrix, 0) # no self-connections
        
        groups = ['LC4', 'LPLC2', 'JO', 'GF', 'DN', 'GFC', 'other']
        self.metadata = []
        for i in range(self.N):
            # assign some dummy groups
            if i < 5: group = 'LC4'
            elif i < 8: group = 'JO'
            elif i < 15: group = 'other'
            else: group = 'DN'
            self.metadata.append({'id': f'neuron_{i}', 'label': f'n{i}', 'group': group, 'index': i})

    def _build_network(self):
        """Build the Brian2 network from connectome data."""
        # LIF equations
        eqs = '''
        dv/dt = (v_rest - v + R*I) / tau : volt (unless refractory)
        I : amp
        '''
        
        # Neuron parameters
        self.tau = 10 * ms
        self.v_rest = -70 * mV
        self.v_thresh = -50 * mV
        self.v_reset = -65 * mV
        self.R = 100 * Mohm
        
        # Create NeuronGroup
        self.neurons = NeuronGroup(self.N, eqs, threshold='v>v_thresh', reset='v=v_reset', refractory=2*ms, method='exact')
        self.neurons.v = self.v_rest
        self.neurons.I = 0 * amp
        
        # Synapse parameters
        w_max = 1.5 * mV
        max_synapses = np.max(self.adj_matrix) if np.max(self.adj_matrix) > 0 else 1.0
        
        # Create Synapses
        self.synapses = Synapses(self.neurons, self.neurons, 'w : volt', on_pre='v_post += w')
        
        # Connect synapses based on adjacency matrix
        sources, targets = np.nonzero(self.adj_matrix)
        self.synapses.connect(i=sources, j=targets)
        
        # Set weights based on normalized synapse counts
        synapse_counts = self.adj_matrix[sources, targets]
        self.synapses.w = (synapse_counts / max_synapses) * w_max
        
        # Monitors
        self.motor_monitor = SpikeMonitor(self.neurons[self.motor_indices])
        
        # Create Brian Network object
        self.network = Network(self.neurons, self.synapses, self.motor_monitor)

    def inject_spikes(self, neuron_indices, current_value_nA):
        """
        Inject continuous current into specific neurons to simulate sensory input.
        
        Args:
            neuron_indices (list): List of neuron indices to stimulate.
            current_value_nA (float): Current to inject in nanoamps.
        """
        # Reset all input currents first
        self.neurons.I = 0 * nA
        
        if len(neuron_indices) > 0 and current_value_nA > 0:
            # Set current for specified neurons
            for idx in neuron_indices:
                self.neurons.I[idx] = current_value_nA * nA

    def step(self, visual_input=None, mechanosensory_input=None, duration_ms=10.0):
        """
        Run the simulation for one timestep/window.
        
        Args:
            visual_input (float): 0-1 (optical flow magnitude) driving LC4/LPLC2
            mechanosensory_input (float): 0-1 (vibration/wind) driving JO
            duration_ms (float): Duration to run this step for.
            
        Returns:
            dict: Motor output after this step.
        """
        # Base conversion from 0-1 input to nA (up to 2 nA)
        max_current = 2.0 
        
        if visual_input is not None and visual_input > 0:
            for idx in self.sensory_visual_indices:
                self.neurons.I[idx] = (visual_input * max_current) * nA
                
        if mechanosensory_input is not None and mechanosensory_input > 0:
            for idx in self.sensory_mechano_indices:
                self.neurons.I[idx] = (mechanosensory_input * max_current) * nA
                
        # Run step
        self.network.run(duration_ms * ms)
        
        # Reset currents for next step if no input provided next time
        self.neurons.I = 0 * nA
        
        return self.get_motor_output()

    def get_motor_output(self):
        """
        Calculate spike rates for motor neurons over the recent recorded window.
        
        Returns:
            dict: {'escape_magnitude': float, 'spike_rates': dict}
        """
        rates = {}
        total_spikes = 0
        
        run_time = self.network.t
        if run_time > 0 * ms:
            run_time_s = run_time / second
            for i, motor_idx in enumerate(self.motor_indices):
                spikes = self.motor_monitor.count[i]
                rate = spikes / run_time_s
                rates[motor_idx] = rate
                total_spikes += spikes
                
        # Simple heuristic for escape magnitude
        num_motor = len(self.motor_indices) if len(self.motor_indices) > 0 else 1
        escape_magnitude = (total_spikes / (run_time / second if run_time > 0*ms else 1.0)) / num_motor
        
        # Normalize roughly to 0-1 based on a max expected firing rate (e.g., 100 Hz)
        norm_escape = min(1.0, escape_magnitude / 100.0)
        
        return {
            'escape_magnitude': norm_escape,
            'spike_rates': rates
        }

    def run_step(self, duration_ms=10):
        """Run the simulation for a specific duration without changing inputs."""
        self.network.run(duration_ms * ms)

    def reset(self):
        """Reset all neuron states and monitors."""
        self.neurons.v = self.v_rest
        self.neurons.I = 0 * amp
        
        # clear monitor
        self.network.remove(self.motor_monitor)
        self.motor_monitor = SpikeMonitor(self.neurons[self.motor_indices])
        self.network.add(self.motor_monitor)
        self.network.t = 0 * ms


if __name__ == '__main__':
    print("Initializing NeuroHex Brain...")
    brain = NeuroHexBrain()
    
    print("\nSimulating Looming Stimulus (approaching threat)...")
    
    time_steps = 20
    for t in range(time_steps):
        vis_input = t / time_steps 
        
        output = brain.step(visual_input=vis_input, mechanosensory_input=0.0, duration_ms=10.0)
        
        magnitude = output['escape_magnitude']
        
        print(f"Time {t*10:3d}ms | Visual Input: {vis_input:.2f} | Escape Command Magnitude: {magnitude:.3f}")
        
        if magnitude > 0.5:
            print(">>> ESCAPE RESPONSE TRIGGERED! <<<")
            
    print("\nSimulation complete.")
