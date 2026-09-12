#include "streaming_regex_ingress_v2.h"
#include <string.h>
int main(void) {
    elpis_streaming_regex_stream_v2* stream = NULL;
    elpis_streaming_regex_result_v1* result = NULL;
    if(elpis_streaming_regex_stream_create_v2(NULL,&stream)) return 1;
    if(elpis_streaming_regex_stream_feed_v2(stream,NULL,0)) return 2;
    if(elpis_streaming_regex_stream_finalize_v2(stream,&result)) return 3;
    elpis_streaming_regex_stream_destroy_v2(stream);
    if(!result || elpis_streaming_regex_result_source_bytes_v1(result)) return 4;
    if(strcmp(elpis_streaming_regex_result_source_sha256_v1(result),
       "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855")) return 5;
    elpis_streaming_regex_result_destroy_v1(result);
    elpis_streaming_regex_stream_destroy_v2(NULL);
    return 0;
}
