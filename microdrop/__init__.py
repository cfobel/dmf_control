"""
Copyright 2011 Ryan Fobel

This file is part of dmf_control_board.

dmf_control_board is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

dmf_control_board is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with dmf_control_board.  If not, see <http://www.gnu.org/licenses/>.
"""

import threading
import time
import math
from cPickle import dumps, loads
from copy import deepcopy

import gtk
import numpy as np

from plugins.dmf_control_board import *
from plugins.dmf_control_board.microdrop.feedback import *
from plugin_manager import IPlugin, IWaveformGenerator, SingletonPlugin, \
    implements, emit_signal


class WaitForFeedbackMeasurement(threading.Thread):
    def __init__(self, control_board, state, feedback_options):
        self.control_board = control_board
        self.state = state
        self.feedback_options = feedback_options
        self.results = None
        threading.Thread.__init__(self)
  
    def run(self):
        self.results = self.control_board.measure_impedance(
                            self.feedback_options.sampling_time_ms,
                            self.feedback_options.n_samples,
                            self.feedback_options.delay_between_samples_ms,
                            self.state)


class DmfControlBoardPlugin(SingletonPlugin):
    """
    This class is automatically registered with the PluginManager.
    """
    implements(IPlugin)
    implements(IWaveformGenerator)

    def __init__(self):
        self.control_board = DmfControlBoard()
        self.name = "wheelerlab.arduino_dmf_control_board_" + \
            self.control_board.host_hardware_version()        
        self.version = self.control_board.host_software_version()
        self.url = self.control_board.host_url()
        self.app = None
        self.steps = [] # list of steps in the protocol
        self.current_state = FeedbackOptions()
        self.feedback_options_controller = None
        self.feedback_results_controller = None

    def on_app_init(self, app):
        """
        Handler called once when the Microdrop application starts.
        """
        self.app = app
        self.feedback_options_controller = FeedbackOptionsController(self)
        self.feedback_results_controller = FeedbackResultsController(self)
        
        try:
            self.app.control_board = self.control_board
            self.control_board.connect()
            name = self.control_board.name()
            version = self.control_board.hardware_version()

            # reflash the firmware if it is not the right version
            if self.control_board.host_software_version() != \
                self.control_board.software_version():
                try:
                    self.control_board.flash_firmware()
                except:
                    self.error("Problem flashing firmware")
            firmware = self.control_board.software_version()
            self.app.main_window_controller.label_connection_status.set_text(name + " v" + version + \
                "\n\tFirmware: " + str(firmware))
        except ConnectionError, why:
            print why
        
    def current_step_options(self):
        """
        Return a FeedbackOptions object for the current step in the protocol.
        If none exists yet, create a new one.
        """
        step = self.app.protocol.current_step_number
        if len(self.steps)<=step:
            # initialize the list if it is empty
            if len(self.steps)==0:
                self.steps = [FeedbackOptions()]
            # pad the state list with copies of the last known state
            for i in range(0,step-len(self.steps)+1):
                self.steps.append(deepcopy(self.steps[-1]))
        return self.steps[step]

    def on_delete_protocol_step(self):
        """
        Handler called whenever a protocol step is deleted.
        """
        if len(self.steps) > 1:
            del self.steps[self.app.protocol.current_step_number]
        else: # reset first step
            self.steps = [FeedbackOptions()]

    def on_insert_protocol_step(self):
        """
        Handler called whenever a protocol step is inserted.
        """
        self.steps.insert(self.app.protocol.current_step_number,
                          deepcopy(self.current_step_options()))

    def on_protocol_update(self, data):
        """
        Handler called whenever the current protocol step changes.
        """
        self.feedback_options_controller.update()
        options = self.current_step_options()
        if self.control_board.connected() and \
            (self.app.realtime_mode or self.app.running):
            emit_signal("set_voltage",
                        float(self.app.protocol.current_step().voltage)* \
                        math.sqrt(2)/100,
                        interface=IWaveformGenerator)
            emit_signal("set_frequency",
                        float(self.app.protocol.current_step().frequency),
                        interface=IWaveformGenerator)
            self.current_state.feedback_enabled = options.feedback_enabled
            state = self.app.protocol.current_step().state_of_channels
            max_channels = self.control_board.number_of_channels() 
            if len(state) >  max_channels:
                state = state[0:max_channels]
            elif len(state) < max_channels:
                state = np.concatenate([state,
                                        np.zeros(max_channels-len(state),
                                                 int)])
            else:
                assert(len(state)==max_channels)

            if options.feedback_enabled:
                thread = WaitForFeedbackMeasurement(self.control_board,
                                                    state,
                                                    options)
                thread.start()
                while thread.is_alive():
                    while gtk.events_pending():
                        gtk.main_iteration()
                results = FeedbackResults(options,
                                          thread.results,
                                          self.app.protocol.current_step().voltage)
                data["FeedbackResults"] = dumps(results)
            else:
                self.control_board.set_state_of_all_channels(state)
                t = time.time()
                while time.time()-t < \
                    self.app.protocol.current_step().duration/1000.0:
                    while gtk.events_pending():
                        gtk.main_iteration()
                        
            """
            start_freq = self.textentry_start_freq.get_text()
            end_freq = self.textentry_end_freq.get_text()
            number_of_steps = self.textentry_n_steps.get_text()
            if is_float(start_freq) == False:
                self.app.main_window_controller.error("Invalid start frequency.")
            elif is_float(end_freq) == False:
                self.app.main_window_controller.error("Invalid end frequency.")
            elif is_int(number_of_steps) == False or number_of_steps < 1:
                self.app.main_window_controller.error("Invalid number of steps.")
            elif end_freq < start_freq:
                self.app.main_window_controller.error("End frequency must be greater than the start frequency.")
            else:
                frequencies = np.logspace(np.log10(float(start_freq)),
                                          np.log10(float(end_freq)),
                                          int(number_of_steps))
                for frequency in frequencies:
                    self.app.protocol.current_step().frequency = frequency*1e3
                    self.app.protocol.copy_step()
            """

    def on_app_exit(self):
        """
        Handler called just before the Microdrop application exists. 
        """
        pass
    
    def on_protocol_save(self):
        """
        Handler called when a protocol is saved.
        """
        self.app.protocol.plugin_data[self.name] = (self.version, dumps(self.steps))
    
    def on_protocol_load(self, version, data):
        """
        Handler called when a protocol is loaded.
        """
        self.steps = loads(data)
    
    def on_protocol_run(self):
        """
        Handler called when a protocol starts running.
        """
        if self.control_board.connected()==False:
            self.app.main_window_controller.warning("Warning: no control "
                "board connected.")
        elif self.control_board.number_of_channels() < \
            self.app.protocol.n_channels:
            self.app.main_window_controller.warning("Warning: currently "
                "connected board does not have enough channels for this "
                "protocol.")

    
    def on_protocol_pause(self):
        """
        Handler called when a protocol is paused.
        """
        pass
        
    def on_protocol_changed(self, protocol):
        """
        Handler called when the protocol changes (e.g., when a new protocol
        is loaded).
        """
        if len(protocol)==1:
            self.steps = []

    def on_dmf_device_changed(self, dmf_device):
        """
        Handler called when the DMF device changes (e.g., when a new device
        is loaded).
        """
        pass

    def on_experiment_log_changed(self, id):
        """
        Handler called when the experiment log changes (e.g., when a protocol
        finishes running.
        """
        pass
        
    def on_experiment_log_selection_changed(self, data):
        """
        Handler called whenever the experiment log selection changes.

        Parameters:
            data : dictionary of experiment log data for the selected steps
        """
        self.feedback_results_controller.on_experiment_log_selection_changed(data)
        
    def set_voltage(self, voltage):
        """
        Set the waveform voltage.
        
        Parameters:
            voltage : RMS voltage
        """
        self.control_board.set_waveform_voltage(voltage)
    
    def set_frequency(self, frequency):
        """
        Set the waveform frequency.
        
        Parameters:
            frequency : frequency in Hz
        """
        self.control_board.set_waveform_frequency(frequency)