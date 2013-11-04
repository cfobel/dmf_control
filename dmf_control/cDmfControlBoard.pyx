#cython: embedsignature=True
from cRemoteObject cimport RemoteObject, cRemoteObject


cdef class cDmfControlBoard(cRemoteObject):
    cdef DmfControlBoard *thisptr

    def __cinit__(self):
        self.thisptr = new DmfControlBoard()
        self.baseptr = <RemoteObject *>self.thisptr

    def __init__(self):
        pass

    def __dealloc__(self):
        del self.thisptr

    property EEPROM_CONFIG_SETTINGS:
        def __get__(self):
            return self.thisptr.EEPROM_CONFIG_SETTINGS

    property BAUD_RATE:
        def __get__(self):
            return self.thisptr.BAUD_RATE

    property SINE:
        def __get__(self):
            return self.thisptr.SINE

    property SQUARE:
        def __get__(self):
            return self.thisptr.SQUARE

    property NUMBER_OF_ADC_CHANNELS:
        def __get__(self):
            return self.thisptr.NUMBER_OF_ADC_CHANNELS

    property CMD_GET_NUMBER_OF_CHANNELS:
        def __get__(self):
            return self.thisptr.CMD_GET_NUMBER_OF_CHANNELS

    property CMD_GET_STATE_OF_ALL_CHANNELS:
        def __get__(self):
            return self.thisptr.CMD_GET_STATE_OF_ALL_CHANNELS

    property CMD_SET_STATE_OF_ALL_CHANNELS:
        def __get__(self):
            return self.thisptr.CMD_SET_STATE_OF_ALL_CHANNELS

    property CMD_GET_STATE_OF_CHANNEL:
        def __get__(self):
            return self.thisptr.CMD_GET_STATE_OF_CHANNEL

    property CMD_SET_STATE_OF_CHANNEL:
        def __get__(self):
            return self.thisptr.CMD_SET_STATE_OF_CHANNEL

    property CMD_GET_WAVEFORM:
        def __get__(self):
            return self.thisptr.CMD_GET_WAVEFORM

    property CMD_SET_WAVEFORM:
        def __get__(self):
            return self.thisptr.CMD_SET_WAVEFORM

    property CMD_GET_WAVEFORM_VOLTAGE:
        def __get__(self):
            return self.thisptr.CMD_GET_WAVEFORM_VOLTAGE

    property CMD_SET_WAVEFORM_VOLTAGE:
        def __get__(self):
            return self.thisptr.CMD_SET_WAVEFORM_VOLTAGE

    property CMD_GET_WAVEFORM_FREQUENCY:
        def __get__(self):
            return self.thisptr.CMD_GET_WAVEFORM_FREQUENCY

    property CMD_SET_WAVEFORM_FREQUENCY:
        def __get__(self):
            return self.thisptr.CMD_SET_WAVEFORM_FREQUENCY

    property CMD_GET_SAMPLING_RATE:
        def __get__(self):
            return self.thisptr.CMD_GET_SAMPLING_RATE

    property CMD_SET_SAMPLING_RATE:
        def __get__(self):
            return self.thisptr.CMD_SET_SAMPLING_RATE

    property CMD_GET_SERIES_RESISTOR_INDEX:
        def __get__(self):
            return self.thisptr.CMD_GET_SERIES_RESISTOR_INDEX

    property CMD_SET_SERIES_RESISTOR_INDEX:
        def __get__(self):
            return self.thisptr.CMD_SET_SERIES_RESISTOR_INDEX

    property CMD_GET_SERIES_RESISTANCE:
        def __get__(self):
            return self.thisptr.CMD_GET_SERIES_RESISTANCE

    property CMD_SET_SERIES_RESISTANCE:
        def __get__(self):
            return self.thisptr.CMD_SET_SERIES_RESISTANCE

    property CMD_GET_SERIES_CAPACITANCE:
        def __get__(self):
            return self.thisptr.CMD_GET_SERIES_CAPACITANCE

    property CMD_SET_SERIES_CAPACITANCE:
        def __get__(self):
            return self.thisptr.CMD_SET_SERIES_CAPACITANCE

    property CMD_GET_AMPLIFIER_GAIN:
        def __get__(self):
            return self.thisptr.CMD_GET_AMPLIFIER_GAIN

    property CMD_SET_AMPLIFIER_GAIN:
        def __get__(self):
            return self.thisptr.CMD_SET_AMPLIFIER_GAIN

    property CMD_GET_AUTO_ADJUST_AMPLIFIER_GAIN:
        def __get__(self):
            return self.thisptr.CMD_GET_AUTO_ADJUST_AMPLIFIER_GAIN

    property CMD_SET_AUTO_ADJUST_AMPLIFIER_GAIN:
        def __get__(self):
            return self.thisptr.CMD_SET_AUTO_ADJUST_AMPLIFIER_GAIN

    property CMD_SYSTEM_RESET:
        def __get__(self):
            return self.thisptr.CMD_SYSTEM_RESET

    property CMD_DEBUG_MESSAGE:
        def __get__(self):
            return self.thisptr.CMD_DEBUG_MESSAGE

    property CMD_DEBUG_ON:
        def __get__(self):
            return self.thisptr.CMD_DEBUG_ON

    property CMD_MEASURE_IMPEDANCE:
        def __get__(self):
            return self.thisptr.CMD_MEASURE_IMPEDANCE

    property CMD_RESET_CONFIG_TO_DEFAULTS:
        def __get__(self):
            return self.thisptr.CMD_RESET_CONFIG_TO_DEFAULTS

    def number_of_channels(self):
        return self.thisptr.number_of_channels()

    def state_of_all_channels(self):
        return self.thisptr.state_of_all_channels()

    def state_of_channel(self, uint16_t channel):
        return self.thisptr.state_of_channel(channel)

    def sampling_rate(self):
        return self.thisptr.sampling_rate()

    def series_resistor_index(self, uchar channel):
        return self.thisptr.series_resistor_index(channel)

    def series_resistance(self, uchar channel):
        return self.thisptr.series_resistance(channel)

    def series_capacitance(self, uchar channel):
        return self.thisptr.series_capacitance(channel)

    def waveform(self):
        return self.thisptr.waveform()

    def waveform_frequency(self):
        return self.thisptr.waveform_frequency()

    def waveform_voltage(self):
        return self.thisptr.waveform_voltage()

    def amplifier_gain(self):
        return self.thisptr.amplifier_gain()

    def auto_adjust_amplifier_gain(self):
        return self.thisptr.auto_adjust_amplifier_gain()

    # Remote mutators (return code is from reply packet)

    def set_state_of_channel(self, uint16_t channel, uchar state):
        return self.thisptr.set_state_of_channel(channel, state)

    def set_state_of_all_channels(self, vector[uchar] state):
        return self.thisptr.set_state_of_all_channels(state)

    def set_waveform_voltage(self, float v_rms):
        return self.thisptr.set_waveform_voltage(v_rms)

    def set_waveform_frequency(self, float freq_hz):
        return self.thisptr.set_waveform_frequency(freq_hz)

    def set_waveform(self, bint waveform):
        return self.thisptr.set_waveform(waveform)

    def set_sampling_rate(self, uchar sampling_rate):
        return self.thisptr.set_sampling_rate(sampling_rate)

    def set_series_resistor_index(self, uchar channel, uchar index):
        return self.thisptr.set_series_resistor_index(channel, index)

    def set_series_resistance(self, uchar channel, float resistance):
        return self.thisptr.set_series_resistance(channel, resistance)

    def set_series_capacitance(self, uchar channel, float capacitance):
        return self.thisptr.set_series_capacitance(channel, capacitance)

    def set_amplifier_gain(self, float gain):
        return self.thisptr.set_amplifier_gain(gain)

    def set_auto_adjust_amplifier_gain(self, bint on):
        return self.thisptr.set_auto_adjust_amplifier_gain(on)

    # other functions
    def MeasureImpedanceNonBlocking(self, uint16_t sampling_time_ms,
                                    uint16_t n_samples,
                                    uint16_t delay_between_samples_ms,
                                    vector[uchar] state):
        self.thisptr.MeasureImpedanceNonBlocking(sampling_time_ms, n_samples,
                                                 delay_between_samples_ms,
                                                 state)

    def GetImpedanceData(self):
        return self.thisptr.GetImpedanceData()

    def MeasureImpedance(self, uint16_t sampling_time_ms, uint16_t n_samples,
                         uint16_t delay_between_samples_ms,
                         vector[uchar] state):
        return self.this.MeasureImpedance(sampling_time_ms, n_samples,
                                          delay_between_samples_ms, state)

    def ResetConfigToDefaults(self):
        return self.thisptr.ResetConfigToDefaults()

    def host_name(self):
        return self.thisptr.host_name()

    def host_manufacturer(self):
        return self.thisptr.host_manufacturer()

    def host_software_version(self):
        return self.thisptr.host_software_version()

    def host_url(self):
        return self.thisptr.host_url()
