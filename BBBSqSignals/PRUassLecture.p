// --- PULSE READER PRU ---

.origin 0
.entrypoint INIT

#include "PRUassLecture.hp"

#define PIN_MASK 0x0F

// r1  = pulses detectedd counter
// r2  = previous sample
// r3  = remaining iterations(2 muestras por iteracion, 12 ciclos = 60 ns), stops counting when 0.
// r7  = edge detections
// r12 = actual sample
// r14 = destino en shared RAM

INIT:
    // Habilitar OCP (obligatorio para Shared RAM y comunicacion con ARM)
    LBCO    r0, CONST_PRUCFG, 4, 4
    CLR     r0, r0, 4
    SBCO    r0, CONST_PRUCFG, 4, 4
    MOV     r14, 0x10000

MAIN_LOOP:
    QBBC    MAIN_LOOP, r31, 30
    LDI     r0, 21                  // ARM_PRU0_INTERRUPT
    SBCO    r0, C0, 0x24, 4         // SICR: limpia el evento 21

    LDI     r1, 0
    MOV     r3, 4166666             // time window = r3 * 60 ns = 0,250 s
    AND     r12, r31, PIN_MASK      // Initial sample
    NOT     r2, r12                 // Previous sample while inverting it

COUNT_LOOP:                         // 
    AND     r12, r31, PIN_MASK      // 1. Selecting just the four first bits of r31 and saving into r12
    AND     r7,  r12, r2            // 2. As r2 is inverted, when doing and, just 1 if the previous sample has detected a zero
    NOT     r2,  r12                // 3. The actual from the previous becomes now the previous
    MIN     r7,  r7, 1              // 4. If r7 register a pulse in channel 4, 3 or 2 will count 8, 5 or 2 respectively. Min compares r7 with 1 and selects the minimum, will be 1 or 0.
    ADD     r1,  r1, r7             // 5. Sum 0 o 1
    SUB     r3,  r3, 1              // 6. Substracting one to the counter r3
    AND     r12, r31, PIN_MASK      // 7. Selecting the following sample
    AND     r7,  r12, r2            // 8. And so on
    NOT     r2,  r12                // 9
    MIN     r7,  r7, 1              // 10
    ADD     r1,  r1, r7             // 11
    LDI     r4,  0
    LDI     r4,  0
    LDI     r4,  0
    LDI     r4,  0
    QBNE    COUNT_LOOP, r3, 0       // 12

    SBBO    r1, r14, 0, 4
    MOV     r31.b0, PRU0_ARM_INTERRUPT + 16
    JMP     MAIN_LOOP

EXIT:
    HALT
ERR:
    HALT