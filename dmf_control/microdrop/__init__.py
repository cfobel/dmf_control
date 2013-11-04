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

import gtk
import gobject
import numpy as np
import yaml

import utility
try:
    from ...dmf_control_board import *
    from ..microdrop.feedback import *
except:
    # Raise the exception(s) if we're running the program (these exceptions
    # are expected when generating documentation with doxygen, so in that case
    # we can safely ignore them).
    if utility.PROGRAM_LAUNCHED:
        raise
from flatland import Element, Dict, List, String, Integer, Boolean, Float, Form, Enum
from flatland.validation import ValueAtLeast, ValueAtMost

from logger import logger
from pygtkhelpers.ui.objectlist import PropertyMapper
from gui.protocol_grid_controller import ProtocolGridController
from plugin_helpers import StepOptionsController, AppDataController, \
    get_plugin_info
from plugin_manager import IPlugin, IWaveformGenerator, Plugin, \
    implements, PluginGlobals, ScheduleRequest, emit_signal,\
    ExtensionPoint, get_service_instance
from app_context import get_app
from utility.gui import yesno, FormViewDialog
from dmf_device import DeviceScaleNotSet


PluginGlobals.push_env('microdrop.managed')


class DmfControlBoardOptions(object):
    def __init__(self, duration=100,
                voltage=100,
                frequency=1e3,
                feedback_options=None):
        self.duration = duration
        if feedback_options is None:
            self.feedback_options = FeedbackOptions()
        else:
            self.feedback_options = feedback_options
        self.voltage = voltage
        self.frequency = frequency


def format_func(value):
    if value:
        # Green
        #return '#00FF00'
        return True
    else:
        # Yellow
        #return '#FFFF00'
        return False


class DmfControlBoardPlugin(Plugin, StepOptionsController, AppDataController):
    """
    This class is automatically registered with the PluginManager.
    """
    implements(IPlugin)
    implements(IWaveformGenerator)
    
    serial_ports_ = [port for port in serial_device.SerialDevice().get_serial_ports()]
    if len(serial_ports_):
        default_port_ = serial_ports_[0]
    else:
        default_port_ = None
    
    AppFields = Form.of(
        Integer.named('sampling_time_ms').using(default=10, optional=True,
            validators=[ValueAtLeast(minimum=0), ],),
        Integer.named('delay_between_samples_ms').using(default=0,
            optional=True, validators=[ValueAtLeast(minimum=0), ],),
        Enum.named('serial_port').using(default=default_port_, optional=True)\
            .valued(*serial_ports_),
    )

    StepFields = Form.of(
        Integer.named('duration').using(default=100, optional=True,
            validators=[ValueAtLeast(minimum=0), ]),
        Float.named('voltage').using(default=100, optional=True,
            validators=[ValueAtLeast(minimum=0), ]),
        Float.named('frequency').using(default=1e3, optional=True,
            validators=[ValueAtLeast(minimum=0), ]),
        Boolean.named('feedback_enabled').using(default=True, optional=True),
    )
    _feedback_fields = set(['feedback_enabled'])
    version = get_plugin_info(path(__file__).parent.parent).version
    
    def __init__(self):
        self.control_board = DmfControlBoard()
        self.name = get_plugin_info(path(__file__).parent.parent).plugin_name
        self.url = self.control_board.host_url()
        self.steps = [] # list of steps in the protocol
        self.feedback_options_controller = None
        self.feedback_results_controller = None
        self.feedback_calibration_controller = None
        self.initialized = False
        self.connection_status = "Not connected"
        self.n_voltage_adjustments = None
        self.amplifier_gain_initialized = False
        self.current_frequency = None
        self.edit_log_calibration_menu_item = gtk.MenuItem("Edit calibration")
        self.save_log_calibration_menu_item = \
            gtk.MenuItem("Save calibration to file")
        self.load_log_calibration_menu_item = \
            gtk.MenuItem("Load calibration from file")
        self.timeout_id = None

    def on_plugin_enable(self):
        if not self.initialized:
            self.feedback_options_controller = FeedbackOptionsController(self)
            self.feedback_results_controller = FeedbackResultsController(self)
            self.feedback_calibration_controller = \
                FeedbackCalibrationController(self)
            self.edit_log_calibration_menu_item.connect("activate",
                self.feedback_calibration_controller.on_edit_log_calibration)
            self.save_log_calibration_menu_item.connect("activate",
                self.feedback_calibration_controller.on_save_log_calibration)
            self.load_log_calibration_menu_item.connect("activate",
                self.feedback_calibration_controller.on_load_log_calibration)
            
            experiment_log_controller = get_service_instance_by_name(
                "microdrop.gui.experiment_log_controller", "microdrop")
            if hasattr(experiment_log_controller, 'popup'):
                experiment_log_controller.popup.add_item(
                    self.edit_log_calibration_menu_item)
                experiment_log_controller.popup.add_item(
                    self.save_log_calibration_menu_item)
                experiment_log_controller.popup.add_item(
                    self.load_log_calibration_menu_item)

            app = get_app()
            self.control_board_menu_item = gtk.MenuItem("DMF control board")
            app.main_window_controller.menu_tools.append(
                self.control_board_menu_item)

            self.control_board_menu = gtk.Menu()
            self.control_board_menu.show()
            self.control_board_menu_item.set_submenu(self.control_board_menu)

            self.feedback_options_controller.on_plugin_enable()
            
            menu_item = gtk.MenuItem("Perform calibration")
            menu_item.connect("activate",
                self.feedback_calibration_controller.on_perform_calibration)
            self.control_board_menu.append(menu_item)
            self.perform_calibration_menu_item = menu_item
            menu_item.show()
            
            menu_item = gtk.MenuItem("Load calibration from file")
            menu_item.connect("activate",
                              self.feedback_calibration_controller. \
                                  on_load_calibration_from_file)
            self.control_board_menu.append(menu_item)
            self.load_calibration_from_file_menu_item = menu_item
            menu_item.show()
                        
            menu_item = gtk.MenuItem("Edit calibration settings")
            menu_item.connect("activate",
                              self.on_edit_calibration)
            self.control_board_menu.append(menu_item)
            self.edit_calibration_menu_item = menu_item
            menu_item.show()

            menu_item = gtk.MenuItem("Reset calibration to default values")
            menu_item.connect("activate",
                              self.on_reset_calibration_to_default_values)
            self.control_board_menu.append(menu_item)
            self.reset_calibration_to_default_values_menu_item = menu_item
            menu_item.show()
                        
            self.initialized = True

        super(DmfControlBoardPlugin, self).on_plugin_enable()
        self.check_device_name_and_version()
        self.control_board_menu_item.show()
        self.edit_log_calibration_menu_item.show()
        self.feedback_results_controller.feedback_results_menu_item.show()
        if get_app().protocol:
            self.on_step_run()
            pgc = get_service_instance(ProtocolGridController, env='microdrop')
            pgc.update_grid()

    def on_plugin_disable(self):
        self.feedback_options_controller.on_plugin_disable()
        self.control_board_menu_item.hide()
        self.edit_log_calibration_menu_item.hide()
        self.feedback_results_controller.window.hide()
        self.feedback_results_controller.feedback_results_menu_item.hide()
        if get_app().protocol:
            self.on_step_run()
            pgc = get_service_instance(ProtocolGridController, env='microdrop')
            pgc.update_grid()

    def on_app_options_changed(self, plugin_name):
        if plugin_name == self.name:
            app_values = self.get_app_values()
            if self.control_board.connected() and \
            self.control_board.port != app_values['serial_port']:
                self.connect()

    def connect(self):
        self.current_frequency = None
        self.amplifier_gain_initialized = False
        if len(DmfControlBoardPlugin.serial_ports_):
            app_values = self.get_app_values()
            # try to connect to the last successful port
            try:
                self.control_board.connect(str(app_values['serial_port']))
            except Exception, why:
                logger.warning('Could not connect to control board on port %s. '
                               'Checking other ports...' % app_values['serial_port'])
                self.control_board.connect()
            app_values['serial_port'] = self.control_board.port
            self.set_app_values(app_values)
        else:
            raise Exception("No serial ports available.")

    def check_device_name_and_version(self):
        try:
            self.connect()
            name = self.control_board.name()
            hardware_version = utility.Version.fromstring(
                self.control_board.hardware_version()
            )

            if name != "Arduino DMF Controller":
                raise Exception("Device is not an Arduino DMF Controller")
                        
            host_software_version = self.control_board.host_software_version()
            remote_software_version = self.control_board.software_version()

            # reflash the firmware if it is not the right version
            if host_software_version !=  remote_software_version:
                response = yesno("The "
                    "control board firmware version (%s) does not match the "
                    "driver version (%s). Update firmware?" %
                    (remote_software_version, host_software_version))
                    #"Update firmware?")
                if response == gtk.RESPONSE_YES:
                    self.on_flash_firmware()
        except Exception, why:
            logger.warning("%s" % why)
        
        self.update_connection_status()
        
    def on_flash_firmware(self, widget=None, data=None):
        app = get_app()
        try:
            connected = self.control_board.connected()
            if not connected:
                self.connect()
            hardware_version = utility.Version.fromstring(
                self.control_board.hardware_version()
            )
            if not connected:
                self.control_board.disconnect()
            self.control_board.flash_firmware(hardware_version)
            app.main_window_controller.info("Firmware updated successfully.",
                                            "Firmware update")
        except Exception, why:
            logger.error("Problem flashing firmware. ""%s" % why)
        self.check_device_name_and_version()

    def on_edit_calibration(self, widget=None, data=None):
        if not self.control_board.connected():
            logging.error("A control board must be connected in order to "
                          "edit calibration settings.")
            return

        hardware_version = utility.Version.fromstring(
            self.control_board.hardware_version())

        schema_entries = []
        settings = {}
        settings['amplifier_gain'] = self.control_board.amplifier_gain()
        schema_entries.append(
            Float.named('amplifier_gain').using(
                default=settings['amplifier_gain'],
                optional=True, validators=[ValueAtLeast(minimum=0.01), ]),
        )
        settings['auto_adjust_amplifier_gain'] = self.control_board \
            .auto_adjust_amplifier_gain()
        schema_entries.append(
            Boolean.named('auto_adjust_amplifier_gain').using(
                default=settings['auto_adjust_amplifier_gain'], optional=True),
        )
        settings['voltage_tolerance'] = \
            self.control_board.voltage_tolerance();
        schema_entries.append(
            Float.named('voltage_tolerance').using(
                default=settings['voltage_tolerance'], optional=True,
                validators=[ValueAtLeast(minimum=0),]),
        )
        
        if hardware_version.major == 1:        
            settings['WAVEOUT_GAIN_1'] = self.control_board \
                .eeprom_read(self.control_board.EEPROM_WAVEOUT_GAIN_1_ADDRESS)
            schema_entries.append(
                Integer.named('WAVEOUT_GAIN_1').using(
                    default=settings['WAVEOUT_GAIN_1'], optional=True,
                    validators=[ValueAtLeast(minimum=0),
                                ValueAtMost(maximum=255),]),
            )
            settings['VGND'] = self.control_board \
                .eeprom_read(self.control_board.EEPROM_VGND_ADDRESS)
            schema_entries.append(
                Integer.named('VGND').using(
                    default=settings['VGND'], optional=True,
                    validators=[ValueAtLeast(minimum=0),
                                ValueAtMost(maximum=255),]),
            )
        else:
            settings['SWITCHING_BOARD_I2C_ADDRESS'] = self.control_board \
                .eeprom_read(self.control_board.EEPROM_SWITCHING_BOARD_I2C_ADDRESS)
            schema_entries.append(
                Integer.named('SWITCHING_BOARD_I2C_ADDRESS').using(
                    default=settings['SWITCHING_BOARD_I2C_ADDRESS'], optional=True,
                    validators=[ValueAtLeast(minimum=0),
                                ValueAtMost(maximum=255),]),
            )
            settings['SIGNAL_GENERATOR_BOARD_I2C_ADDRESS'] = self.control_board \
                .eeprom_read(self.control_board.EEPROM_SIGNAL_GENERATOR_BOARD_I2C_ADDRESS)
            schema_entries.append(
                Integer.named('SIGNAL_GENERATOR_BOARD_I2C_ADDRESS').using(
                    default=settings['SIGNAL_GENERATOR_BOARD_I2C_ADDRESS'], optional=True,
                    validators=[ValueAtLeast(minimum=0),
                                ValueAtMost(maximum=255),]),
            )
        for i in range(len(self.control_board.calibration.R_hv)):
            settings['R_hv_%d' % i] = self.control_board.calibration.R_hv[i]
            schema_entries.append(
                Float.named('R_hv_%d' % i).using(
                    default=settings['R_hv_%d' % i], optional=True,
                    validators=[ValueAtLeast(minimum=0),]))
            settings['C_hv_%d' % i] =\
                self.control_board.calibration.C_hv[i]*1e12
            schema_entries.append(
                Float.named('C_hv_%d' % i).using(
                    default=settings['C_hv_%d' % i], optional=True,
                    validators=[ValueAtLeast(minimum=0),]))
        for i in range(len(self.control_board.calibration.R_fb)):
            settings['R_fb_%d' % i] = self.control_board.calibration.R_fb[i]
            schema_entries.append(
                Float.named('R_fb_%d' % i).using(
                    default=settings['R_fb_%d' % i], optional=True,
                    validators=[ValueAtLeast(minimum=0),]))
            settings['C_fb_%d' % i] = \
                self.control_board.calibration.C_fb[i]*1e12
            schema_entries.append(
                Float.named('C_fb_%d' % i).using(
                    default=settings['C_fb_%d' % i], optional=True,
                    validators=[ValueAtLeast(minimum=0),]))

        form = Form.of(*schema_entries)
        dialog = FormViewDialog('Edit calibration settings')
        valid, response =  dialog.run(form)
        if valid:
            for k, v in response.items():
                if settings[k] != v:
                    m = re.match('(R|C)_(hv|fb)_(\d)', k)
                    if k=='amplifier_gain':
                        self.control_board.set_amplifier_gain(v)
                    elif k=='auto_adjust_amplifier_gain':
                        self.control_board.set_auto_adjust_amplifier_gain(v)
                    elif k=='WAVEOUT_GAIN_1':
                        self.control_board.eeprom_write(
                            self.control_board.EEPROM_WAVEOUT_GAIN_1_ADDRESS, v)
                    elif k=='VGND':
                        self.control_board.eeprom_write(
                            self.control_board.EEPROM_VGND_ADDRESS, v)
                    elif k=='SWITCHING_BOARD_I2C_ADDRESS':
                        self.control_board.eeprom_write(
                            self.control_board.EEPROM_SWITCHING_BOARD_I2C_ADDRESS, v)
                    elif k=='SIGNAL_GENERATOR_BOARD_I2C_ADDRESS':
                        self.control_board.eeprom_write(
                            self.control_board.EEPROM_SIGNAL_GENERATOR_BOARD_I2C_ADDRESS, v)
                    elif k=='voltage_tolerance':
                        self.control_board.set_voltage_tolerance(v)
                    elif m:
                        series_resistor = int(m.group(3))
                        if m.group(2)=='hv':
                            channel = 0
                        else:
                            channel = 1
                        self.control_board.set_series_resistor_index(channel,
                            series_resistor)
                        if m.group(1)=='R':
                            self.control_board.set_series_resistance(channel, v)
                        else:
                            if v is None:
                                v=0
                            self.control_board.set_series_capacitance(channel,
                                v/1e12)
            # reconnect to update settings
            self.connect()
            if get_app().protocol:
                self.on_step_run()

    def on_reset_calibration_to_default_values(self, widget=None, data=None):
        self.control_board.reset_config_to_defaults()
        # reconnect to update settings
        self.connect()

    def update_connection_status(self):
        self.connection_status = "Not connected"
        app = get_app()
        connected = self.control_board.connected()
        if connected:
            try:
                name = self.control_board.name()
                version = self.control_board.hardware_version()
                firmware = self.control_board.software_version()
                n_channels = self.control_board.number_of_channels()
                self.connection_status = name + " v" + version + \
                    " (Firmware: " + str(firmware) + ")\n" + \
                    str(n_channels) + " channels"
            except:
                pass
        self.perform_calibration_menu_item.set_sensitive(connected)
        self.load_calibration_from_file_menu_item.set_sensitive(connected)
        self.edit_calibration_menu_item.set_sensitive(connected)
        self.reset_calibration_to_default_values_menu_item.set_sensitive(
            connected)
        self.feedback_options_controller.measure_cap_filler_menu_item. \
            set_sensitive(connected)
        self.feedback_options_controller.measure_cap_liquid_menu_item. \
            set_sensitive(connected)
        app.main_window_controller.label_control_board_status. \
            set_text(self.connection_status)

    def on_device_impedance_update(self, impedance):
        app = get_app()
        app.main_window_controller.label_control_board_status. \
            set_text(self.connection_status + ", Voltage: %.1f V" % \
                     impedance.V_actuation()[-1])
        options = impedance.options
        feedback_options = impedance.options.feedback_options

        app_values = self.get_app_values()            

        if impedance.V_actuation()[-1]<5.0:
            logger.error("Low voltage detected. Please check that the amplifier is on.")
        else:
            voltage = options.voltage
            if feedback_options.action.__class__ == RetryAction:
                attempt = app.protocol.current_step_attempt
                voltage += feedback_options.action.increase_voltage * \
                        attempt
            logger.info('[DmfControlBoardPlugin].on_device_impedance_update():')
            logger.info('\tset_voltage=%.1f, measured_voltage=%.1f, '
                'error=%.1f%%' % (voltage, impedance.V_actuation()[-1],
                100*(impedance.V_actuation()[-1]-voltage)/voltage))
            
            # check that the signal is within tolerance
            if abs(impedance.V_actuation()[-1]-voltage) > \
                self.control_board.voltage_tolerance():
                
                # allow maximum of 5 adjustment attempts
                if self.control_board.auto_adjust_amplifier_gain() and \
                self.n_voltage_adjustments is not None and \
                self.n_voltage_adjustments<5:
                        logger.info('\tn_voltage_adjustments=%d' % \
                                    self.n_voltage_adjustments)
                        emit_signal("set_voltage", voltage,
                            interface=IWaveformGenerator)
                        self.check_impedance(options,
                                             self.n_voltage_adjustments+1)
                else:
                    self.n_voltage_adjustments = None
                    logger.error("Unable to achieve the specified voltage.")
             
             
            if self.control_board.auto_adjust_amplifier_gain() and not \
            self.amplifier_gain_initialized:
                self.amplifier_gain_initialized = True
                logger.info('Amplifier gain initialized (gain=%.1f)' % \
                            self.control_board.amplifier_gain())

    def get_actuated_area(self):
        app = get_app()
        if app.dmf_device.scale is None:
            raise DeviceScaleNotSet()
        area = 0
        options = app.dmf_device_controller.get_step_options()
        state_of_all_channels = options.state_of_channels
        for id, electrode in app.dmf_device.electrodes.iteritems():
            channels = app.dmf_device.electrodes[id].channels
            if channels:
                # get the state(s) of the channel(s) connected to this electrode
                states = state_of_all_channels[channels]
                if len(np.nonzero(states > 0)[0]):
                    area += electrode.area() * app.dmf_device.scale
        return area

    def on_step_run(self):
        """
        Handler called whenever a step is executed.

        Plugins that handle this signal must emit the on_step_complete
        signal once they have completed the step. The protocol controller
        will wait until all plugins have completed the current step before
        proceeding.
        """
        logger.debug('[DmfControlBoardPlugin] on_step_run()')
        self._kill_running_step()
        app = get_app()
        options = self.get_step_options()
        dmf_options = app.dmf_device_controller.get_step_options()
        logger.debug('[DmfControlBoardPlugin] options=%s dmf_options=%s' % \
                     (options, dmf_options))
        feedback_options = options.feedback_options
        app_values = self.get_app_values()

        start_time = time.time()
        return_value = None

        try:
            if self.control_board.connected() and \
                (app.realtime_mode or app.running):
                
                # initialize the amplifier gain
                if self.control_board.auto_adjust_amplifier_gain() and \
                    not self.amplifier_gain_initialized:
                    emit_signal("set_frequency",
                                options.frequency,
                                interface=IWaveformGenerator)
                    emit_signal("set_voltage", options.voltage,
                                interface=IWaveformGenerator)
                    self.check_impedance(options)

                state = dmf_options.state_of_channels
                max_channels = self.control_board.number_of_channels()
                if len(state) >  max_channels:
                    state = state[0:max_channels]
                elif len(state) < max_channels:
                    state = np.concatenate([state,
                            np.zeros(max_channels - len(state), int)])
                else:
                    assert(len(state) == max_channels)
    
                if feedback_options.feedback_enabled:
                    # calculate the total area of actuated electrodes
                    area = self.get_actuated_area()
                    
                    if feedback_options.action.__class__ == RetryAction:
                        attempt = app.protocol.current_step_attempt
                        if attempt <= feedback_options.action.max_repeats:
                            voltage = options.voltage + \
                                feedback_options.action.increase_voltage * \
                                attempt
                            frequency = options.frequency
                            emit_signal("set_voltage", voltage,
                                        interface=IWaveformGenerator)
                            if frequency != self.current_frequency:
                                emit_signal("set_frequency", frequency,
                                            interface=IWaveformGenerator)
                                self.check_impedance(options)
                            self.control_board.measure_impedance_non_blocking(
                                app_values['sampling_time_ms'],
                                int(math.ceil(options.duration/ 
                                    app_values['sampling_time_ms'])),
                                app_values['delay_between_samples_ms'],
                                state)
                            logger.debug('[DmfControlBoardPlugin] on_step_run: '
                                         'timeout_add(%d, _callback_retry_action'
                                         '_completed)' % options.duration)
                            self.timeout_id = \
                                gobject.timeout_add(options.duration,
                                    self._callback_retry_action_completed,
                                    options)
                        else:
                            self.step_complete('Fail')
                        return
                    elif feedback_options.action.__class__ == \
                        SweepFrequencyAction:
                        frequencies = np.logspace(
                            np.log10(feedback_options.action.start_frequency),
                            np.log10(feedback_options.action.end_frequency),
                            int(feedback_options.action.n_frequency_steps)
                        ).tolist()
                        voltage = options.voltage
                        results = SweepFrequencyResults(feedback_options,
                            area,
                            self.control_board.calibration)
                        emit_signal("set_voltage", voltage,
                                    interface=IWaveformGenerator)
                        test_options = deepcopy(options)
                        self._callback_sweep_frequency(test_options,
                                                       results,
                                                       state,
                                                       frequencies,
                                                       first_call=True)
                        return
                    elif feedback_options.action.__class__==SweepVoltageAction:
                        voltages = np.linspace(
                           feedback_options.action.start_voltage,
                           feedback_options.action.end_voltage,
                           feedback_options.action.n_voltage_steps).tolist()
                        frequency = options.frequency
                        if frequency != self.current_frequency:
                            emit_signal("set_voltage", options.voltage,
                                        interface=IWaveformGenerator)
                            emit_signal("set_frequency", frequency,
                                        interface=IWaveformGenerator)
                            self.check_impedance(options)
                        results = SweepVoltageResults(feedback_options,
                            area,
                            frequency,
                            self.control_board.calibration)
                        test_options = deepcopy(options)
                        self._callback_sweep_voltage(test_options,
                                                     results,
                                                     state,
                                                     voltages,
                                                     first_call=True)
                        return
                else:
                    emit_signal("set_frequency",
                                options.frequency,
                                interface=IWaveformGenerator)
                    emit_signal("set_voltage", options.voltage,
                                interface=IWaveformGenerator)
                    self.check_impedance(options)
                    self.control_board.state_of_all_channels = state
            # turn off all electrodes if we're not in realtime mode and not
            # running a protocol
            elif self.control_board.connected() and \
                not app.realtime_mode and not app.running:
                # turn off all electrodes
                self.control_board.set_state_of_all_channels(
                    np.zeros(self.control_board.number_of_channels())
                )
            
            # if a protocol is running, wait for the specified minimum duration
            if app.running:
                logger.debug('[DmfControlBoardPlugin] on_step_run: '
                             'timeout_add(%d, _callback_step_completed)' %
                             options.duration)
                self.timeout_id = \
                    gobject.timeout_add(options.duration,
                    self._callback_step_completed)
                return
            else:
                self.step_complete()
        except DeviceScaleNotSet:
            logger.error("Please set the area of one of your electrodes.")

    def step_complete(self, return_value=None):
        app = get_app()
        if app.running or app.realtime_mode:
            emit_signal('on_step_complete', [self.name, return_value])

    def on_step_complete(self, plugin_name, return_value=None):
        if plugin_name==self.name:
            self.timeout_id = None

    def get_impedance_data(self, options):
        """
        This function wraps the control_board.get_impedance_data() function
        and sends an on_device_impedance_update.
        """
        app_values = self.get_app_values()
        (V_hv, hv_resistor, V_fb, fb_resistor) = \
            self.control_board.get_impedance_data()
        results = FeedbackResults(options,
            app_values['sampling_time_ms'],
            app_values['delay_between_samples_ms'],
            V_hv,
            hv_resistor,
            V_fb,
            fb_resistor,
            self.get_actuated_area(),
            self.control_board.calibration,
            0)
        emit_signal("on_device_impedance_update", results)
        return (V_hv, hv_resistor, V_fb, fb_resistor)

    def _kill_running_step(self):
        if self.timeout_id:
            logger.debug('[DmfControlBoardPlugin] _kill_running_step: removing'
                         'timeout_id=%d' % self.timeout_id)
            gobject.source_remove(self.timeout_id)

    def _callback_step_completed(self):
        logger.debug('[DmfControlBoardPlugin] _callback_step_completed')
        self.step_complete()
        return False # stop the timeout from refiring

    def _callback_retry_action_completed(self, options):
        logger.debug('[DmfControlBoardPlugin] '
                     '_callback_retry_action_completed')
        app = get_app()
        app_values = self.get_app_values()
        area = self.get_actuated_area()
        return_value = None
        (V_hv, hv_resistor, V_fb, fb_resistor) = \
            self.get_impedance_data(options)
        results = FeedbackResults(options,
            app_values['sampling_time_ms'],
            app_values['delay_between_samples_ms'],
            V_hv,
            hv_resistor,
            V_fb,
            fb_resistor,
            area,
            self.control_board.calibration,
            app.protocol.current_step_attempt)
        logger.debug("V_actuation=%s" % \
                    results.V_actuation())
        logger.debug("Z_device=%s" % results.Z_device())
        app.experiment_log.add_data(
            {"FeedbackResults":results},self.name)
        if self.control_board.calibration.C_drop and \
            max(results.capacitance())/area < \
            options.feedback_options.action.percent_threshold/ \
                100.0*self.control_board.calibration.C_drop:
            logger.info('step=%d: attempt=%d, max(C)'
                        '/A=%.1e F/mm^2. Repeat' % \
                        (app.protocol.current_step_number,
                         app.protocol.current_step_attempt,
                         max(results.capacitance())/area))
            # signal that the step should be repeated
            return_value = 'Repeat'
        else:
            logger.info('step=%d: attempt=%d, max(C)'
                        '/A=%.1e F/mm^2. OK' % \
                        (app.protocol.current_step_number,
                         app.protocol.current_step_attempt,
                         max(results.capacitance())/area))
        self.step_complete(return_value)
        return False # stop the timeout from refiring

    def _callback_sweep_frequency(self, options, results, state, frequencies,
                                  first_call=False):
        logger.debug('[DmfControlBoardPlugin] '
                     '_callback_sweep_frequency')
        app = get_app()
        app_values = self.get_app_values()

        # if this isn'g the first call, we need to retrieve the data from the
        # previous call
        if first_call==False:
            frequency = frequencies.pop(0)
            (V_hv, hv_resistor, V_fb, fb_resistor) = \
                self.get_impedance_data(options)
            results.add_frequency_step(frequency, V_hv, hv_resistor, V_fb,
                                       fb_resistor)
            app.experiment_log.add_data(
                {"SweepFrequencyResults":results}, self.name)
            logger.debug("V_actuation=%s" % results.V_actuation())
            logger.debug("Z_device=%s" % results.Z_device())

        # if there are frequencies left to sweep
        if len(frequencies):
            frequency  = frequencies[0]
            emit_signal("set_frequency",
                        frequency,
                        interface=IWaveformGenerator)
            options.frequency = frequency
            self.control_board.measure_impedance_non_blocking(
                app_values['sampling_time_ms'],
                int(math.ceil(options.duration/ 
                    app_values['sampling_time_ms'])),
                app_values['delay_between_samples_ms'],
                state)
            logger.debug('[DmfControlBoardPlugin] _callback_sweep_frequency: '
                         'timeout_add(%d, _callback_sweep_frequency)' %
                         options.duration)
            self.timeout_id = \
                gobject.timeout_add(options.duration,
                                    self._callback_sweep_frequency,
                                    options, results, state, frequencies)
        else:
            self.step_complete()
        return False # stop the timeout from refiring
    
    def _callback_sweep_voltage(self, options, results, state, voltages,
                                first_call=False):
        logger.debug('[DmfControlBoardPlugin] '
                     '_callback_sweep_voltage')
        app = get_app()
        app_values = self.get_app_values()

        # if this isn'g the first call, we need to retrieve the data from the
        # previous call
        if first_call==False:
            voltage = voltages.pop(0)
            (V_hv, hv_resistor, V_fb, fb_resistor) = \
                self.get_impedance_data(options)
            results.add_voltage_step(voltage, V_hv, hv_resistor, V_fb,
                                     fb_resistor)
            app.experiment_log.add_data(
                {"SweepVoltageResults":results}, self.name)
            logger.debug("V_actuation=%s" % results.V_actuation())
            logger.debug("Z_device=%s" % results.Z_device())

        # if there are voltages left to sweep
        if len(voltages):
            voltage  = voltages[0]
            emit_signal("set_voltage", voltage,
                        interface=IWaveformGenerator)            
            options.voltage = voltage
            self.control_board.measure_impedance_non_blocking(
                app_values['sampling_time_ms'],
                int(math.ceil(options.duration/ 
                    app_values['sampling_time_ms'])),
                app_values['delay_between_samples_ms'],
                state)
            logger.debug('[DmfControlBoardPlugin] _callback_sweep_voltage: '
                         'timeout_add(%d, _callback_sweep_voltage)' %
                         options.duration)
            self.timeout_id = \
                gobject.timeout_add(options.duration,
                                    self._callback_sweep_voltage,
                                    options, results, state, voltages)
        else:
            self.step_complete()
        return False # stop the timeout from refiring
    
    def on_dmf_device_swapped(self, old_dmf_device, dmf_device):
        self.feedback_options_controller. \
            feedback_options_menu_item.set_sensitive(True)
    
    def on_protocol_run(self):
        """
        Handler called when a protocol starts running.
        """
        app = get_app()
        if self.control_board.connected() == False:
            logger.warning("Warning: no control board connected.")
        elif self.control_board.number_of_channels() <= \
            app.dmf_device.max_channel():
            logger.warning("Warning: currently "
                "connected board does not have enough channels for this "
                "protocol.")

    def on_protocol_pause(self):
        """
        Handler called when a protocol is paused.
        """
        app = get_app()
        self._kill_running_step()
        if self.control_board.connected() and not app.realtime_mode:
            # turn off all electrodes
            self.control_board.set_state_of_all_channels(
                np.zeros(self.control_board.number_of_channels())
            )
    
    def on_experiment_log_selection_changed(self, data):
        """
        Handler called whenever the experiment log selection changes.

        Parameters:
            data : dictionary of experiment log data for the selected steps
        """
        if self.feedback_results_controller:
            self.feedback_results_controller. \
                on_experiment_log_selection_changed(data)
        
    def set_voltage(self, voltage):
        """
        Set the waveform voltage.
        
        Parameters:
            voltage : RMS voltage
        """
        logger.info("[DmfControlBoardPlugin].set_voltage(%.1f)" % voltage)
        self.control_board.set_waveform_voltage(voltage)
        
    def set_frequency(self, frequency):
        """
        Set the waveform frequency.
        
        Parameters:
            frequency : frequency in Hz
        """
        logger.info("[DmfControlBoardPlugin].set_frequency(%.1f)" % frequency)
        self.control_board.set_waveform_frequency(frequency)
        self.current_frequency = frequency
        
    def check_impedance(self, options, n_voltage_adjustments=0):
        """
        Check the device impedance.
        
        Note that this function blocks until it returns.
        """
        # increment the number of adjustment attempts
        self.n_voltage_adjustments = n_voltage_adjustments

        app_values = self.get_app_values()
        test_options = deepcopy(options)
        # take 5 samples to allow signal/gain to stabilize
        test_options.duration = app_values['sampling_time_ms']*5
        test_options.feedback_options = FeedbackOptions(
            feedback_enabled=True, action=RetryAction())
        state = np.zeros(self.control_board.number_of_channels())
        (V_hv, hv_resistor, V_fb, fb_resistor) = \
            self.control_board.measure_impedance(
                app_values['sampling_time_ms'],
                int(math.ceil(test_options.duration/ 
                    app_values['sampling_time_ms'])),
                app_values['delay_between_samples_ms'],
                state)
        results = FeedbackResults(test_options,
            app_values['sampling_time_ms'],
            app_values['delay_between_samples_ms'],
            V_hv,
            hv_resistor,
            V_fb,
            fb_resistor,
            self.get_actuated_area(),
            self.control_board.calibration,
            0)
        emit_signal("on_device_impedance_update", results)
        return results
        
    def get_default_step_options(self):
        return DmfControlBoardOptions()

    def set_step_values(self, values_dict, step_number=None):
        step_number = self.get_step_number(step_number)
        logger.debug('[DmfControlBoardPlugin] set_step[%d]_values(): '\
                    'values_dict=%s' % (step_number, values_dict,))
        el = self.StepFields(value=values_dict)
        try:
            if not el.validate():
                raise ValueError()            
            options = self.get_step_options(step_number=step_number)
            for name, field in el.iteritems():
                if field.value is None:
                    continue
                if name in self._feedback_fields:
                    setattr(options.feedback_options, name, field.value)
                else:
                    setattr(options, name, field.value)
        finally:
            emit_signal('on_step_options_changed', [self.name, step_number],
                        interface=IPlugin)

    def get_step_values(self, step_number=None):
        app = get_app()
        if step_number is None:
            step_number = app.protocol.current_step_number
        step = app.protocol.steps[step_number]

        options = self.get_step_options(step_number)

        values = {}
        for name in self.StepFields.field_schema_mapping:
            try:
                value = getattr(options, name)
            except AttributeError:
                value = getattr(options.feedback_options, name)
            values[name] = value
        return values

    def get_step_value(self, name, step_number=None):
        app = get_app()
        if not name in self.StepFields.field_schema_mapping:
            raise KeyError('No field with name %s for plugin %s' % (name,
                                                                    self.name))
        if step_number is None:
            step_number = app.protocol.current_step_number
        step = app.protocol.steps[step_number]

        options = self.get_step_options(step_number)
        try:
            return getattr(options, name)
        except AttributeError:
            return getattr(options.feedback_options, name)

    def on_step_options_changed(self, plugin, step_number):
        logger.debug('[DmfControlBoardPlugin] on_step_options_changed():'\
                     '%s step #%d' % (plugin, step_number))
        app = get_app()
        if self.feedback_options_controller:
            self.feedback_options_controller\
                .on_step_options_changed(plugin, step_number)
        if app.protocol and not app.running and not app.realtime_mode and \
            (plugin=='microdrop.gui.dmf_device_controller' or \
             plugin==self.name) and \
            app.protocol.current_step_number==step_number:
            self.on_step_run()

    def on_step_swapped(self, original_step_number, new_step_number):
        logger.debug('[DmfControlBoardPlugin] on_step_swapped():'\
                    'original_step_number=%d, new_step_number=%d' % \
                    (original_step_number, new_step_number))
        self.on_step_options_changed(self.name,
                                     get_app().protocol.current_step_number)

    def on_experiment_log_created(self, log):
        app = get_app()
        data = {}
        if self.control_board.connected():
            data["control board name"] = \
                self.control_board.name()
            data["control board hardware version"] = \
                self.control_board.hardware_version()
            data["control board software version"] = \
                self.control_board.software_version()
        log.add_data(data)

    def get_schedule_requests(self, function_name):
        """
        Returns a list of scheduling requests (i.e., ScheduleRequest
        instances) for the function specified by function_name.
        """
        if function_name in ['on_step_options_changed']:
            return [ScheduleRequest(self.name,
                                    'microdrop.gui.protocol_grid_controller')]
        return []

    def on_experiment_log_created(self, log):
        app = get_app()
        data = {}
        if self.control_board.connected():
            data["control board name"] = \
                self.control_board.name()
            data["control board hardware version"] = \
                self.control_board.hardware_version()
            data["control board software version"] = \
                self.control_board.software_version()
        log.add_data(data)


PluginGlobals.pop_env()
