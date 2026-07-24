// --- SCRIPT MINIMAL DE PRU ---
// Solo mantiene la lógica de interrupciones Host → PRU y PRU → Host

.origin 0
.entrypoint INIT

#include "PRUassLecture.hp"

#define PIN_MASK 0x0F
// r31: registro de entrada
// r30: registro de salida
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
    MOV     r1, 0            //Used for counting
    MOV     r2, 0
    MOV     r3, 2000000
COUNT_LOOP:
    MOV     r12, r31
    //MOV     r2, r31
    AND     r12, r12, PIN_MASK
    
    QBEQ    LOOP_END, r12, r2
    QBNE    EDGE_DETECTED, r12, 0

NO_EDGE:    
    MOV     r6, r12
    JMP     LOOP_END
EDGE_DETECTED:
    NOT r6, r6
    AND r6, r6, r12
    //MOV     r2, r12
    QBEQ    LOOP_END, r6, 0
    ADD     r1, r1, 1
    JMP     LOOP_END
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