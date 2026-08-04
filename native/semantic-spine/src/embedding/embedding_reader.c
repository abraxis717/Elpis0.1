/* embedding_reader.c — Reader stub that delegates to storage module.
 *
 * The read operations are defined in embedding_storage.h and implemented
 * in embedding_writer.c for co-location with the file format knowledge.
 * This file exists as the compile-unit target for the reader interface.
 */
#include "elpis_semantic/embedding_storage.h"

/* All reader functions are defined in embedding_writer.c alongside the
 * format constants and atomic_write helper. They are declared in the
 * public header embedding_storage.h. This translation unit links the
 * symbols into the library. */
