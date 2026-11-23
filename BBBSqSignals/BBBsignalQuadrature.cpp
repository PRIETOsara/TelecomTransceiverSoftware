#include "BBBsignalQuadrature.h"
#include <iostream>
#include <unistd.h> // for sleep
#include <signal.h>
#include <cstring>
#include <thread>
#include <pthread.h>
#include <chrono>   // time management
#include <cmath>
#include <poll.h>
#include <stdio.h>
#include <sys/mman.h>
#include <fcntl.h>
#include <prussdrv.h>
#include <pruss_intc_mapping.h>

// >>> QSFP: minimal I2C control for laser (Tx) and detector (Rx) on/off.
// Put QsfpI2c.h next to this .cpp (the header is self-contained).
#include "QsfpI2c.h"
// <<< QSFP

#define PRU_ClockPhys_NUM 1    // PRU1
#define PRU_HandlerSynch_NUM 0 // PRU0

// Memory / PRU defines (kept from your original file)
#define AM33XX_PRUSS_IRAM_SIZE 8192
#define AM33XX_PRUSS_DRAM_SIZE 8192
#define AM33XX_PRUSS_SHAREDRAM_SIZE 12000

#define PRU_ADDR   0x4A300000
#define PRU_LEN    0x80000

#define DDR_BASEADDR 0x80000000
#define OFFSET_DDR 0x00001000
#define SHAREDRAM 0x00010000
#define OFFSET_SHAREDRAM 0x00000000

#define PRU0_DATARAM 0x00000000
#define PRU1_DATARAM 0x00002000
#define DATARAMoffset 0x00000200

#define PRUSS0_PRU0_DATARAM 0
#define PRUSS0_PRU1_DATARAM 1
#define PRUSS0_PRU0_IRAM 2
#define PRUSS0_PRU1_IRAM 3
#define PRUSS0_SHARED_DATARAM 4

using namespace std;

namespace exploringBBBCKPD {

// If your header already declares these static members, these definitions match them.
// Otherwise, these definitions correspond to the members used in the rest of the file.
void* CKPD::ddrMem = nullptr;
void* CKPD::sharedMem = nullptr;
void* CKPD::pru0dataMem = nullptr;
void* CKPD::pru1dataMem = nullptr;
void* CKPD::pru_int = nullptr;

unsigned int* CKPD::sharedMem_int = nullptr;
unsigned int* CKPD::pru0dataMem_int = nullptr;
unsigned int* CKPD::pru1dataMem_int = nullptr;

int CKPD::mem_fd = -1;

CKPD* g_agentInstance = nullptr;

// >>> QSFP: one global I2C handle. Opened once, lives for the process.
//      Non-fatal if /dev/i2c-2 is missing (qsfp_ok stays false).
static QsfpI2c g_qsfp;
static bool    g_qsfp_ok = false;
// <<< QSFP

// Global / module-local timeout (microseconds) for waiting PRU interrupt.
// If the header already defines WaitTimeInterruptPRU0, you can remove this line there.
// Setting to 15 seconds to be safe (PRU counts 10s).

CKPD::CKPD() {
    tpruss_intc_initdata pruss_intc_initdata = PRUSS_INTC_INITDATA;
    prussdrv_init();

    if (prussdrv_open(PRU_EVTOUT_0) == -1) {
        perror("prussdrv_open(PRU_EVTOUT_0) failed.");
    }
    if (prussdrv_open(PRU_EVTOUT_1) == -1) {
        perror("prussdrv_open(PRU_EVTOUT_1) failed.");
    }

    prussdrv_pruintc_init(&pruss_intc_initdata);

    // Clear possible pending events
    prussdrv_pru_clear_event(PRU_EVTOUT_0, PRU0_ARM_INTERRUPT);
    prussdrv_pru_clear_event(PRU_EVTOUT_1, PRU1_ARM_INTERRUPT);

    // Map memories (LOCAL_DDMinit will apply DATARAMoffset to PRU data RAM)



    // Load PRU binaries
    if (prussdrv_exec_program(PRU_HandlerSynch_NUM, "./PRUassLecture.bin") == -1) {
        perror("prussdrv_exec_program failed: PRU0 (PRUassLecture.bin)");
    }
    // Start generator PRU1
    if (prussdrv_exec_program(PRU_ClockPhys_NUM, "./PRUassTrigSigScriptHist4Sig.bin") == -1) {
        perror("prussdrv_exec_program failed: PRU1 (PRUassTrigSigScriptHist4Sig.bin)");
    }
    sleep(1); // let PRUs initialize
    LOCAL_DDMinit();

    // Initialize time tracking variables if present in header/class
    // These members assumed to exist in the header: TimePointClockCurrentInitial, TimeAdjPeriod, etc.
    this->TimePointClockCurrentInitial = ClockWatch::now();
    this->requestWhileWait = this->SetWhileWait();

    // >>> QSFP: bring up I2C and leave the module with lasers ON, detectors ON.
    g_qsfp_ok = g_qsfp.ok();
    if (g_qsfp_ok) {
        g_qsfp.laser_on();      // P0 b86 = 0x00  TX all 4 lasers enabled
        g_qsfp.detector_on();   // P3 b241 = 0x00 RX all 4 detectors enabled (no-op on LR4-40G)
    } else {
        cerr << "[QSFP] /dev/i2c-2 not available; laser/detector control disabled\n";
    }
    // <<< QSFP

    cout << "System initiated. Generating pulse bursts and ready to acquire..." << endl;
}

// Signal handler
void handle_signal(int sig) {
    if (g_agentInstance != nullptr) {
        g_agentInstance->m_exit();
    }
}

// Main acquisition function adapted for 10s measurement window
int CKPD::HandleInterruptSynchPRU() {
    printf("\n[HOST] Measure of 0.25s...\n");

    // >>> QSFP: lasers ON for the measurement window.
    if (g_qsfp_ok){
        //g_qsfp.laser_on();   // TX all 4 lasers enabled
        g_qsfp.detector_on();   // RX all 4 detectors disabled
    }
    // <<< QSFP

    pru1dataMem_int[0] = 1; // Command to action
    // Start generator PRU1
    prussdrv_pru_send_event(22);

    pru0dataMem_int[0] = 1;
    // 1) Trigger PRU via the memory handshake (pru0dataMem_int points to OWN_RAM + 0x200)
    prussdrv_pru_send_event(21);

    // 2) Wait for PRU0 to finish (PRU0 will raise PRU_EVTOUT_0 when done)
    int ret = prussdrv_pru_wait_event_timeout(PRU_EVTOUT_0, WaitTimeInterruptPRU0);

    if (ret > 0) {
        // PRU signaled completion
        prussdrv_pru_clear_event(PRU_EVTOUT_0, PRU0_ARM_INTERRUPT);
        printf("PRU0 Everything OK");
        // Read result: PRU wrote total pulses into sharedMem_int[0]
        unsigned int totalPulsos = sharedMem_int[0];
        /*unsigned int totalPulsosCH1 = sharedMem_int[0];
        unsigned int totalPulsosCH2 = sharedMem_int[1];        
        unsigned int totalPulsosCH3 = sharedMem_int[2];
        unsigned int totalPulsosCH4 = sharedMem_int[3];*/

        printf("------------------------------------------------\n");
        printf("FINAL RESULT (time window):\n");
        printf(" -> Total pulses: %d\n", totalPulsos);
        /*printf(" -> Pulsos Totales CH1: %d\n", totalPulsosCH1);
        printf(" -> Pulsos Totales CH2: %d\n", totalPulsosCH2);
        printf(" -> Pulsos Totales CH3: %d\n", totalPulsosCH3);
        printf(" -> Pulsos Totales CH4: %d\n", totalPulsosCH4);*/          
        printf("------------------------------------------------\n");
    }
    else {
        prussdrv_pru_clear_event(PRU_EVTOUT_0, PRU0_ARM_INTERRUPT);
        cout << "Error en prussdrv_pru_wait_event_timeout()" << endl;
    }

    // 2) Wait for PRU1 to finish (PRU1 will raise PRU_EVTOUT_0 when done)
    ret = prussdrv_pru_wait_event_timeout(PRU_EVTOUT_1, WaitTimeInterruptPRU1);

    if (ret > 0) {
        // PRU signaled completion
        prussdrv_pru_clear_event(PRU_EVTOUT_1, PRU1_ARM_INTERRUPT);
        printf("PRU1 Everything OK");
    }
    else {
        prussdrv_pru_clear_event(PRU_EVTOUT_1, PRU1_ARM_INTERRUPT);
        cout << "Error en prussdrv_pru_wait_event_timeout()" << endl;
    }

    // >>> QSFP: lasers OFF after the measurement window.
    if (g_qsfp_ok){
    //    g_qsfp.laser_off();  // TX all 4 lasers disabled
        g_qsfp.detector_off();   // RX all 4 detectors disabled
    }
    // <<< QSFP

    return 0;
}

// Timing helper (keeps same behavior as your original)
struct timespec CKPD::SetWhileWait() {
    struct timespec req;
    this->TimePointClockCurrentFinal =
        this->TimePointClockCurrentInitial + std::chrono::nanoseconds(this->TimeAdjPeriod);
    this->TimePointClockCurrentInitial = this->TimePointClockCurrentFinal;

    auto duration = this->TimePointClockCurrentFinal.time_since_epoch();
    long long ns = std::chrono::duration_cast<std::chrono::nanoseconds>(duration).count();

    req.tv_sec = static_cast<long>(ns / 1000000000);
    req.tv_nsec = static_cast<long>(ns % 1000000000);
    return req;
}

// LOCAL_DDMinit: map memories and apply DATARAMoffset for PRU data RAMs
int CKPD::LOCAL_DDMinit() {
   // SHARED RAM (para leer el total de pulsos)
    prussdrv_map_prumem(PRUSS0_SHARED_DATARAM, &sharedMem);
    sharedMem_int = (unsigned int*) sharedMem;


    prussdrv_map_prumem(PRUSS0_PRU0_DATARAM, &pru0dataMem);
    pru0dataMem_int = (unsigned int*) pru0dataMem;
    // Ahora: pru0dataMem_int[0] → dirección física 0x200

    // === PRU1 (TRANSMISOR / GENERADOR) ===
    // El firmware antiguo de PRU1 espera SU COMANDO en offset 0 (NO en 0x200)
    prussdrv_map_prumem(PRUSS0_PRU1_DATARAM, &pru1dataMem);
    pru1dataMem_int = (unsigned int*) pru1dataMem;
    // Ahora: pru1dataMem_int[0] → dirección física 0x00 (correcto)

    return 0;
}

int CKPD::Killsignalpru() {
    if (prussdrv_exec_program(PRU_HandlerSynch_NUM, "./PRUkillSignal.bin") == -1) {
        perror("prussdrv_exec_program failed ./PRUkillSignal.bin");
    }
    return 0;
}

int CKPD::DisablePRUs() {
    prussdrv_pru_disable(PRU_ClockPhys_NUM);
    prussdrv_pru_disable(PRU_HandlerSynch_NUM);
    return 0;
}

CKPD::~CKPD() {
    // >>> QSFP: leave the module in a sane state (lasers ON, detectors ON).
    if (g_qsfp_ok) {
        g_qsfp.laser_off();      // TX all 4 lasers disabled
        g_qsfp.detector_off();   // RX all 4 detectors disabled
    }
    // <<< QSFP

    // Safety cleanup
    this->Killsignalpru();
    this->DisablePRUs();
    sleep(1);
    prussdrv_exit();
}

} // namespace exploringBBBCKPD

using namespace exploringBBBCKPD;

int main(int argc, char const* argv[]) {
    cout << "CKPDagent started..." << endl;

    CKPD CKPDagent;
    g_agentInstance = &CKPDagent;

    signal(SIGINT, handle_signal);
    CKPDagent.m_start();

    bool isValidWhileLoop = (CKPDagent.getState() != CKPD::APPLICATION_EXIT);

    cout << "Starting continuous measurement loop (Ctrl+C to stop)..." << endl;

    while (isValidWhileLoop) {
        switch (CKPDagent.getState()) {
            case CKPD::APPLICATION_RUNNING:
                CKPDagent.HandleInterruptSynchPRU();
                break;

            default:
                isValidWhileLoop = false;
                break;
        }
        sleep(1);
    }

    cout << "Exiting the BBBclockKernelPhysicalDaemon" << endl;
    return 0;
}