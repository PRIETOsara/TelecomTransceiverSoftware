// --- SCRIPT MINIMAL DE PRU ---
// Solo mantiene la lógica de interrupciones Host → PRU y PRU → Host

.origin 0
.entrypoint INIT

#include "PRUassLecture.hp"

#define PIN_MASK 0x0F
// r31  input register
// r30  output register
// r1   for pulse counting
// r2   actual sample
// r3   number of iterations. 2 000 000 means 0,1s. 20 000 000 means 1s.
// r12  previous detection (1 or 0)
// r7   final valid value

// r6 for 0 detections
// r12 for 1 detections

INIT:
    // Habilitar OCP (obligatorio para Shared RAM y comunicación con ARM)
    LBCO    r0, CONST_PRUCFG, 4, 4
    CLR     r0, r0, 4
    SBCO    r0, CONST_PRUCFG, 4, 4
    MOV     r14, 0x10000

MAIN_LOOP:
    // Esperar interrupción del host (bit 30 de r31)
    QBBC    MAIN_LOOP, r31, 30

    // Limpiar la interrupción del host
    MOV     r0, 0
    SBCO    r0, C0, 0x24, 1   // Limpia host interrupt (R31.30)
    MOV     r1, 0           
    MOV     r3, 2000000 // sample window
COUNT_LOOP:

    MOV     r12, r31
    AND     r12, r12, PIN_MASK      // Selecting just the four first bits.
    NOT     r12, r12                // Inverting the first sample, as the constraint is to have a 0 before a 1

    MOV     r2, r31                 // Copying the register 31 in r2 (the value has moved 3 instructions = 15ns)
    AND     r2, r2, PIN_MASK 

    AND     r7, r2, r12             // If r12 has detected some pulse, r7 = 0 and discarted
    MIN     r7, r7, 1               // r7 will contain the lower value: 0 or 1
    
    QBEQ    LOOP_END, r7, 0         // If not detected jump, skip EDGE_DETECTED

EDGE_DETECTED:
    ADD     r1, r1, 1
    MOV     r7, 0

LOOP_END:
    SUB     r3, r3, 1
    QBNE    COUNT_LOOP, r3, 0

    // Enviar interrupción al host
    SBBO    r1, r14, 0, 4
    MOV     r31.b0, PRU0_ARM_INTERRUPT + 16

    // Regresar al loop para esperar la siguiente interrupción
    JMP     MAIN_LOOP
EXIT:
    HALT
ERR:    // Signal error
    //LED_ON
    //JMP INITIATIONS
    //JMP ERR
    HALT