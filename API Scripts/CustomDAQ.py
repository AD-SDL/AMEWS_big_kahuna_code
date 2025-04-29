import sys, os
from mcculw import ul
from mcculw.enums import InterfaceType
from mcculw.enums import DigitalIODirection
from mcculw.device_info import DaqDeviceInfo


def config_first_detected_device(board_num, dev_id_list=None):
    ul.ignore_instacal()
    devices = ul.get_daq_device_inventory(InterfaceType.ANY)
    if not devices:
        raise Exception('Error: No DAQ devices found')

    print('\n\nFound %d DAQ devices:' % len(devices))
    for device in devices:
        print('  ', device.product_name, ' (', device.unique_id, ') - ',
              'Device ID = ', device.product_id, sep='')

    device = devices[0]
    if dev_id_list:
        device = next((device for device in devices
                       if device.product_id in dev_id_list), None)
        if not device:
            err_str = 'Error: No DAQ device found in device ID list: '
            err_str += ','.join(str(dev_id) for dev_id in dev_id_list)
            raise Exception(err_str)

    ul.create_daq_device(board_num, device)



def DIO_in(port_kind="A", bit_num=0): # port A, B, C

    use_device_detection = True
    dev_id_list = []
    board_num = 0

    try:
        config_first_detected_device(board_num, dev_id_list)
        daq_dev_info = DaqDeviceInfo(board_num)
        dio_info = daq_dev_info.get_dio_info()

        for port in dio_info.port_info:
           if port.supports_input:
               if port.type.name[-1] == port_kind:

                    ul.d_config_port(board_num, 
                                     port.type, 
                                     DigitalIODirection.IN)

                    port_value = ul.d_in(board_num, port.type)
                    bit_value =  (port_value >> bit_num) & 1

                    #bit_value = ul.d_bit_in(board_num, port.type, bit_num)

                    print("\n\n>>> Port %s = %d, bit %d = %d\n\n" % (port.type.name, port_value, bit_num, bit_value))
                    return bit_value

    except Exception as e:
        print('\n', e)
        return -1
    finally:
        if use_device_detection:
            ul.release_daq_device(board_num)

def check_BK_door():
    return DIO_in("A", 0)