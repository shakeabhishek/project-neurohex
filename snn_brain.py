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
  synapses between neurons. Most synapses are log-scaled to a shared weight
  ceiling (log-compression keeps a few very strong connections from drowning
  out weaker but still meaningful ones). GF's direct synapses onto its true
  motor targets (TTMn/DN) are the exception: see _build_network().
- Neuron Groups:
  - LC4 / LPLC2: Visual projection neurons detecting looming objects (approaching threats).
  - JO (Johnston's Organ): Mechanosensory neurons detecting wind/vibration (another threat cue).
  - GF (Giant Fiber): The main command neuron (bilateral pair) that initiates the fast escape response.
  - TTMn / DN: GF's real motor targets -- TTMn (tergotrochanteral motor neuron)
    fires the jump muscle directly; DN (incl. DNp11) carries the descending
    command onward. GFC1-4 are a mid-circuit relay, modeled but not read out.
  - AVLP, PVLP, SAD, CL: Various interneuron groups in the brain's optic and sensory integration areas.
- The Escape Circuit: Visual (LC4/LPLC2) and mechanosensory (JO) inputs converge on
  the GF and related interneurons. When enough inputs fire synchronously (e.g., due to
  a looming object), the GF fires, triggering TTMn/DN to execute a jump/fly-away sequence.

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
    
    def __init__(self, connectome_dir='connectome_data', dt_ms=1.0, readout_window_ms=100.0):
        """
        Initialize the SNN brain.

        Args:
            connectome_dir (str): Path to the directory containing connectome data.
            dt_ms (float): Simulation time step in milliseconds.
            readout_window_ms (float): Trailing window used by step() to compute
                escape magnitude -- a rolling "recent activity" rate rather than
                an average since the network started. 100ms balances reacting
                quickly to a new threat against enough spikes to give a stable
                rate estimate (a single call's duration_ms is usually too short
                on its own: 1-2 motor spikes in 10-20ms is a noisy rate).
        """
        defaultclock.dt = dt_ms * ms
        self.dt_ms = dt_ms
        self.readout_window_ms = readout_window_ms

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
            elif group in ['DN', 'TTMn']:
                # True post-GF motor output: TTMn is the tergotrochanteral
                # motor neuron that fires the jump muscle; DN (DNp11 and
                # others) carries the descending command onward. GFC is a
                # mid-circuit relay, not a motor neuron, so it's excluded
                # here (it still participates in the network dynamics).
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
        # Neuron parameters
        tau = 10 * ms
        v_rest = -70 * mV
        v_thresh = -50 * mV
        v_reset = -65 * mV
        R = 100 * Mohm
        
        # Store for reset
        self.v_rest = v_rest
        
        # LIF equations
        eqs = '''
        dv/dt = (v_rest - v + R*I) / tau : volt (unless refractory)
        I : amp
        '''
        
        # Create NeuronGroup
        self.neurons = NeuronGroup(
            self.N, eqs,
            threshold='v > v_thresh',
            reset='v = v_reset',
            refractory=2*ms,
            method='exact',
            namespace={
                'tau': tau,
                'v_rest': v_rest,
                'v_thresh': v_thresh,
                'v_reset': v_reset,
                'R': R,
            }
        )
        self.neurons.v = v_rest
        self.neurons.I = 0 * amp
        
        # Synapse parameters
        w_max = 1.5 * mV
        max_synapses = np.max(self.adj_matrix) if np.max(self.adj_matrix) > 0 else 1.0

        # Create Synapses
        self.synapses = Synapses(self.neurons, self.neurons, 'w : volt', on_pre='v_post += w')

        # Connect synapses based on adjacency matrix
        sources, targets = np.nonzero(self.adj_matrix)
        self.synapses.connect(i=sources, j=targets)

        # Set weights: use log-scaling to compress the large dynamic range of
        # synapse counts (single digits to 700+). This works well for the
        # population-coded pathways (e.g. LC4/LPLC2 -> GF), where hundreds of
        # neurons converge and threshold-crossing is a matter of summation.
        synapse_counts = self.adj_matrix[sources, targets].astype(float)
        log_weights = np.log1p(synapse_counts)
        log_max = np.log1p(float(max_synapses))
        weight_mV = (log_weights / log_max) * (w_max / mV)

        # GF's direct synapses onto TTMn/DN are the opposite regime: a single
        # presynaptic partner, not a convergent population. Physiologically
        # this is the classic "giant synapse" of the escape circuit -- a
        # mixed electrical+chemical junction known for ~one-for-one, near
        # zero-latency following (Trimarchi & Schneiderman 1993; Allen et al.
        # 2007) -- so log-compressing it against hundreds of unrelated brain
        # synapses would crush it below firing threshold regardless of its
        # real reliability. Give these specific edges a flat, comfortably
        # suprathreshold weight (threshold is 20 mV above rest) instead.
        group_of_index = np.empty(self.N, dtype=object)
        for meta in self.metadata:
            group_of_index[meta['index']] = meta['group']

        gf_to_motor = (group_of_index[sources] == 'GF') & np.isin(group_of_index[targets], ['TTMn', 'DN'])
        w_gf_motor_mV = 22.0
        weight_mV[gf_to_motor] = w_gf_motor_mV

        self.synapses.w = weight_mV * mV
        
        # Monitors - monitor ALL neurons (brian2 requires contiguous indices for subgroups)
        self.spike_monitor = SpikeMonitor(self.neurons)
        
        # Create Brian Network object
        self.network = Network(self.neurons, self.synapses, self.spike_monitor)

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
        # Reset all currents
        self.neurons.I = 0 * nA
        
        # Threshold current is ~200 pA. Scale input 0-1 to 0-1 nA (well above threshold).
        max_current = 1.0  # nA
        
        if visual_input is not None and visual_input > 0:
            self.neurons.I[self.sensory_visual_indices] = (visual_input * max_current) * nA
                
        if mechanosensory_input is not None and mechanosensory_input > 0:
            self.neurons.I[self.sensory_mechano_indices] = (mechanosensory_input * max_current) * nA
                
        # Run step
        self.network.run(duration_ms * ms)

        return self.get_motor_output(window_ms=self.readout_window_ms)

    def get_motor_output(self, window_ms=None):
        """
        Calculate spike rates for motor neurons.

        Args:
            window_ms (float, optional): If given, only counts spikes in the
                trailing window_ms of simulated time (a rolling recent rate).
                If None, averages over the network's entire history since
                creation/reset instead. That cumulative average is fine for a
                short one-shot run (e.g. the demo below), but for a
                continuously-running control loop it makes the readout less
                and less responsive to new activity the longer the process
                has been running, since old quiet periods keep diluting the
                denominator -- always pass a window in that case (step()
                does this automatically via self.readout_window_ms).

        Returns:
            dict: {'escape_magnitude': float, 'spike_rates': dict}
        """
        rates = {}
        total_spikes = 0

        run_time = self.network.t
        if run_time > 0 * ms:
            if window_ms is not None:
                window_start = max(0 * ms, run_time - window_ms * ms)
                duration_s = (run_time - window_start) / second
                in_window = self.spike_monitor.t >= window_start
                spike_indices = self.spike_monitor.i[in_window]
            else:
                duration_s = run_time / second
                spike_indices = self.spike_monitor.i

            for motor_idx in self.motor_indices:
                spikes = np.sum(spike_indices == motor_idx)
                rate = spikes / duration_s if duration_s > 0 else 0.0
                rates[motor_idx] = rate
                total_spikes += spikes
        else:
            duration_s = 1.0

        # Simple heuristic for escape magnitude
        num_motor = len(self.motor_indices) if len(self.motor_indices) > 0 else 1
        escape_magnitude = (total_spikes / duration_s) / num_motor if duration_s > 0 else 0.0
        
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
        
        # Clear and replace monitor
        self.network.remove(self.spike_monitor)
        self.spike_monitor = SpikeMonitor(self.neurons)
        self.network.add(self.spike_monitor)
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
