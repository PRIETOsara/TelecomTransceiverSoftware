// --- LECTOR DE PULSOS PRU0 ---
// Muestreo directo, sin deteccion de flancos.
// Valido cuando el hueco de muestreo (5 ciclos) es MAYOR que el ON del pulso
// (3 ciclos): ninguna muestra puede caer dos veces en el mismo pulso.

.origin 0
.entrypoint INIT

#include "PRUassLecture.hp"

#define PIN_MASK 0x0F

// r1  = muestras en alto acumuladas
// r3  = iteraciones restantes (1 muestra por vuelta, 5 ciclos = 25 ns)
// r12 = muestra actual
// r14 = destino en shared RAM

INIT:
    LBCO    r0, CONST_PRUCFG, 4, 4
    CLR     r0, r0, 4
    SBCO    r0, CONST_PRUCFG, 4, 4
    MOV     r14, 0x10000

MAIN_LOOP:
    QBBC    MAIN_LOOP, r31, 30
    LDI     r0, 21                  // ARM_PRU0_INTERRUPT
    SBCO    r0, C0, 0x24, 4         // SICR: limpia el evento 21

    LDI     r1, 0
    MOV     r3, 10000000            // window time = r3 * 25 ns = 0,250 s

COUNT_LOOP:                         // 5 instrucciones = 5 ciclos = 25 ns por muestra
    AND     r12, r31, PIN_MASK      // 1  muestrea los 4 pines
    MIN     r12, r12, 1             // Whatever high value -> 1. otherwise 0
    ADD     r1,  r1, r12            // counter
    SUB     r3,  r3, 1              // substraction window
    QBNE    COUNT_LOOP, r3, 0       // 5

    SBBO    r1, r14, 0, 4
    MOV     r31.b0, PRU0_ARM_INTERRUPT + 16
    JMP     MAIN_LOOP

EXIT:
    HALT
ERR:
    HALT