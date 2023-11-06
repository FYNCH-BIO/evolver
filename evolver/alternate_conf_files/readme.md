Server Configuration Files (conf.yml)
===

## Summary

Configuration files (conf.yml) contain the parameters for the server to run.

For more information check the wiki [page](https://khalil-lab.gitbook.io/evolver/software/server-code-structure/configuration-files-conf.yml).

## Examples of potential alternate conf files
- Calibration conf - (default conf) broadcast_timing parameter should be low to speed up calibration
- stir_pause_on_od - prevents stirring from affecting OD. Important if bubbling or in low volume applications
- odled_normally_off - OD LED will be normally off unless OD is read to prevent the IR light affecting other light sensors
