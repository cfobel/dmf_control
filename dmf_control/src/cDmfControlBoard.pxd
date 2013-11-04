from libcpp.vector cimport vector
from libcpp.string cimport string
from libc.stdint cimport uint16_t, uint32_t
from cRemoteObject cimport uchar, RemoteObject


cdef extern from "dmf_control_board.h":
    cdef cppclass DmfControlBoard:
        DmfControlBoard()

        uint32_t BAUD_RATE
        uchar SINE
        uchar SQUARE
        uint16_t EEPROM_CONFIG_SETTINGS

        uchar NUMBER_OF_ADC_CHANNELS

        uchar CMD_GET_NUMBER_OF_CHANNELS
        uchar CMD_GET_STATE_OF_ALL_CHANNELS
        uchar CMD_SET_STATE_OF_ALL_CHANNELS
        uchar CMD_GET_STATE_OF_CHANNEL
        uchar CMD_SET_STATE_OF_CHANNEL
        uchar CMD_GET_WAVEFORM
        uchar CMD_SET_WAVEFORM
        uchar CMD_GET_WAVEFORM_VOLTAGE
        uchar CMD_SET_WAVEFORM_VOLTAGE
        uchar CMD_GET_WAVEFORM_FREQUENCY
        uchar CMD_SET_WAVEFORM_FREQUENCY
        uchar CMD_GET_SAMPLING_RATE
        uchar CMD_SET_SAMPLING_RATE
        uchar CMD_GET_SERIES_RESISTOR_INDEX
        uchar CMD_SET_SERIES_RESISTOR_INDEX
        uchar CMD_GET_SERIES_RESISTANCE
        uchar CMD_SET_SERIES_RESISTANCE
        uchar CMD_GET_SERIES_CAPACITANCE
        uchar CMD_SET_SERIES_CAPACITANCE
        uchar CMD_GET_AMPLIFIER_GAIN
        uchar CMD_SET_AMPLIFIER_GAIN
        uchar CMD_GET_AUTO_ADJUST_AMPLIFIER_GAIN
        uchar CMD_SET_AUTO_ADJUST_AMPLIFIER_GAIN
        uchar CMD_SYSTEM_RESET
        uchar CMD_DEBUG_MESSAGE
        uchar CMD_DEBUG_ON
        uchar CMD_MEASURE_IMPEDANCE
        uchar CMD_RESET_CONFIG_TO_DEFAULTS

        uint16_t number_of_channels() except +
        vector[uchar] state_of_all_channels() except +
        uchar state_of_channel(uint16_t channel) except +
        float sampling_rate() except +
        uchar series_resistor_index(uchar channel) except +
        float series_resistance(uchar channel) except +
        float series_capacitance(uchar channel) except +
        string waveform() except +
        float waveform_frequency() except +
        float waveform_voltage() except +
        float amplifier_gain() except +
        bint auto_adjust_amplifier_gain() except +

        # Remote mutators (return code is from reply packet)
        uchar set_state_of_channel(uint16_t channel, uchar state) except +
        uchar set_state_of_all_channels(vector[uchar] state) except +
        uchar set_waveform_voltage(float v_rms) except +
        uchar set_waveform_frequency(float freq_hz) except +
        uchar set_waveform(bint waveform) except +
        uchar set_sampling_rate(uchar sampling_rate) except +
        uchar set_series_resistor_index(uchar channel, uchar index) except +
        uchar set_series_resistance(uchar channel, float resistance) except +
        uchar set_series_capacitance(uchar channel, float capacitance) except +
        uchar set_amplifier_gain(float gain) except +
        uchar set_auto_adjust_amplifier_gain(bint on) except +

        # other functions
        void MeasureImpedanceNonBlocking(uint16_t sampling_time_ms,
                                         uint16_t n_samples,
                                         uint16_t delay_between_samples_ms,
                                         vector[uchar] state) except +
        vector[float] GetImpedanceData() except +
        vector[float] MeasureImpedance(uint16_t sampling_time_ms,
                                       uint16_t n_samples,
                                       uint16_t delay_between_samples_ms,
                                       vector[uchar] state) except +
        uchar ResetConfigToDefaults() except +
        string host_name()
        string host_manufacturer()
        string host_software_version()
        string host_url()
