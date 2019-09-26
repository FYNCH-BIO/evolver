import os
import sys
import json
import time
import optparse

FITTED_CAL_DIRECTORY = "fittedCal"
RAW_CAL_DIRECTORY = "rawCal"
OD_CAL_DIRECTORY = "od"
TEMP_CAL_DIRECTORY = "temp"
VALID_PARAMS = ['od', 'temp', 'od90', 'od135']

def process_old_directory(directory):
    raw_cal_directory = os.path.join(directory, RAW_CAL_DIRECTORY)
    fitted_cal_directory = os.path.join(directory, FITTED_CAL_DIRECTORY)
    od_cal_raw_directory = os.path.join(directory, RAW_CAL_DIRECTORY, OD_CAL_DIRECTORY)
    temp_cal_raw_directory = os.path.join(directory, RAW_CAL_DIRECTORY, TEMP_CAL_DIRECTORY)
    od_cal_fit_directory = os.path.join(directory, FITTED_CAL_DIRECTORY, OD_CAL_DIRECTORY)
    temp_cal_fit_directory = os.path.join(directory, FITTED_CAL_DIRECTORY, TEMP_CAL_DIRECTORY)

    if not os.path.exists(raw_cal_directory) or not os.path.exists(fitted_cal_directory):
        print("Data directories do not exist in " + directory)
        sys.exit(1)

    # Process raw data first
    measured_od_datas, raw_od_calibrations = process_raw(od_cal_raw_directory)
    measured_temp_datas, raw_temp_calibrations = process_raw(temp_cal_raw_directory)

    # Process fits
    od_fit_calibrations = process_fit(od_cal_fit_directory, 'sigmoid', ['od_90'])
    temp_fit_calibrations = process_fit(temp_cal_fit_directory, 'linear', ['temp'])

    cals = get_cal_list(raw_od_calibrations, measured_od_datas, od_fit_calibrations, 'od')
    cals = cals + get_cal_list(raw_temp_calibrations, measured_temp_datas, temp_fit_calibrations, 'temperature')

    return cals

def process_raw(calibration_raw_directory):
    raw_calibrations = {}
    measured_datas = {}
    for filename in os.listdir(calibration_raw_directory):
        filename_split = filename.split('.')[0]
        raw_calibrations[filename_split] = []
        with open(os.path.join(calibration_raw_directory, filename)) as f:
            data = json.load(f)
            vial_datas = data.get('vialData')
            measured_datas[filename_split] = [data.get("inputData")] * 16
            cal_datas = {'od90': [0] * 16, 'od135': [0] * 16, 'temp': [0] * 16, 'od': [0] * 16}
            for step in vial_datas:
                for param, param_vial_datas in step.items():
                    if param in VALID_PARAMS:
                        for i, vial_data in enumerate(param_vial_datas):
                            cal_datas[param][i] = [0] * 16
                            for j in range(16):
                                index_change = -j + i
                                cal_datas[param][i][j] = param_vial_datas[index_change]
                        raw_calibrations[filename_split].append(create_raw(param, filename_split, cal_datas[param]))
    return measured_datas, raw_calibrations

def process_fit(calibration_fit_directory, fit_type, params):
    fit_calibrations = {}
    active = True
    for filename in os.listdir(calibration_fit_directory):
        fit = process_old_fit(os.path.join(calibration_fit_directory, filename), filename, fit_type, active, params)
        fit_calibrations[filename.split('.')[0]] = [fit]
        active = False
    return fit_calibrations

def get_cal_list(raw_calibrations, measured_datas, fit_calibrations, cal_type):
    cals = []
    for filename in raw_calibrations.keys():
        try:
            new_cal = {"name": filename, "calibrationType": cal_type, "timeCollected": time.time(), "measuredData": measured_datas[filename], "raw": raw_calibrations[filename], "fits":fit_calibrations[filename]}
            cals.append(new_cal)
        except KeyError:
            print('Key error - skipping ' + filename)
    return cals
 
def process_old_fit(filename, name, fit_type, active, params):
    coefficients = []
    with open(filename) as f:
        lines = f.read().strip().split('\n')
        for line in lines:
            data = line.strip().split(',')
            for i, datum in enumerate(data):
                if len(coefficients) <= i:
                    coefficients.append([])
                coefficients[i].append(float(datum))
    return create_fit(name, coefficients, fit_type, bool(active), params)

def create_fit(name, coefficients, fit_type, active, params):
    return {'name': name, 'coefficients': coefficients, 'type':fit_type, 'timeFit': time.time(), 'active': active, 'params': params}

def create_raw(param, name, vial_data):
    return {'param': param, 'vialData': vial_data, 'name': name, 'timeCollected': time.time()}

if __name__ == '__main__':
    parser = optparse.OptionParser()
    parser.add_option('-d', '--directory', action = 'store', dest = 'directory', help = 'Location of old calibration directory')
    parser.add_option('-f', '--file', action = 'store', dest = 'filename', help = 'Filename of new calibration file')

    (options, args) = parser.parse_args()
    directory = options.directory
    filename = options.filename

    if not os.path.isdir(directory):
        print("Calibration directory does not exist " + directory)
        sys.exit(2)

    cals = process_old_directory(directory)

    with open(filename, 'w') as f:
        json.dump(cals, f)