// Blink the radio's status LED (D1 on WL_GPIO0) and report progress on USB/UART stdio.
#include <stdio.h>
#include "pico/stdlib.h"
#include "pico/cyw43_arch.h"

int main(void) {
    stdio_init_all();
    sleep_ms(2000);
    printf("rm2_blink: starting cyw43 on WL_ON=%d CS=%d DATA=%d CLK=%d\n",
           CYW43_DEFAULT_PIN_WL_REG_ON, CYW43_DEFAULT_PIN_WL_CS,
           CYW43_DEFAULT_PIN_WL_DATA_OUT, CYW43_DEFAULT_PIN_WL_CLOCK);
    if (cyw43_arch_init()) {
        printf("rm2_blink: cyw43_arch_init failed (check RM2 solder joints and GPIO 43-46)\n");
        return 1;
    }
    printf("rm2_blink: radio up\n");
    bool on = false;
    while (true) {
        on = !on;
        cyw43_arch_gpio_put(CYW43_WL_GPIO_LED_PIN, on);
        sleep_ms(250);
    }
}
