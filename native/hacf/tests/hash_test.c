#include "elpis/sha256.h"

#include <stdio.h>
#include <string.h>

int main(void) {
    uint8_t digest[32], decoded[32];
    char hex[65];
    elpis_sha256("abc", 3, digest);
    elpis_hex32(digest, hex);
    if (strcmp(hex, "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad") != 0) {
        return 1;
    }
    if (elpis_unhex32(hex, decoded) != 0 || !elpis_digest_equal(digest, decoded)) {
        return 1;
    }
    puts("sha256 checks: PASS");
    return 0;
}
