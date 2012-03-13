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

import os
import math

import logging
import gtk
import numpy as np
import matplotlib
import matplotlib.mlab as mlab
if os.name=='nt':
    matplotlib.rc('font', **{'family':'sans-serif','sans-serif':['Arial']})
from matplotlib.figure import Figure
from path import path
try:
    from matplotlib.backends.backend_gtkagg import FigureCanvasGTKAgg as FigureCanvasGTK
    from matplotlib.backends.backend_gtkagg import NavigationToolbar2GTKAgg as NavigationToolbar
except RuntimeError:
    if PROGRAM_LAUNCHED:
        raise
    else:
        logging.info('Skipping error!')


try:
    from ...dmf_control_board import *
except:
    # Raise the exception(s) if we're running the program (these exceptions
    # are expected when generating documentation with doxygen, so in that case
    # we can safely ignore them).
    if utility.PROGRAM_LAUNCHED:
        raise
from utility import SetOfInts, Version, VersionError, FutureVersionError
from utility.gui import textentry_validate, combobox_set_model_from_list, \
    combobox_get_active_text
from plugin_manager import emit_signal, IWaveformGenerator, IPlugin
from app_context import get_app


def feedback_signal(p, frequency, Z):
    """p[0]=C, p[1]=R"""
    return np.abs(p[1]/(Z+p[1]+Z*p[1]*2*np.pi*p[0]*complex(0,1)*frequency))


class RetryAction():
    capacitance_threshold = 0
    def __init__(self,
                 capacitance_threshold=None,
                 increase_voltage=None,
                 max_repeats=None):
        if capacitance_threshold:
            self.capacitance_threshold = capacitance_threshold
        else:
            self.capacitance_threshold = self.__class__.capacitance_threshold
        if increase_voltage:
            self.increase_voltage = increase_voltage
        else:
            self.increase_voltage = 0
        if max_repeats:
            self.max_repeats = max_repeats
        else:
            self.max_repeats = 3


class SweepFrequencyAction():
    def __init__(self,
                 start_frequency=None,
                 end_frequency=None,
                 n_frequency_steps=None):
        if start_frequency:
            self.start_frequency = start_frequency
        else:
            self.start_frequency = 1e2
        if end_frequency:
            self.end_frequency = end_frequency
        else:
            self.end_frequency = 30e3
        if n_frequency_steps:
            self.n_frequency_steps = n_frequency_steps
        else:
            self.n_frequency_steps = 30


class SweepVoltageAction():
    def __init__(self,
                 start_voltage=None,
                 end_voltage=None,
                 n_voltage_steps=None):
        if start_voltage:
            self.start_voltage = start_voltage
        else:
            self.start_voltage = 5
        if end_voltage:
            self.end_voltage = end_voltage
        else:
            self.end_voltage = 100
        if n_voltage_steps:
            self.n_voltage_steps = n_voltage_steps
        else:
            self.n_voltage_steps = 20


class SweepElectrodesAction():
    def __init__(self,
                 channels=None):
        if channels:
            self.channels = channels
        else:
            self.channels = SetOfInts()
            app = get_app()
            for e in app.dmf_device.electrodes.values():
                self.channels.update(e.channels)

class FeedbackOptions():
    """
    This class stores the feedback options for a single step in the protocol.
    """
    def __init__(self, feedback_enabled=None,
                 sampling_time_ms=None,
                 n_samples=None,
                 delay_between_samples_ms=None,
                 action=None):
        if feedback_enabled:
            self.feedback_enabled = feedback_enabled
        else:
            self.feedback_enabled = False
        if sampling_time_ms:
            self.sampling_time_ms = sampling_time_ms
        else:
            self.sampling_time_ms = 10
        if n_samples:
            self.n_samples = n_samples
        else:
            self.n_samples = 10
        if delay_between_samples_ms:
            self.delay_between_samples_ms = delay_between_samples_ms
        else:
            self.delay_between_samples_ms = 0
        if action:
            self.action = action
        else:
            self.action = RetryAction()


class FeedbackOptionsController():
    def __init__(self, plugin):
        self.plugin = plugin
        self.builder = gtk.Builder()
        app = get_app()
        self.builder.add_from_file(
            path(app.config['plugins']['directory']).joinpath('dmf_control_board',
                        'microdrop', 'glade', 'feedback_options.glade'))
        self.window = self.builder.get_object("window")
        self.builder.connect_signals(self)
        self.window.set_title("Feedback Options")
        menu_item = gtk.MenuItem("Feedback Options")
        app.main_window_controller.menu_tools.append(menu_item)
        menu_item.connect("activate", self.on_window_show)
        menu_item.show()
        
        menu_item = gtk.MenuItem("Calibrate feedback")
        app.dmf_device_controller.popup.append(menu_item)
        menu_item.connect("activate", self.on_calibrate_feedback)
        menu_item.show()

    def on_window_show(self, widget, data=None):
        """
        Handler called when the user clicks on "Feedback Options" in the "Tools"
        menu.
        """
        self.window.show()

    def on_window_delete_event(self, widget, data=None):
        """
        Handler called when the user closes the "Feedback Options" window. 
        """
        self.window.hide()
        return True

    def on_calibrate_feedback(self, widget, data=None):
        app = get_app()
        if self.plugin.control_board.connected():
            electrode = \
                app.dmf_device_controller.last_electrode_clicked
            area = electrode.area() * app.dmf_device.scale
            current_state = self.plugin.control_board.state_of_all_channels()
            state = np.zeros(len(current_state))

            if self.plugin.control_board.number_of_channels() < \
                max(electrode.channels):
                logging.warning("Error: "
                    "currently connected board does not have enough channels "
                    "to perform calibration on this electrode.")
                return

            state[electrode.channels]=1
            options = FeedbackOptions(feedback_enabled=True,
                                      sampling_time_ms=10,
                                      n_samples=1,
                                      delay_between_samples_ms=0,
                                      action=RetryAction())
            step = app.protocol.current_step()
            dmf_options = step.get_data(self.plugin.name)
            voltage = dmf_options.voltage
            frequency = dmf_options.frequency
            emit_signal("set_frequency", frequency,
                        interface=IWaveformGenerator)
            emit_signal("set_voltage", voltage, interface=IWaveformGenerator)
            (V_hv, hv_resistor, V_fb, fb_resistor) = \
                self.plugin.measure_impedance(state, options)
            results = FeedbackResults(options,
                V_hv, hv_resistor,
                V_fb, fb_resistor,
                area, frequency,
                voltage,
                self.plugin.control_board.calibration)
            logging.info('max(results.capacitance())/area=%s' % (max(results.capacitance()) / area))
            self.plugin.control_board.set_state_of_all_channels(current_state)
            RetryAction.capacitance_threshold =\
                max(results.capacitance()) / area * .95

    def on_button_feedback_enabled_toggled(self, widget, data=None):
        """
        Handler called when the "Feedback enabled" check box is toggled. 
        """
        app = get_app()
        all_options = self.plugin.get_step_options()
        options = all_options.feedback_options
        options.feedback_enabled = widget.get_active()
        emit_signal('on_step_options_changed',
                    [self.plugin.name, app.protocol.current_step_number],
                    interface=IPlugin)

    def on_step_options_changed(self, plugin_name, step_number):
        app = get_app()
        if(self.plugin.name == plugin_name) \
        and app.protocol.current_step_number == step_number:
            all_options = self.plugin.get_step_options(step_number)
            options = all_options.feedback_options
            self._set_gui_sensitive(options)
            self._update_gui_state(options)

    def _update_gui_state(self, options):
        # update the state of the "Feedback enabled" check button        
        button = self.builder.get_object("button_feedback_enabled")
        if options.feedback_enabled != button.get_active():
            # Temporarily disable radio-button toggled signal handler to avoid
            # infinite loop (handler emits signal that results in this method
            # being called).
            button.handler_block_by_func(self.on_button_feedback_enabled_toggled)
            button.set_active(options.feedback_enabled)
            button.handler_unblock_by_func(self.on_button_feedback_enabled_toggled)

        # update the retry action parameters
        retry = (options.action.__class__ == RetryAction)
        if retry:
            self.builder.get_object("textentry_capacitance_threshold"). \
                set_text(str(options.action.capacitance_threshold))
            self.builder.get_object("textentry_increase_voltage"). \
                set_text(str(options.action.increase_voltage))
            self.builder.get_object("textentry_max_repeats").set_text(
                str(options.action.max_repeats))
        else:
            self.builder.get_object("textentry_capacitance_threshold"). \
                set_text("")
            self.builder.get_object("textentry_increase_voltage").set_text("")
            self.builder.get_object("textentry_max_repeats").set_text("")
        button = self.builder.get_object("radiobutton_retry")
        if retry != button.get_active():
            # Temporarily disable toggled signal handler (see above)
            button.handler_block_by_func(self.on_radiobutton_retry_toggled)
            button.set_active(retry)
            button.handler_unblock_by_func(self.on_radiobutton_retry_toggled)

        sweep_frequency = (options.action.__class__ == SweepFrequencyAction)
        # update the sweep frequency action parameters
        if sweep_frequency:
            self.builder.get_object("textentry_start_frequency"). \
                set_text(str(options.action.start_frequency/1000.0))
            self.builder.get_object("textentry_end_frequency").set_text(
                str(options.action.end_frequency/1000.0))
            self.builder.get_object("textentry_n_frequency_steps").set_text(
                str(str(options.action.n_frequency_steps)))
        else:
            self.builder.get_object("textentry_start_frequency").set_text("")
            self.builder.get_object("textentry_end_frequency").set_text("")
            self.builder.get_object("textentry_n_frequency_steps").set_text("")
        button = self.builder.get_object("radiobutton_sweep_frequency")
        if sweep_frequency != button.get_active():
            # Temporarily disable toggled signal handler (see above)
            button.handler_block_by_func(self.on_radiobutton_sweep_frequency_toggled)
            button.set_active(sweep_frequency)
            button.handler_unblock_by_func(self.on_radiobutton_sweep_frequency_toggled)

        sweep_voltage = (options.action.__class__ == SweepVoltageAction)
        # update the sweep voltage action parameters
        if sweep_voltage:
            self.builder.get_object("textentry_start_voltage"). \
                set_text(str(options.action.start_voltage))
            self.builder.get_object("textentry_end_voltage").set_text(
                str(options.action.end_voltage))
            self.builder.get_object("textentry_n_voltage_steps").set_text(
                str(str(options.action.n_voltage_steps)))
        else:
            self.builder.get_object("textentry_start_voltage").set_text("")
            self.builder.get_object("textentry_end_voltage").set_text("")
            self.builder.get_object("textentry_n_voltage_steps").set_text("")
        button = self.builder.get_object("radiobutton_sweep_voltage")
        if sweep_voltage != button.get_active():
            # Temporarily disable toggled signal handler (see above)
            button.handler_block_by_func(self.on_radiobutton_sweep_voltage_toggled)
            button.set_active(sweep_voltage)
            button.handler_unblock_by_func(self.on_radiobutton_sweep_voltage_toggled)

        sweep_electrodes = (options.action.__class__ == SweepElectrodesAction)
        # update the sweep electrodes action parameters
        if sweep_electrodes:
            self.builder.get_object("textentry_channels"). \
                set_text(str(options.action.channels))
        else:
            self.builder.get_object("textentry_channels").set_text("")
        button = self.builder.get_object("radiobutton_sweep_electrodes")
        if sweep_electrodes != button.get_active():
            # Temporarily disable toggled signal handler (see above)
            button.handler_block_by_func(self.on_radiobutton_sweep_electrodes_toggled)
            button.set_active(sweep_electrodes)
            button.handler_unblock_by_func(self.on_radiobutton_sweep_electrodes_toggled)
        
        # on_textentry_sampling_time_ms_changed
        self.builder.get_object("textentry_sampling_time_ms").set_text(
            str(options.sampling_time_ms))

        # on_textentry_n_samples_changed
        self.builder.get_object("textentry_n_samples").set_text(
            str(options.n_samples))

        # on_textentry_delay_between_samples_ms_changed
        self.builder.get_object("textentry_delay_between_samples_ms")\
            .set_text(str(options.delay_between_samples_ms))

    def _set_gui_sensitive(self, options):
        self.builder.get_object("textentry_sampling_time_ms")\
            .set_sensitive(options.feedback_enabled)
        self.builder.get_object("textentry_n_samples")\
            .set_sensitive(options.feedback_enabled)

        self.builder.get_object("textentry_delay_between_samples_ms")\
            .set_sensitive(options.feedback_enabled)
        self.builder.get_object("radiobutton_retry")\
            .set_sensitive(options.feedback_enabled)
        self.builder.get_object("radiobutton_sweep_frequency")\
            .set_sensitive(options.feedback_enabled)
        self.builder.get_object("radiobutton_sweep_voltage")\
            .set_sensitive(options.feedback_enabled)
        self.builder.get_object("radiobutton_sweep_electrodes")\
            .set_sensitive(options.feedback_enabled)

        retry = (options.action.__class__ == RetryAction)
        self.builder.get_object("textentry_capacitance_threshold")\
            .set_sensitive(options.feedback_enabled and retry)
        self.builder.get_object("textentry_increase_voltage")\
            .set_sensitive(options.feedback_enabled and retry)
        self.builder.get_object("textentry_max_repeats")\
            .set_sensitive(options.feedback_enabled and retry)

        sweep_frequency = (options.action.__class__ == SweepFrequencyAction)
        self.builder.get_object("textentry_start_frequency")\
            .set_sensitive(options.feedback_enabled and sweep_frequency)
        self.builder.get_object("textentry_end_frequency")\
            .set_sensitive(options.feedback_enabled and sweep_frequency)
        self.builder.get_object("textentry_n_frequency_steps")\
            .set_sensitive(options.feedback_enabled and sweep_frequency)

        sweep_voltage = (options.action.__class__ == SweepVoltageAction)
        self.builder.get_object("textentry_start_voltage")\
            .set_sensitive(options.feedback_enabled and sweep_voltage)
        self.builder.get_object("textentry_end_voltage")\
            .set_sensitive(options.feedback_enabled and sweep_voltage)
        self.builder.get_object("textentry_n_voltage_steps")\
            .set_sensitive(options.feedback_enabled and sweep_voltage)

        sweep_electrodes = (options.action.__class__ == SweepElectrodesAction)
        self.builder.get_object("textentry_channels")\
            .set_sensitive(options.feedback_enabled and sweep_electrodes)

    def on_radiobutton_retry_toggled(self, widget, data=None):
        """
        Handler called when the "Retry until capacitance..." radio button is
        toggled. 
        """
        logging.debug('retry was toggled %s'\
            % (('OFF', 'ON')[widget.get_active()]))
        app = get_app()
        all_options = self.plugin.get_step_options()
        options = all_options.feedback_options
        retry = widget.get_active()
        if retry and options.action.__class__ != RetryAction:
            options.action = RetryAction()
        if retry:
            emit_signal('on_step_options_changed',
                        [self.plugin.name, app.protocol.current_step_number],
                        interface=IPlugin)
        
    def on_radiobutton_sweep_frequency_toggled(self, widget, data=None):
        """
        Handler called when the "Sweep Frequency..." radio button is
        toggled. 
        """
        logging.debug('sweep_frequency was toggled %s'\
            % (('OFF', 'ON')[widget.get_active()]))
        app = get_app()
        all_options = self.plugin.get_step_options()
        options = all_options.feedback_options
        sweep_frequency = widget.get_active()
        if sweep_frequency and options.action.__class__ != SweepFrequencyAction:
            options.action = SweepFrequencyAction()
        if sweep_frequency:
            emit_signal('on_step_options_changed',
                        [self.plugin.name, app.protocol.current_step_number],
                        interface=IPlugin)
        
    def on_radiobutton_sweep_voltage_toggled(self, widget, data=None):
        """
        Handler called when the "Sweep Voltage..." radio button is
        toggled. 
        """
        logging.debug('sweep_voltage was toggled %s'\
            % (('OFF', 'ON')[widget.get_active()]))
        app = get_app()
        all_options = self.plugin.get_step_options()
        options = all_options.feedback_options
        sweep_voltage = widget.get_active() 
        if sweep_voltage and options.action.__class__!=SweepVoltageAction:
            options.action = SweepVoltageAction()
        if sweep_voltage:
            emit_signal('on_step_options_changed',
                        [self.plugin.name, app.protocol.current_step_number],
                        interface=IPlugin)

    def on_radiobutton_sweep_electrodes_toggled(self, widget, data=None):
        """
        Handler called when the "Sweep Electrodes..." radio button is
        toggled. 
        """
        logging.debug('sweep_electrodes was toggled %s'\
            % (('OFF', 'ON')[widget.get_active()]))
        app = get_app()
        all_options = self.plugin.get_step_options()
        options = all_options.feedback_options
        sweep_electrodes = widget.get_active() 
        if sweep_electrodes and options.action.__class__!= \
        SweepElectrodesAction:
            options.action = SweepElectrodesAction()
        if sweep_electrodes:
            emit_signal('on_step_options_changed',
                        [self.plugin.name, app.protocol.current_step_number],
                        interface=IPlugin)
            
    def on_textentry_sampling_time_ms_focus_out_event(self, widget, event):
        """
        Handler called when the "sampling time" text box loses focus. 
        """
        logging.info("on_textentry_sampling_time_ms_focus_out_event")
        self.on_textentry_sampling_time_ms_changed(widget)
        return False

    def on_textentry_sampling_time_ms_key_press_event(self, widget, event):
        """
        Handler called when the user presses a key within the "sampling time" text box. 
        """
        logging.info("on_textentry_sampling_time_ms_key_press_event")
        if event.keyval == 65293: # user pressed enter
            self.on_textentry_sampling_time_ms_changed(widget)
    
    def on_textentry_sampling_time_ms_changed(self, widget):
        """
        Update the sampling time value for the current step. 
        """
        logging.info("on_textentry_sampling_time_ms_changed")
        all_options = self.plugin.get_step_options()
        options = all_options.feedback_options
        options.sampling_time_ms = textentry_validate(widget,
                            options.sampling_time_ms, int)
        app = get_app()
        emit_signal('on_step_options_changed',
                    [self.plugin.name, app.protocol.current_step_number],
                    interface=IPlugin)

    def on_textentry_n_samples_focus_out_event(self, widget, event):
        """
        Handler called when the "number of samples" text box loses focus. 
        """
        self.on_textentry_n_samples_changed(widget)
        return False
    
    def on_textentry_n_samples_key_press_event(self, widget, event):
        """
        Handler called when the user presses a key within the "number of
        samples" text box. 
        """
        if event.keyval == 65293: # user pressed enter
            self.on_textentry_n_samples_changed(widget)
    
    def on_textentry_n_samples_changed(self, widget):
        """
        Update the number of samples value for the current step. 
        """
        app = get_app()
        all_options = self.plugin.get_step_options()
        options = all_options.feedback_options
        options.n_samples = textentry_validate(widget, options.n_samples, int)
        emit_signal('on_step_options_changed',
                    [self.plugin.name, app.protocol.current_step_number],
                    interface=IPlugin)

    def on_textentry_delay_between_samples_ms_focus_out_event(self,
                                                              widget,
                                                              event):
        """
        Handler called when the "delay between samples" text box loses focus. 
        """
        self.on_textentry_delay_between_samples_ms_changed(widget)
        return False
    
    def on_textentry_delay_between_samples_ms_key_press_event(self,
                                                              widget,
                                                              event):
        """
        Handler called when the user presses a key within the "delay between
        samples" text box. 
        """
        if event.keyval == 65293: # user pressed enter
            self.on_textentry_delay_between_samples_ms_changed(widget)
    
    def on_textentry_delay_between_samples_ms_changed(self, widget):
        """
        Update the delay between samples value for the current step. 
        """
        app = get_app()
        all_options = self.plugin.get_step_options()
        options = all_options.feedback_options
        options.delay_between_samples_ms = textentry_validate(widget,
                            options.delay_between_samples_ms, int)
        emit_signal('on_step_options_changed',
                    [self.plugin.name, app.protocol.current_step_number],
                    interface=IPlugin)
    
    def on_textentry_capacitance_threshold_focus_out_event(self,
                                                           widget,
                                                           event):
        """
        Handler called when the "capacitance threshold" text box loses focus. 
        """
        self.on_textentry_capacitance_threshold_changed(widget)
        return False
    
    def on_textentry_capacitance_threshold_key_press_event(self,
                                                           widget,
                                                           event):
        """
        Handler called when the user presses a key within the "capacitance
        threshold" text box. 
        """
        if event.keyval == 65293: # user pressed enter
            self.on_textentry_capacitance_threshold_changed(widget)
    
    def on_textentry_capacitance_threshold_changed(self, widget):
        """
        Update the capacitance threshold value for the current step. 
        """
        app = get_app()
        all_options = self.plugin.get_step_options()
        options = all_options.feedback_options
        options.action.capacitance_threshold = textentry_validate(widget,
                            options.action.capacitance_threshold, float)
        emit_signal('on_step_options_changed',
                    [self.plugin.name, app.protocol.current_step_number],
                    interface=IPlugin)

    def on_textentry_increase_voltage_focus_out_event(self, widget, event):
        """
        Handler called when the "increase voltage" text box loses focus. 
        """
        self.on_textentry_increase_voltage_changed(widget)
        return False
    
    def on_textentry_increase_voltage_key_press_event(self, widget, event):
        """
        Handler called when the user presses a key within the "increase
        voltage" text box. 
        """
        if event.keyval == 65293: # user pressed enter
            self.on_textentry_increase_voltage_changed(widget)
    
    def on_textentry_increase_voltage_changed(self, widget):
        """
        Update the increase voltage value for the current step. 
        """
        app = get_app()
        all_options = self.plugin.get_step_options()
        options = all_options.feedback_options
        options.action.increase_voltage = textentry_validate(widget,
                            options.action.increase_voltage, float)
        emit_signal('on_step_options_changed',
                    [self.plugin.name, app.protocol.current_step_number],
                    interface=IPlugin)
    
    def on_textentry_max_repeats_focus_out_event(self, widget, event):
        """
        Handler called when the "max repeats" text box loses focus. 
        """
        self.on_textentry_max_repeats_changed(widget)
        return False
    
    def on_textentry_max_repeats_key_press_event(self, widget, event):
        """
        Handler called when the user presses a key within the "max repeats"
        text box. 
        """
        if event.keyval == 65293: # user pressed enter
            self.on_textentry_max_repeats_changed(widget)
    
    def on_textentry_max_repeats_changed(self, widget):
        """
        Update the max repeats value for the current step. 
        """
        app = get_app()
        all_options = self.plugin.get_step_options()
        options = all_options.feedback_options
        options.action.max_repeats = textentry_validate(widget,
                            options.action.max_repeats, int)
        emit_signal('on_step_options_changed',
                    [self.plugin.name, app.protocol.current_step_number],
                    interface=IPlugin)
            
    def on_textentry_start_frequency_focus_out_event(self, widget, event):
        """
        Handler called when the "start frequency" text box loses focus. 
        """
        self.on_textentry_start_frequency_changed(widget)
        return False
    
    def on_textentry_start_frequency_key_press_event(self, widget, event):
        """
        Handler called when the user presses a key within the "start frequency"
        text box. 
        """
        if event.keyval == 65293: # user pressed enter
            self.on_textentry_start_frequency_changed(widget)
    
    def on_textentry_start_frequency_changed(self, widget):
        """
        Update the start frequency value for the current step. 
        """
        app = get_app()
        all_options = self.plugin.get_step_options()
        options = all_options.feedback_options
        options.action.start_frequency = textentry_validate(widget,
                            options.action.start_frequency / 1e3, float) * 1e3
        emit_signal('on_step_options_changed',
                    [self.plugin.name, app.protocol.current_step_number],
                    interface=IPlugin)

    def on_textentry_end_frequency_focus_out_event(self, widget, event):
        """
        Handler called when the "end frequency" text box loses focus. 
        """
        self.on_textentry_end_frequency_changed(widget)
        return False
    
    def on_textentry_end_frequency_key_press_event(self, widget, event):
        """
        Handler called when the user presses a key within the "end frequency"
        text box. 
        """
        if event.keyval == 65293: # user pressed enter
            self.on_textentry_end_frequency_changed(widget)
    
    def on_textentry_end_frequency_changed(self, widget):
        """
        Update the end frequency value for the current step. 
        """
        app = get_app()
        all_options = self.plugin.get_step_options()
        options = all_options.feedback_options
        options.action.end_frequency = textentry_validate(widget,
                            options.action.end_frequency / 1e3, float) * 1e3
        emit_signal('on_step_options_changed',
                    [self.plugin.name, app.protocol.current_step_number],
                    interface=IPlugin)

    def on_textentry_n_frequency_steps_focus_out_event(self, widget, event):
        """
        Handler called when the "number of frequency steps" text box loses focus. 
        """
        self.on_textentry_n_frequency_steps_changed(widget)
        return False
    
    def on_textentry_n_frequency_steps_key_press_event(self, widget, event):
        """
        Handler called when the user presses a key within the "number of
        frequency steps" text box. 
        """
        if event.keyval == 65293: # user pressed enter
            self.on_textentry_n_frequency_steps_changed(widget)
    
    def on_textentry_n_frequency_steps_changed(self, widget):
        """
        Update the number of frequency steps value for the current step. 
        """
        app = get_app()
        all_options = self.plugin.get_step_options()
        options = all_options.feedback_options
        options.action.n_frequency_steps = textentry_validate(widget,
                            options.action.n_frequency_steps, float)
        emit_signal('on_step_options_changed',
                    [self.plugin.name, app.protocol.current_step_number],
                    interface=IPlugin)

    def on_textentry_start_voltage_focus_out_event(self, widget, event):
        """
        Handler called when the "start voltage" text box loses focus. 
        """
        self.on_textentry_start_voltage_changed(widget)
        return False
    
    def on_textentry_start_voltage_key_press_event(self, widget, event):
        """
        Handler called when the user presses a key within the "start voltage"
        text box. 
        """
        if event.keyval == 65293: # user pressed enter
            self.on_textentry_start_voltage_changed(widget)
    
    def on_textentry_start_voltage_changed(self, widget):
        """
        Update the start voltage value for the current step. 
        """
        app = get_app()
        all_options = self.plugin.get_step_options()
        options = all_options.feedback_options
        options.action.start_voltage = textentry_validate(widget,
                            options.action.start_voltage, float)
        emit_signal('on_step_options_changed',
                    [self.plugin.name, app.protocol.current_step_number],
                    interface=IPlugin)

    def on_textentry_end_voltage_focus_out_event(self, widget, event):
        """
        Handler called when the "end voltage" text box loses focus. 
        """
        self.on_textentry_end_voltage_changed(widget)
        return False
    
    def on_textentry_end_voltage_key_press_event(self, widget, event):
        """
        Handler called when the user presses a key within the "end voltage"
        text box. 
        """
        if event.keyval == 65293: # user pressed enter
            self.on_textentry_end_voltage_changed(widget)
    
    def on_textentry_end_voltage_changed(self, widget):
        """
        Update the end voltage value for the current step. 
        """
        app = get_app()
        all_options = self.plugin.get_step_options()
        options = all_options.feedback_options
        options.action.end_voltage = textentry_validate(widget,
                            options.action.end_voltage, float)
        emit_signal('on_step_options_changed',
                    [self.plugin.name, app.protocol.current_step_number],
                    interface=IPlugin)

    def on_textentry_n_voltage_steps_focus_out_event(self, widget, event):
        """
        Handler called when the "number of voltage steps" text box loses focus. 
        """
        self.on_textentry_n_voltage_steps_changed(widget)
        return False
    
    def on_textentry_n_voltage_steps_key_press_event(self, widget, event):
        """
        Handler called when the user presses a key within the "number of
        voltage steps" text box. 
        """
        if event.keyval == 65293: # user pressed enter
            self.on_textentry_n_voltage_steps_changed(widget)
    
    def on_textentry_n_voltage_steps_changed(self, widget):
        """
        Update the number of voltage steps value for the current step. 
        """
        app = get_app()
        all_options = self.plugin.get_step_options()
        options = all_options.feedback_options
        options.action.n_voltage_steps = textentry_validate(widget,
                            options.action.n_voltage_steps, float)
        emit_signal('on_step_options_changed',
                    [self.plugin.name, app.protocol.current_step_number],
                    interface=IPlugin)

    def on_textentry_channels_focus_out_event(self, widget, event):
        """
        Handler called when the "electrodes" text box loses focus. 
        """
        self.on_textentry_channels_changed(widget)
        return False
    
    def on_textentry_channels_key_press_event(self, widget, event):
        """
        Handler called when the user presses a key within the "electrodes"
        text box. 
        """
        if event.keyval == 65293: # user pressed enter
            self.on_textentry_channels_changed(widget)
    
    def on_textentry_channels_changed(self, widget):
        """
        Update the electrodes value for the current step. 
        """
        app = get_app()
        all_options = self.plugin.get_step_options()
        options = all_options.feedback_options
        try:
            channels = SetOfInts(widget.get_text())
            assert(min(channels)>=0)
            options.action.channels = channels
            emit_signal('on_step_options_changed',
                        [self.plugin.name, app.protocol.current_step_number],
                        interface=IPlugin)
        except:
            widget.set_text(str(options.action.channels))


class FeedbackResults():
    """
    This class stores the impedance results for a single step in the protocol.
    """
    class_version = str(Version(0,1))
    
    def __init__(self,
                 options,
                 V_hv,
                 hv_resistor,
                 V_fb,
                 fb_resistor,
                 area,
                 frequency,
                 V_total,
                 calibration):
        self.options = options
        self.area = area
        self.frequency = frequency
        self.V_hv = V_hv
        self.hv_resistor = hv_resistor
        self.V_fb = V_fb
        self.fb_resistor = fb_resistor
        self.time = np.array(range(0,self.options.n_samples)) * \
            (self.options.sampling_time_ms + \
            self.options.delay_between_samples_ms)
        self._V_total = V_total
        self.calibration = calibration
        self.version = self.class_version

    def _upgrade(self):
        """
        Upgrade the serialized object if necessary.

        Raises:
            FutureVersionError: file was written by a future version of the
                software.
        """
        logging.debug('[FeedbackResults]._upgrade()')
        if hasattr(self, 'version'):
            version = Version.fromstring(self.version)
        else:
            version = Version(0)
        logging.debug('[FeedbackResults] version=%s, class_version=%s' % \
                     (str(version), self.class_version))
        if version > Version.fromstring(self.class_version):
            logging.debug('[FeedbackResults] version>class_version')
            raise FutureVersionError(Version.fromstring(self.class_version),
                                     version)
        elif version < Version.fromstring(self.class_version):
            if version < Version(0,1):
                self.calibration = FeedbackCalibration()
                self.version = str(Version(0,1))
                logging.info('[FeedbackResults] upgrade to version %s' % \
                            self.version)
        # else the versions are equal and don't need to be upgraded

    def __setstate__(self, state):
        self.__dict__ = state
        self._upgrade()
        
    def __getstate__(self):
        for k, v in self.__dict__.items():
            if isinstance(v, np.ndarray):
                self.__dict__[k] = v.tolist()
        return self.__dict__

    def V_total(self):
        T = feedback_signal([self.calibration.C_hv[self.hv_resistor],
                             self.calibration.R_hv[self.hv_resistor]],
                            self.frequency, 10e6)
        return self.V_hv/T

    def Z_device(self):
        R_fb = self.calibration.R_fb[self.fb_resistor]
        C_fb = self.calibration.C_fb[self.fb_resistor]
        return R_fb/np.sqrt(1+np.square(R_fb*C_fb*self.frequency*2*math.pi))* \
            (self.V_total()/self.V_fb - 1)
        
    def min_impedance(self):
        return min(self.Z_device())
    
    def capacitance(self):
        return 1.0/(2*math.pi*self.frequency*self.Z_device())
    
    def dxdt(self):
        """
        # remove outliers
        ind = np.nonzero(abs(Z-smooth(Z))/Z>10)[0]
        for j in range(len(ind)-1, -1, -1):
            Z = np.concatenate([Z[:ind[j]],Z[ind[j]+1:]])
            t = np.concatenate([t[:ind[j]],t[ind[j]+1:]])
        """
        window_len = 9
        dt = np.diff(self.time)*1./1000
        dZdt = self.smooth(np.diff(self.Z_device()), window_len) / dt
        return -dZdt / self.Z_device()[:-1]**2/(2*np.pi*self.frequency* \
               self.capacitance()[-1]/np.sqrt(self.area))

    def smooth(self, x, window_len=11, window='hanning'):
        """smooth the data using a window with requested size.
        
        This method is based on the convolution of a scaled window with the signal.
        
        :param x: the input signal 
        :param window_len: the dimension of the smoothing window; should be an odd integer
        :param window: the type of window from 'flat', 'hanning', 'hamming', 'bartlett', 'blackman'.  'flat' will produce a moving average smoothing.
    
        :returns: the smoothed signal
            
        **Usage**::
    
        >>t=linspace(-2,2,0.1)
        >>x=sin(t)+randn(len(t))*0.1
        >>y=smooth(x)
        
        .. seealso:: numpy.hanning, numpy.hamming, numpy.bartlett, numpy.blackman, numpy.convolve, scipy.signal.lfilter
     
        .. todo:: the window parameter could be the window itself if an array instead of a string   
        """
    
        if x.ndim != 1:
            raise ValueError, "smooth only accepts 1 dimension arrays."
    
        if x.size < window_len:
            raise ValueError, "Input vector needs to be bigger than window size."
    
        if window_len<3:
            return x
    
        if not window in ['flat', 'hanning', 'hamming', 'bartlett', 'blackman']:
            raise ValueError, "Window is none of 'flat', 'hanning', 'hamming', 'bartlett', 'blackman'"
    
        s=np.r_[x[0]*np.ones(window_len),x,x[-1]*np.ones(window_len)]
        if window == 'flat': #moving average
            w=np.ones(window_len,'d')
        else:
            w=eval('np.'+window+'(window_len)')
    
        y=np.convolve(w/w.sum(),s,mode='valid')
        y = y[(window_len-1)/2+1:-(window_len-1)/2-1]
        return y


class SweepFrequencyResults():
    """
    This class stores the results for a frequency sweep.
    """
    class_version = str(Version(0,1))
    
    def __init__(self, options, area, V_total, calibration):
        self.options = options
        self.area = area
        self._V_total = V_total
        self.calibration = calibration
        self.frequency = []
        self.V_hv = []
        self.hv_resistor = []
        self.V_fb = []
        self.fb_resistor = []
        self.version = self.class_version

    def _upgrade(self):
        """
        Upgrade the serialized object if necessary.

        Raises:
            FutureVersionError: file was written by a future version of the
                software.
        """
        logging.debug('[SweepFrequencyResults]._upgrade()')
        if hasattr(self, 'version'):
            version = Version.fromstring(self.version)
        else:
            version = Version(0)
        logging.debug('[SweepFrequencyResults] version=%s, class_version=%s' % \
                     (str(version), self.class_version))
        if version > Version.fromstring(self.class_version):
            logging.debug('[SweepFrequencyResults] version>class_version')
            raise FutureVersionError(Version.fromstring(self.class_version),
                                     version)
        elif version < Version.fromstring(self.class_version):
            if version < Version(0,1):
                self.calibration = FeedbackCalibration()
                self.version = str(Version(0,1))
                logging.info('[SweepFrequencyResults] upgrade to version %s' % \
                            self.version)
        # else the versions are equal and don't need to be upgraded

    def __setstate__(self, state):
        self.__dict__ = state
        self._upgrade()

    def __getstate__(self):
        for k, v in self.__dict__.items():
            if isinstance(v, list):
                for i in range(len(v)):
                    if isinstance(self.__dict__[k][i], np.ndarray):
                        self.__dict__[k][i] = self.__dict__[k][i].tolist()
                    elif isinstance(self.__dict__[k][i], np.float64):
                        self.__dict__[k][i] = float(self.__dict__[k][i])
            elif isinstance(v, np.ndarray):
                self.__dict__[k] = v.tolist()
        return self.__dict__

    def add_frequency_step(self, frequency,
                           V_hv, hv_resistor,
                           V_fb, fb_resistor):
        self.frequency.append(frequency)
        self.V_hv.append(V_hv)
        self.hv_resistor.append(hv_resistor)
        self.V_fb.append(V_fb)
        self.fb_resistor.append(fb_resistor)

    def V_total(self):
        V = []
        for i in range(0, np.size(self.V_hv, 0)):
            T = feedback_signal([self.calibration.C_hv[self.hv_resistor[i]],
                                 self.calibration.R_hv[self.hv_resistor[i]]],
                                self.frequency[i], 10e6)
            V.append(np.array(self.V_hv[i])/T)
        return V

    def Z_device(self):
        Z = []
        V_total = self.V_total()
        for i in range(0, np.size(self.V_hv, 0)):
            R_fb = self.calibration.R_fb[self.fb_resistor[i]]
            Z.append(R_fb/np.sqrt(1+np.square(R_fb* \
                     self.calibration.C_fb[self.fb_resistor[i]]* \
                     self.frequency[i]*2*math.pi))*(V_total[i]/self.V_fb[i]-1))
        return Z
    
    def capacitance(self):
        frequency = np.reshape(np.array(self.frequency),
                               (len(self.frequency),1))
        frequency = np.repeat(frequency, np.size(self.Z_device(), 1), axis=1)
        return 1.0/(2*math.pi*frequency*self.Z_device())


class SweepVoltageResults():
    """
    This class stores the results for a frequency sweep.
    """
    class_version = str(Version(0,1))
    
    def __init__(self, options, area, frequency, calibration):
        self.options = options
        self.area = area
        self.frequency = frequency
        self.calibration = calibration
        self.voltage = []
        self.V_hv = []
        self.hv_resistor = []
        self.V_fb = []
        self.fb_resistor = []
        self.version = self.class_version

    def _upgrade(self):
        """
        Upgrade the serialized object if necessary.

        Raises:
            FutureVersionError: file was written by a future version of the
                software.
        """
        logging.debug('[SweepVoltageResults]._upgrade()')
        if hasattr(self, 'version'):
            version = Version.fromstring(self.version)
        else:
            version = Version(0)
        logging.debug('[SweepVoltageResults] version=%s, class_version=%s' % \
                     (str(version), self.class_version))
        if version > Version.fromstring(self.class_version):
            logging.debug('[SweepVoltageResults] version>class_version')
            raise FutureVersionError(Version.fromstring(self.class_version),
                                     version)
        elif version < Version.fromstring(self.class_version):
            if version < Version(0,1):
                self.calibration = FeedbackCalibration()
                self.version = str(Version(0,1))
                logging.info('[SweepVoltageResults] upgrade to version %s' % \
                            self.version)
        # else the versions are equal and don't need to be upgraded

    def __setstate__(self, state):
        self.__dict__ = state
        self._upgrade()

    def __getstate__(self):
        for k, v in self.__dict__.items():
            if isinstance(v, list):
                for i in range(len(v)):
                    if isinstance(self.__dict__[k][i], np.ndarray):
                        self.__dict__[k][i] = self.__dict__[k][i].tolist()
                    elif isinstance(self.__dict__[k][i], np.float64):
                        self.__dict__[k][i] = float(self.__dict__[k][i])
            elif isinstance(v, np.ndarray):
                self.__dict__[k] = v.tolist()
        return self.__dict__

    def add_voltage_step(self, voltage,
                         V_hv, hv_resistor,
                         V_fb, fb_resistor):
        self.voltage.append(voltage)
        self.V_hv.append(V_hv)
        self.hv_resistor.append(hv_resistor)
        self.V_fb.append(V_fb)
        self.fb_resistor.append(fb_resistor)        

    def V_total(self):
        V = []
        for i in range(0, np.size(self.V_hv, 0)):
            T = feedback_signal([self.calibration.C_hv[self.hv_resistor[i]],
                                 self.calibration.R_hv[self.hv_resistor[i]]],
                                self.frequency, 10e6)
            V.append(np.array(self.V_hv[i])/T)
        return V

    def Z_device(self):
        Z = []
        V_total = self.V_total()
        for i in range(0, np.size(self.V_hv, 0)):
            R_fb = self.calibration.R_fb[self.fb_resistor[i]]
            Z.append(R_fb/np.sqrt(1+np.square(R_fb* \
                     self.calibration.C_fb[self.fb_resistor[i]]* \
                     self.frequency*2*math.pi))*(V_total[i]/self.V_fb[i]-1))
        return Z

    def capacitance(self):
        return 1.0/(2*math.pi*self.frequency*np.array(self.Z_device()))


class FeedbackResultsController():
    def __init__(self, plugin):
        self.plugin = plugin
        self.builder = gtk.Builder()
        app = get_app()
        self.builder.add_from_file(
            path(app.config['plugins']['directory']).joinpath('dmf_control_board',
                                'microdrop', 'glade', 'feedback_results.glade'))
        self.window = self.builder.get_object("window")
        self.combobox_x_axis = self.builder.get_object("combobox_x_axis")
        self.combobox_y_axis = self.builder.get_object("combobox_y_axis")
        self.window.set_title("Feedback Results")
        self.builder.connect_signals(self)
        self.data = []

        menu_item = gtk.MenuItem("Feedback Results")
        app.main_window_controller.menu_view.append(menu_item)
        menu_item.connect("activate", self.on_window_show)
        menu_item.show()

        self.figure = Figure()   
        self.canvas = FigureCanvasGTK(self.figure)
        self.axis = self.figure.add_subplot(111)
        self.vbox = self.builder.get_object("vbox1")
        toolbar = NavigationToolbar(self.canvas, self.window)
        self.vbox.pack_start(self.canvas)
        self.vbox.pack_start(toolbar, False, False)
        combobox_set_model_from_list(self.combobox_x_axis,
                                     ["Time", "Frequency", "Voltage"])
        combobox_set_model_from_list(self.combobox_y_axis,
                                     ["Impedance", "Capacitance", "Velocity"])
        self.combobox_x_axis.set_active(0)
        self.combobox_y_axis.set_active(0)

    def on_window_show(self, widget, data=None):
        """
        Handler called when the user clicks on "Feedback Results" in the "View"
        menu.
        """
        self.window.show_all()

    def on_window_delete_event(self, widget, data=None):
        """
        Handler called when the user closes the "Feedback Results" window. 
        """
        self.window.hide()
        return True

    def on_combobox_x_axis_changed(self, widget, data=None):
        x_axis = combobox_get_active_text(self.combobox_x_axis)
        y_axis = combobox_get_active_text(self.combobox_y_axis)
        if x_axis=="Time":
            combobox_set_model_from_list(self.combobox_y_axis,
                                         ["Impedance", "Capacitance",
                                          "Velocity"])
        else:
            combobox_set_model_from_list(self.combobox_y_axis,
                                         ["Impedance", "Capacitance"])
        self.combobox_y_axis.set_active(0)
        self.update_plot()

    def on_combobox_y_axis_changed(self, widget, data=None):
        self.update_plot()

    def on_export_data_clicked(self, widget, data=None):
        dialog = gtk.FileChooserDialog(title="Export data",
                                       action=gtk.FILE_CHOOSER_ACTION_SAVE,
                                       buttons=(gtk.STOCK_CANCEL,
                                                gtk.RESPONSE_CANCEL,
                                                gtk.STOCK_SAVE,
                                                gtk.RESPONSE_OK))
        dialog.set_default_response(gtk.RESPONSE_OK)
        dialog.set_current_name("export.csv")
        filter = gtk.FileFilter()
        filter.set_name("*.csv")
        filter.add_pattern("*.csv")
        dialog.add_filter(filter)
        filter = gtk.FileFilter()
        filter.set_name("All files")
        filter.add_pattern("*")
        dialog.add_filter(filter)
        response = dialog.run()
        if response == gtk.RESPONSE_OK:
            filename = dialog.get_filename()
            logging.info("Exporting to file %s." % filename)
            try:
                with open(filename, 'w') as f:
                    f.write("\n".join(self.export_data))
            except Exception, e:
                logging.error("Problem exporting file. %s." % e)
        dialog.destroy()

    def on_experiment_log_selection_changed(self, data):
        """
        Handler called whenever the experiment log selection changes.

        :param data: experiment log data (list of dictionaries, one per step) for the selected steps
        """
        self.data = data
        self.update_plot()

    def update_plot(self):
        x_axis = combobox_get_active_text(self.combobox_x_axis)
        y_axis = combobox_get_active_text(self.combobox_y_axis)
        self.axis.cla()
        self.axis.grid(True)
        legend = []
        legend_loc = "upper right"
        self.export_data = []        
        if x_axis=="Time":
            self.axis.set_xlabel("Time (ms)")
            for row in self.data:
                if self.plugin.name in row.keys() and "FeedbackResults" in row[self.plugin.name].keys():
                    results = row[self.plugin.name]["FeedbackResults"]
                    self.export_data.append('step:, %d' % (row['core']["step"]+1))
                    self.export_data.append('step time (s):, %f' % (row['core']["time"]))
                    if y_axis=="Impedance":
                        self.axis.set_title("Impedance")
                        self.axis.set_ylabel(
                            "|Z$_{device}$(f=%.1e Hz)| ($\Omega$)" % \
                            results.frequency)
                        self.axis.plot(results.time,
                                       results.Z_device())
                        self.axis.set_yscale('log')
                        self.export_data.append('time (ms):, '+
                            ", ".join([str(x) for x in results.time]))
                        self.export_data.append('impedance (Ohms):, ' + 
                            ", ".join([str(x) for x in results.Z_device()]))
                    elif y_axis=="Capacitance":
                        self.axis.set_title("Capacitance/Area")
                        self.axis.set_ylabel("C$_{device}$ (F/mm$^2$)")
                        self.axis.plot(results.time,
                                       results.capacitance()/results.area)
                        legend_loc = "lower right"
                        self.export_data.append('time (ms):, '+
                            ", ".join([str(x) for x in results.time]))
                        self.export_data.append('capacitance/area (F/mm^2):,' + 
                            ", ".join([str(x) for x in results.capacitance()]))
                    elif y_axis=="Velocity":
                        dxdt = results.dxdt()
                        self.axis.set_title("Instantaneous velocity")
                        self.axis.set_ylabel("Velocity$_{drop}$ (mm/s)")
                        self.axis.plot((np.array(results.time[:-1]) + \
                                        np.array(results.time[1:]))/2,
                                       dxdt)
                        self.export_data.append('time (ms):, '+
                            ", ".join([str(x) for x in (
                                np.array(results.time[:-1])+
                                np.array(results.time[1:]))/2]))
                        self.export_data.append('velocity (mm/s):,' + 
                            ", ".join([str(x) for x in dxdt]))
                    legend.append("Step %d (%.3f s)" % (row['core']["step"]+1,
                                                        row['core']["time"]))
        elif x_axis=="Frequency":
            self.axis.set_xlabel("Frequency (Hz)")
            for row in self.data:
                if self.plugin.name in row.keys() and \
                "SweepFrequencyResults" in row[self.plugin.name].keys():
                    results = row[self.plugin.name]["SweepFrequencyResults"]
                    self.export_data.append('step:, %d' % \
                                            (row['core']["step"]+1))
                    self.export_data.append('step time (s):, %f' % \
                                            (row['core']["time"]))
                    self.export_data.append('frequency (Hz):, '+
                        ", ".join([str(x) for x in results.frequency]))
                    if y_axis=="Impedance":
                        self.axis.set_title("Impedance")
                        self.axis.set_ylabel("|Z$_{device}$(f)| ($\Omega$)")
                        self.axis.errorbar(results.frequency,
                                           np.mean(results.Z_device(), 1),
                                           np.std(results.Z_device(), 1),
                                           fmt='.')
                        self.axis.set_xscale('log')
                        self.axis.set_yscale('log')
                        self.export_data.append('mean(impedance) (Ohms):, ' + 
                            ", ".join([str(x) for x in np.mean(
                            results.Z_device(), 1)]))
                        self.export_data.append('std(impedance) (Ohms):, ' + 
                            ", ".join([str(x) for x in np.std(
                            results.Z_device(), 1)]))
                    elif y_axis=="Capacitance":
                        self.axis.set_title("Capacitance/Area")
                        self.axis.set_ylabel("C$_{device}$ (F/mm$^2$)")
                        self.axis.errorbar(results.frequency,
                                           np.mean(results.capacitance(), 1)/
                                                results.area,
                                           np.std(results.capacitance(), 1)/
                                                results.area,
                                           fmt='.')
                        self.axis.set_xscale('log')
                        self.export_data.append('mean(capacitance/area) '
                            '(F/mm^2):, ' + ", ".join([str(x) for x in np.mean(
                            results.Z_device(), 1)]))
                        self.export_data.append('std(capacitance/area) '
                            '(F/mm^2):, ' + ", ".join([str(x) for x in np.std(
                            results.Z_device(), 1)]))
                    legend.append("Step %d (%.3f s)" % \
                                  (row['core']["step"]+1, row['core']["time"]))
        elif x_axis=="Voltage":
            self.axis.set_xlabel("Voltage (V$_{rms}$)")
            for row in self.data:
                if self.plugin.name in row.keys() and \
                "SweepVoltageResults" in row[self.plugin.name].keys():
                    results = row[self.plugin.name]["SweepVoltageResults"]
                    self.export_data.append('step:, %d' % \
                                            (row['core']["step"]+1))
                    self.export_data.append('step time (s):, %f' % \
                                            (row['core']["time"]))
                    self.export_data.append('voltage (Vrms):, '+
                        ", ".join([str(x) for x in results.voltage]))
                    if y_axis=="Impedance":
                        self.axis.set_title("Impedance")
                        self.axis.set_ylabel(
                            "|Z$_{device}$(f=%.1e Hz)| ($\Omega$)" % \
                            results.frequency)
                        self.axis.errorbar(results.voltage,
                                           np.mean(results.Z_device(), 1),
                                           np.std(results.Z_device(), 1),
                                           fmt='.')
                        self.axis.set_yscale('log')
                        self.export_data.append('mean(impedance) (Ohms):, ' + 
                            ", ".join([str(x) for x in np.mean(
                            results.Z_device(), 1)]))
                        self.export_data.append('std(impedance) (Ohms):, ' + 
                            ", ".join([str(x) for x in np.std(
                            results.Z_device(), 1)]))
                    elif y_axis=="Capacitance":
                        self.axis.set_title("Capacitance/Area")
                        self.axis.set_ylabel("C$_{device}$ (F/mm$^2$)")
                        self.axis.errorbar(results.voltage,
                                           np.mean(results.capacitance()/results.area, 1),
                                           np.std(results.capacitance()/results.area, 1),
                                           fmt='.')
                        self.export_data.append('mean(capacitance/area) '
                            '(F/mm^2):, ' + ", ".join([str(x) for x in np.mean(
                            results.Z_device(), 1)]))
                        self.export_data.append('std(capacitance/area) '
                            '(F/mm^2):, ' + ", ".join([str(x) for x in np.std(
                            results.Z_device(), 1)]))
                    legend.append("Step %d (%.3f s)" % (row['core']["step"]+1, row['core']["time"]))
        if len(legend):
            self.axis.legend(legend, loc=legend_loc)
        self.figure.subplots_adjust(left=0.17, bottom=0.15)
        self.canvas.draw()
