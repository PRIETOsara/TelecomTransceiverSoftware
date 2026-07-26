# Telecom Transceiver Software


---

## Overview

This repository contains the software and scripts required to operate the project. The core processing unit is a **BeagleBone Black (BBB)**, which utilizes its Programmable Real-Unit (PRU) cores to execute and manage precise hardware signals for the telecom transceivers.

---

## Project Structure

Here is a quick map of how the project is organized:

* **`BBBDTSscripts/`** – Contains Device Tree Source (`.dts`) files, compiled overlays (`.dtbo`), and configuration files (such as `uEnv.txt` and Makefiles) used to configure the pin muxing and hardware peripherals on the BeagleBone Black.
* **`BBBSqSignals/`** – Houses the main C++ source files, header files, and compiled PRU binary assembly files (`.p` and `.bin`) responsible for generating pulses.
* **`BBBSscripts/`** – Containig the sime files as "BBBDTSscripts" but reduced. Used as a backup.
* **`InternalTransceiverConnectionScripts/`** – Python scripts necessaries to access internally the QSFP28 modules.
* **`Tools`** – Includes helper shell scripts (`.sh`) for automating tasks, configuring pin layouts, setting up PWM, launching PRU signal generation, and compiling/deploying code directly to the BBB.
* **`am335x_pru_package`** – A public library integrated to initialize and interface with the PRU subsystem of the AM335x processor on the BBB.

---
