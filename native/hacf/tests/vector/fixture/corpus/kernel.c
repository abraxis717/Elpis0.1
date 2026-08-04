#include <stdint.h>

static double dot_product(const float *a, const float *b, uint32_t n) {
    double acc = 0.0;
    for (uint32_t i = 0; i < n; i++) acc += (double)a[i] * (double)b[i];
    return acc;
}

int main(void) {
    return dot_product(0, 0, 0) == 0.0 ? 0 : 1;
}
