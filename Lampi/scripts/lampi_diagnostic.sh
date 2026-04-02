#!/bin/bash
# =============================================================================
# LAMPI Touchscreen & Display Diagnostic Script
# =============================================================================
#
# Run this script on your Raspberry Pi when the touchscreen stops working
# after a reboot. It collects device, service, and configuration state
# into a tarball you can send to the instructor for diagnosis.
#
# IMPORTANT: When touch stops working after reboot, don't reboot again!
#            Run this script first to capture the current state.
#
# Usage:
#   bash ~/connected-devices/Lampi/scripts/lampi_diagnostic.sh
#
# Then scp the resulting .tar.gz from /tmp/ to your laptop and email it
# to the instructor.
# =============================================================================

set -uo pipefail

HOSTNAME=$(hostname)
TIMESTAMP=$(date +%Y%m%d-%H%M%S)
DIAG_DIR="/tmp/lampi-diag-${HOSTNAME}-${TIMESTAMP}"
TARBALL="/tmp/lampi-diag-${HOSTNAME}-${TIMESTAMP}.tar.gz"

mkdir -p "${DIAG_DIR}"

echo "============================================"
echo "  LAMPI Diagnostic Script"
echo "============================================"
echo ""
echo "Collecting diagnostic data into: ${DIAG_DIR}"
echo ""

# Helper: run a command, capture output, don't fail the script if it errors
capture() {
    local outfile="${DIAG_DIR}/$1"
    shift
    echo "  Capturing: $*"
    {
        echo "# Command: $*"
        echo "# Captured: $(date)"
        echo ""
        "$@" 2>&1 || echo "[command exited with status $?]"
    } >> "${outfile}"
}

# Helper: capture contents of a file
capture_file() {
    local outfile="${DIAG_DIR}/$1"
    local srcfile="$2"
    echo "  Capturing file: ${srcfile}"
    {
        echo "# File: ${srcfile}"
        echo "# Captured: $(date)"
        echo ""
        if [ -f "${srcfile}" ]; then
            cat "${srcfile}" 2>&1
        else
            echo "[file does not exist]"
        fi
    } >> "${outfile}"
}

# ---- System Info ----
echo ""
echo "--- System Info ---"
capture system_info.txt hostname
capture system_info.txt uname -a
capture system_info.txt cat /etc/debian_version
capture system_info.txt uptime
capture system_info.txt date

# ---- Device State ----
echo ""
echo "--- Device State ---"
capture device_state.txt ls -la /dev/input/by-path/
capture device_state.txt ls -la /dev/input/event*
capture device_state.txt readlink -f /dev/input/by-path/platform-3f804000.i2c-event
capture device_state.txt ls -la /dev/dri/by-path/
capture device_state.txt ls -la /dev/dri/card*
# Use glob to find SPI DRM card symlink (bus address varies by Pi model)
{
    echo "# Command: readlink -f /dev/dri/by-path/platform-*spi*-card"
    echo "# Captured: $(date)"
    echo ""
    readlink -f /dev/dri/by-path/platform-*spi*-card 2>&1 || echo "[no SPI DRM by-path symlink found]"
} >> "${DIAG_DIR}/device_state.txt"
echo "  Capturing: readlink -f /dev/dri/by-path/platform-*spi*-card"

# ---- Input Devices ----
echo ""
echo "--- Input Devices ---"
capture proc_input_devices.txt cat /proc/bus/input/devices

# ---- Udev Info ----
echo ""
echo "--- Udev Info ---"
capture udev_info.txt udevadm info --query=all --name=/dev/input/by-path/platform-3f804000.i2c-event
# Use glob for SPI DRM device (bus address varies by Pi model)
for spi_card in /dev/dri/by-path/platform-*spi*-card; do
    if [ -e "${spi_card}" ]; then
        capture udev_info.txt udevadm info --query=all --name="${spi_card}"
    fi
done
# also dump udev info for all input event devices
for dev in /dev/input/event*; do
    if [ -e "${dev}" ]; then
        capture udev_info.txt udevadm info --query=all --name="${dev}"
    fi
done
for dev in /dev/dri/card*; do
    if [ -e "${dev}" ]; then
        capture udev_info.txt udevadm info --query=all --name="${dev}"
    fi
done

# ---- Service Status ----
echo ""
echo "--- Service Status ---"
capture service_status.txt systemctl status lampi_app.service --no-pager
capture service_status.txt systemctl status lampi_service.service --no-pager
capture service_status.txt systemctl status lampi_pigpio.service --no-pager
capture service_status.txt systemctl is-failed lampi_app.service
capture service_status.txt systemctl is-failed lampi_service.service
capture service_status.txt systemctl is-failed lampi_pigpio.service

# ---- Journal Logs (current boot) ----
echo ""
echo "--- Journal Logs ---"
capture journal_lampi_app.txt journalctl -b -u lampi_app.service --no-pager -n 100
capture journal_lampi_service.txt journalctl -b -u lampi_service.service --no-pager -n 100
capture journal_lampi_pigpio.txt journalctl -b -u lampi_pigpio.service --no-pager -n 100

# ---- Kernel Messages ----
echo ""
echo "--- Kernel Messages ---"
{
    echo "# Command: dmesg (filtered for display/touch keywords)"
    echo "# Captured: $(date)"
    echo ""
    dmesg 2>&1 | grep -iE 'i2c|spi|drm|input|hid|cec|pitft|stmpe|ft6|event|card' || echo "[no matching lines]"
} > "${DIAG_DIR}/dmesg_filtered.txt"
echo "  Capturing: dmesg (filtered)"

capture dmesg_full.txt dmesg

# ---- Boot Configuration ----
echo ""
echo "--- Boot Configuration ---"
capture_file config_txt.txt /boot/firmware/config.txt
capture_file cmdline_txt.txt /boot/firmware/cmdline.txt

# ---- Kivy Configuration ----
echo ""
echo "--- Kivy Configuration ---"
capture_file kivy_config.txt /home/pi/.kivy/config.ini

# ---- Installed Service Files ----
echo ""
echo "--- Installed Service Files ---"
capture_file lampi_app_service_file.txt /etc/systemd/system/lampi_app.service

# ---- Permissions ----
echo ""
echo "--- Permissions ---"
capture permissions.txt id pi
capture permissions.txt ls -la /dev/dri/card*
capture permissions.txt ls -la /dev/input/by-path/platform-3f804000.i2c-event
capture permissions.txt getfacl /dev/dri/card*
capture permissions.txt groups pi

# ---- Create Tarball ----
echo ""
echo "--- Creating tarball ---"
tar czf "${TARBALL}" -C /tmp "$(basename "${DIAG_DIR}")"

echo ""
echo "============================================"
echo "  Diagnostic collection complete!"
echo "============================================"
echo ""
echo "Tarball: ${TARBALL}"
echo ""
echo "To copy it to your laptop, run from your laptop:"
echo "  scp pi@<your-lampi-ip>:${TARBALL} ."
echo ""
echo "Then email/upload the tarball to the instructor."
echo "============================================"
