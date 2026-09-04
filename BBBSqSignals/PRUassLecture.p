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

    // Configure the programmable pointer register for PRU by setting c24_pointer // related to pru data RAM. Where the commands will be found
    // This will make C24 point to 0x00000000 (PRU data RAM).
    MOV r0, OWN_RAM | OWN_RAMoffset// | OWN_RAMoffset
    MOV r10, 0x24000+0x20// | C24add//CONST_PRUDRAM
    SBBO    r0, r10, 0, 4//SBCO r0, CONST_PRUDRAM, 0, 4  // Load the base address of PRU0 Data RAM into C

CMDLOOP:
    QBBC    CMDLOOP, r31, 30
    LDI     r0, 21                  // ARM_PRU0_INTERRUPT
    SBCO    r0, C0, 0x24, 4         // SICR: limpia el evento 21
CMDLOOP2:// Double verification of host sending start command
    LBCO    r0.b0, CONST_PRUDRAM, 0, 1 // Load to r0 the content of CONST_PRUDRAM with offset 0, and 1 bytes
    QBEQ    CMDLOOP, r0.b0, 0 // loop until we get an instruction
    SBCO    r4.b0, CONST_PRUDRAM, 0, 1

    LDI     r1, 0
    MOV     r3, 10000000            // window time = r3 * 25 ns = 0,250 s
// COUNT_LOOP:                         // 
//     AND     r12, r31, PIN_MASK      // 1. Selecting just the four first bits of r31 and saving into r12
//     AND     r7,  r12, r2            // 2. As r2 is inverted, when doing and, just 1 if the previous sample has detected a zero
//     NOT     r2,  r12                // 3. The actual from the previous becomes now the previous
//     MIN     r7,  r7, 1              // 4. If r7 register a pulse in channel 4, 3 or 2 will count 8, 5 or 2 respectively. Min compares r7 with 1 and selects the minimum, will be 1 or 0.
//     ADD     r1,  r1, r7             // 5. Sum 0 o 1
//     SUB     r3,  r3, 1              // 6. Substracting one to the counter r3
//     AND     r12, r31, PIN_MASK      // 7. Selecting the following sample
//     AND     r7,  r12, r2            // 8. And so on
//     NOT     r2,  r12                // 9
//     MIN     r7,  r7, 1              // 10
//     ADD     r1,  r1, r7             // 11
//     QBNE    COUNT_LOOP, r3, 0       // 12

COUNT_LOOP:                         // 5 instrucciones = 5 ciclos = 25 ns por muestra
    AND     r12, r31, PIN_MASK      // 1  muestrea los 4 pines
    MIN     r12, r12, 1             // Whatever high value -> 1. otherwise 0
    ADD     r1,  r1, r12            // counter
    SUB     r3,  r3, 1              // substraction window
    QBNE    COUNT_LOOP, r3, 0       // 5

    SBBO    r1, r14, 0, 4
    MOV     r31.b0, PRU0_ARM_INTERRUPT + 16
    JMP     CMDLOOP

EXIT:
    HALT
ERR:
    HALT