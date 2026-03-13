#!bin/bash

ID="0930:6544"
MountPoint="/mnt/mi_usb"

sudo mkdir -p "$MountPoint""

if lsusb -d "$ID" > /dev/null; then
	echo "Hardware mounted"
	if mountpoint -q "MountPoint"; then
		echo "Device ready in $MountPoint"
	else
		sudo mount /dev/sda1 "$MountPoint" 2>/dev/null
		if [ $? -eq 0 ]; then
			echo "Succesfull, files available in the mount point"
		else
			echo "Error"
		fi
	fi
echo "USB content:"
ls "$MountPoint"
else
	echo "Hardware not detected"
fi
