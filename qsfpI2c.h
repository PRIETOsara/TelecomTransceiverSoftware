#ifndef QSFP_I2C_H
#define QSFP_I2C_H

#include <linux/i2c-dev.h>
#include <linux/i2c.h>
#include <sys/ioctl.h>
#include <fcntl.h>
#include <unistd.h>
#include <cstdio>
#include <cerrno>
#include <cstring>

// Minimal QSFP control: laser (Tx) and detector (Rx) on/off only.
// Bus 2, address 0x50  (BeagleBone /dev/i2c-2, QSFP lower page).
//
// Register map used:
//   Page 0, byte 86  -> Tx disable  (bit n = 1 -> lane n laser OFF)
//   Page 3, byte 241 -> Rx output disable (bit n+4 = 1 -> lane n detector OFF)
//
// NOTE: on QSFP-LR4-40G, opt194 = 0x00, so Rx output disable is NOT
// implemented by the module. detector_off()/on() will write the byte but
// the optics will ignore it. The methods are kept so the API is uniform.
class QsfpI2c {
public:
    explicit QsfpI2c(const char* dev = "/dev/i2c-2", int addr = 0x50)
        : addr_(addr) { fd_ = ::open(dev, O_RDWR); }

    ~QsfpI2c() { if (fd_ >= 0) ::close(fd_); }

    bool ok() const { return fd_ >= 0; }

    // ---- laser (Tx) -----------------------------------------------------
    // All four lanes at once.
    bool laser_on()  { return write8(86, 0x00); }   // 0 = laser enabled
    bool laser_off() { return write8(86, 0x0F); }   // 1 = laser disabled

    // Single lane (1..4). Preserves the other three bits.
    bool laser_on(int lane)  { return laser_set(lane, false); }
    bool laser_off(int lane) { return laser_set(lane, true);  }

    // ---- detector (Rx) --------------------------------------------------
    // All four lanes at once. Requires page 3 selected.
    bool detector_on()  { return detector_write(0x00); }
    bool detector_off() { return detector_write(0xF0); }

    // Single lane (1..4). Read-modify-write on page 3 byte 241.
    bool detector_on(int lane)  { return detector_set(lane, false); }
    bool detector_off(int lane) { return detector_set(lane, true);  }

    // ---- raw helpers (for readback / debug) -----------------------------
    bool read8(int reg, int* val) {
        unsigned char r = (unsigned char)reg, v = 0;
        struct i2c_msg msgs[2] = {
            { (unsigned short)addr_, 0, 1, &r },
            { (unsigned short)addr_, I2C_M_RD, 1, &v }
        };
        struct i2c_rdwr_ioctl_data xfer = { msgs, 2 };
        if (::ioctl(fd_, I2C_RDWR, &xfer) < 0) {
            std::fprintf(stderr, "[QSFP] read 0x%02X: %s\n",
                         reg, std::strerror(errno));
            return false;
        }
        *val = v;
        return true;
    }

    bool write8(int reg, int val) {
        unsigned char buf[2] = { (unsigned char)reg, (unsigned char)val };
        struct i2c_msg msg = { (unsigned short)addr_, 0, 2, buf };
        struct i2c_rdwr_ioctl_data xfer = { &msg, 1 };
        if (::ioctl(fd_, I2C_RDWR, &xfer) < 0) {
            std::fprintf(stderr, "[QSFP] write 0x%02X=0x%02X: %s\n",
                         reg, val, std::strerror(errno));
            return false;
        }
        return true;
    }

private:
    // Laser: page 0, byte 86. Bit set = disabled.
    bool laser_set(int lane, bool disable) {
        if (lane < 1 || lane > 4) return false;
        int cur = 0;
        if (!read8(86, &cur)) return false;
        int mask = 1 << (lane - 1);
        int val  = disable ? (cur | mask) : (cur & ~mask);
        return write8(86, val);
    }

    // Detector: page 3, byte 241. Bits 4..7 map to lanes 1..4.
    // Select page 3, read-modify-write, then always restore page 0.
    bool detector_set(int lane, bool disable) {
        if (lane < 1 || lane > 4) return false;
        if (!select_page(3)) return false;
        int cur = 0;
        bool ok = read8(241, &cur);
        if (ok) {
            int mask = 1 << (lane + 3);           // lane 1 -> bit 4, lane 4 -> bit 7
            int val  = disable ? (cur | mask) : (cur & ~mask);
            ok = write8(241, val);
        }
        ok = select_page(0) && ok;                // always return to page 0
        return ok;
    }

    bool detector_write(int value) {
        if (!select_page(3)) return false;
        bool ok = write8(241, value);
        ok = select_page(0) && ok;                // always return to page 0
        return ok;
    }

    bool select_page(int page) { return write8(127, page); }

    int fd_ = -1;
    int addr_;
};

#endif // QSFP_I2C_H