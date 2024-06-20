eVOLVER Server Code
===================

This code sits on the eVOLVER Raspberry Pi and handles communications between the DPU and the SAMD21 microcontrollers that monitor and actuate experimental parameters. Calibrations, experiment commands, and data transmission are all handled by this code using `python socket-io <https://python-socketio.readthedocs.io/en/latest/>`_ and `pyserial <https://pythonhosted.org/pyserial/>`_.

For more information check the `wiki <https://khalil-lab.gitbook.io/evolver/software/server-code-structure>`_.

Installation
============

eVOLVER units should come with this software pre-installed.

If you are making an eVOLVER from scratch or are replacing a broken Raspberry Pi, you can follow these guides:
* `Raspberry Pi configuration <https://khalil-lab.gitbook.io/evolver/guides/raspberry-pi-configuration>`_
* `Updating the eVOLVER server <https://khalil-lab.gitbook.io/evolver/guides/updating-the-evolver-server>`_

Calibration Conversion
======================

If you desire to update an older evolvers calibrations to the current release formatting, use the script located at ``utls/calibration_transformation.py``. To run:

``python3.6 utils/calibration_transformation.py -d evolver/calibrations -f evolver/calibrations.json``
