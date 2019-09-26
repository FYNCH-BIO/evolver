eVOLVER Server Code
===================

This code sits on the eVOLVER raspberry pi and handles communications between the DPU and the SAMD21 microcontrollers that monitor and actuate experimental parameters. Calibrations, experiment commands, and data transmission are all handled by this code using `python socket-io <https://python-socketio.readthedocs.io/en/latest/>`_ and `pyserial <https://pythonhosted.org/pyserial/>`_.

Installation
============

eVOLVER units should come with this software pre-installed. If you need to, you can install all dependencies by running the following command:

``python3.6 setup.py install``

NOTE: You must use python3.6 at this point in time - some of the dependencies currently do not work on 3.7.

Running the server
==================

We use `supervisor <http://supervisord.org/running.html>`_ to run and manage the logs for the eVOLVER server. eVOLVERs should come pre-configured. We also provide a utility monitoring and restart script, ``evolvercron`` and ``server_monitor.sh``. To use, add the crontab job line in ``evolvercron`` into your cron installation.

Calibration Conversion
======================

If you desire to update an older evolvers calibrations to the current release formatting, use the script located at ``utls/calibration_transformation.py``. To run:

``python3.6 utils/calibration_transformation.py -d evolver/calibrations -f evolver/calibrations.json``


