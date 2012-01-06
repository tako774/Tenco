#!/usr/bin/sh
export LD_LIBRARY_PATH=/usr/local/apr/lib;
time ./glicko_ratings_from_file_to_file 2 ../dat/matched_track_records ../dat/ratings false 2>&1;
